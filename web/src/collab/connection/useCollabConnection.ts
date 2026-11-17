import type { Graph } from '@maxgraph/core'
import { computed, onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import { cloneJson } from '@/model/ModelSnapshot'
import type { WorkspaceLanguageReference } from '@/services/api/types/model'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, Room, Session, Workpiece } from '@/collab/kit/collabKitV1'
import { holdSession } from '@/collab/kit/liveSession'
import { frameCell, showConflicts } from '@/collab/graph/conflicts'
import { bindGraph } from '@/collab/graph/graphBinding'
import { LANGUAGES_KEY, languagesChange, type ModelUnit } from '@/collab/converters/model/modelUnits'
import { CELLS_MAP, linkOf } from '@/collab/storage/workpiece'
import { checkShareGone, resumeShare, shareDialog } from '@/collab/sharing/shareModel'
import { watchCheckpoints } from '@/collab/storage/workpieceVersions'
import { watchShare } from '@/collab/sharing/watchShare'
import { roleOf, roomRole, type RoomRole } from '@/collab/rooms/roomRole'
import { openWorkpiece } from './openWorkpiece'
import { startPresence, type Person } from '@/collab/presence/presence'
import { COLLAB_AREAS, isCollabArea, loadCollabSettings, type CollabArea } from '@/collab/settings/collabSettings'
import { log, logBy, logChange, logEntries, SOMEONE_COLOR, trackPeople, type LogEntry, type LogKind } from './collabLog'

const WORKPIECE_KEY = 'collabWorkpieceId'
const LIVE_CLASS = 'collab-live'
/** The actions of the workspace that change the languages of the model. */
const LANGUAGE_ACTIONS = new Set(['addLanguage', 'changeLanguageVersion', 'removeLanguage', 'moveLanguage', 'importFile'])

// One connection for the page: the editor holds it, the sync sidebar only shows it.
const isConnected = ref(false)
const connecting = ref(false)
const workpieceId = ref(localStorage.getItem(WORKPIECE_KEY) ?? '')
const people = ref<Person[]>([])
// Whether the own person writes anonymously at the workpiece, so others see a pseudonym.
const anonymous = ref(false)
const editorGraph = shallowRef<Graph>()
let unbind: (() => void) | null = null
let stopPresence: (() => void) | null = null
let stopConflicts: (() => void) | null = null
let stopShare: (() => void) | null = null
let stopCheckpoints: (() => void) | null = null
let stopPeopleLog: (() => void) | null = null
let session: Session<ModelUnit> | null = null
let lastLiveStatus = ''
let lastOnline = ''
// Whether the connection is gone, lost or disconnected; the next connected then reports it again.
let away = false
// The workpiece the log belongs to, and how the connection entries name it: model and room.
let loggedWorkpiece = ''
let place = 'the model'

/** An entry of a person, in the color they wear in the model now. */
const logPerson = (kind: LogKind, by: string, text: string) => logBy(kind, by, text, Date.now(), people.value.find((person) => person.name === by)?.color)

/**
 * Who made a change; collab-kit does not tell. What another selected is locked, so it was the one other
 * person whose selection in the presence holds one of the cells. Otherwise, such as after deleting with
 * the selection already empty, the only other person, if just one is there.
 */
const authorOf = (keys: string[]) => {
  const others = people.value.filter((person) => !person.self)
  const changed = new Set(keys)
  const selecting = (session?.presence.people() ?? []).filter((person) => !person.self && person.clients.some(({ state }) => Array.isArray(state.selection) && state.selection.some((id) => changed.has(id))))
  if (selecting.length === 1) return others.find((person) => person.id === selecting[0].id)
  return selecting.length === 0 && others.length === 1 ? others[0] : undefined
}

/** The close codes of collab-kit in words; 4000 plus the status of a call before connecting. */
const CLOSE_REASONS: Record<number, string> = {
  4401: 'your sign-in expired',
  4403: 'your access was withdrawn',
  4404: 'the model no longer exists',
  4409: 'your rights changed'
}

const rightsText = (mayWrite: boolean) => (mayWrite ? 'you can edit' : 'you can only view')

// The frames of the entry shown last; a new one takes them away, those of hovering also leaving it.
let unframeShown: (() => void)[] = []
let hovering = false

/**
 * Shows the elements of an entry in the editor, framed in the person's color and not selected, as a
 * selection would lock them for the others. On hover the frame stays until hideEdits, a click scrolls there.
 */
export const showEdits = (entry: LogEntry, hover = false) => {
  const graph = editorGraph.value
  if (!graph || !entry.edits) return
  unframeShown.forEach((unframe) => unframe())
  hovering = hover
  const ids = [...new Set(entry.edits.map(({ id }) => id))]
  const cells = ids.flatMap((id) => graph.getDataModel().getCell(id) ?? [])
  if (!hover && cells.length === 0) notifyWarning('No longer in the model.')
  if (!hover && cells.length > 0) graph.scrollCellToVisible(cells[0], true)
  unframeShown = ids.flatMap((id) => frameCell(graph, id, entry.color ?? SOMEONE_COLOR, hover ? Infinity : undefined) ?? [])
}

/** Takes away the frames of hovering; those of a click stay their time. */
export const hideEdits = () => {
  if (!hovering) return
  unframeShown.forEach((unframe) => unframe())
  unframeShown = []
  hovering = false
}

/** How long the bar above the model shows a release by someone else. */
const RELEASE_NOTICE_MS = 10_000
/** The release someone else just made; the bar shows it briefly, the log keeps it. */
const recentRelease = ref<{ by: string; label: string } | null>(null)
let releaseTimer: ReturnType<typeof setTimeout> | undefined
const announceRelease = (release: { by: string; label: string }) => {
  recentRelease.value = release
  clearTimeout(releaseTimer)
  releaseTimer = setTimeout(() => (recentRelease.value = null), RELEASE_NOTICE_MS)
}

// Reconnect attempts repeat the same status; the log keeps only the changes.
const logLiveStatus = (status: string) => {
  if (status === lastLiveStatus) return
  lastLiveStatus = status
  log(`live · ${status}`)
}

/** Ends the session for good; the next connect opens a new one. */
const closeSession = () => {
  unbind?.()
  unbind = null
  stopPresence?.()
  stopPresence = null
  stopConflicts?.()
  stopConflicts = null
  stopShare?.()
  stopShare = null
  stopCheckpoints?.()
  stopCheckpoints = null
  stopPeopleLog?.()
  stopPeopleLog = null
  session?.close()
  session = null
  holdSession(null)
  isConnected.value = false
  anonymous.value = false
  roomRole.value = null
}

/** The room of the open model if it is linked to this workpiece; the model knows it from its link. */
const roomIdOf = (id: string) => {
  const link = linkOf(useModelWorkspaceStore().model?.preferences)
  return link?.workpieceId === id ? link.roomId : null
}

/** Writes the languages beside the cells and out of the undo of the graph; others take them when they open the model next. */
const writeLanguages = (id: string | null, languages: WorkspaceLanguageReference[]) => {
  if (!session || session.workpieceId !== id || !session.mayWrite) return
  if (JSON.stringify(session.units.get(LANGUAGES_KEY)) === JSON.stringify(languages)) return
  session.units.update(languagesChange(languages), { undoable: false })
}

/** Reads an area of the collab settings; if that fails, the values so far stay. */
const loadSettings = (ck: CollabKitApi, area: CollabArea) => loadCollabSettings(ck, area).catch((error) => log(`collab-kit · settings ${area}: ${collabErrorMessage(error)}`))

const connect = async (id: string) => {
  if (connecting.value || isConnected.value) return
  if (!editorGraph.value) {
    notifyWarning('No graph available.')
    return
  }
  // The same workpiece again: the doc kept what changed meanwhile and sends it on.
  if (session?.workpieceId === id) {
    session.connect()
    isConnected.value = true
    return
  }

  // One log per workpiece: entries of another model, its people and elements do not belong here.
  if (loggedWorkpiece !== id) {
    logEntries.value = []
    loggedWorkpiece = id
    place = 'the model'
  }
  let ck: CollabKitApi
  let anonymousHere = false
  let role: RoomRole | null = null
  connecting.value = true
  try {
    ck = await loadCollabKit()
    // Check sign-in and access to the workpiece; if they fail, the error below tells.
    await ck.me.who()
    // The collab settings apply to the whole instance; the connection does not wait for them.
    for (const area of COLLAB_AREAS) void loadSettings(ck, area)
    const workpiece = await ck.workpieces.get(id)
    anonymousHere = await ck.me.anonymous({ kind: 'workpiece', id })
    if (anonymousHere) log('collab-kit · anonymous at this workpiece')
    // Without a readable room the behavior of a share stays; the connection does not depend on it.
    const roomId = roomIdOf(id)
    role = roomId ? await ck.rooms.get(roomId).then(roleOf, () => null) : null
    place = `"${workpiece.name}"${role ? ` in ${role.name}` : ''}`
    // A host who is back wakes the sweep of the backend, which then opens a room it had locked.
    // A group room has no share that could wake the backend.
    if (role?.kind !== 'group') void resumeShare()
  } catch (error) {
    log(`collab-kit · workpiece ${id}: ${collabErrorMessage(error)}`)
    log(`Couldn't open the model · ${collabErrorMessage(error)}`, 'failed')
    // A visitor who cannot reach the workpiece any more, e.g. after a reload into a closed room, must not sit here.
    void checkShareGone()
    return
  } finally {
    connecting.value = false
  }
  // The editor may have gone meanwhile; its graph is then no longer there to bind.
  const graph = editorGraph.value
  if (!graph || isConnected.value) return

  workpieceId.value = id
  localStorage.setItem(WORKPIECE_KEY, id)
  lastLiveStatus = ''
  closeSession()
  // Before the presence, as the names depend on the role.
  roomRole.value = role
  // The session asks for token and rights itself before every connection.
  const opened = ck.open<ModelUnit>(id, { map: CELLS_MAP })
  session = opened
  holdSession(opened)
  anonymous.value = anonymousHere
  let synced = false
  const peopleLog = trackPeople()
  stopPeopleLog = peopleLog.stop
  away = false
  opened.on('status', (status) => {
    const before = lastLiveStatus
    logLiveStatus(status)
    // The first connected is reported by synced; after that only if the connection was gone.
    if (!synced) return
    if (status === 'connected' && away) {
      away = false
      log(`Connected to ${place} · ${rightsText(opened.mayWrite)}`, 'connected')
    } else if ((status === 'connecting' || status === 'disconnected') && before === 'connected' && !away) {
      away = true
      log('Connection lost · reconnecting…', 'offline')
    }
  })
  // The library asks again on every reconnect and tells the new value only when it changed.
  opened.on('anonymityChanged', (value) => (anonymous.value = value))
  // Changed or reset in the "Collab settings" tab: read the area again, it applies on its next use.
  opened.on('settingsChanged', (key) => {
    if (isCollabArea(key)) void loadSettings(ck, key)
  })
  opened.on('closed', ({ code, reason }) => {
    log(`closed by collab-kit · ${code} ${reason}`)
    away = true
    log(`Disconnected from ${place} · ${CLOSE_REASONS[code] ?? 'the connection was closed'} (${code})`, 'closed')
    // Before synced the doc never held the state of collab-kit, so the next connect starts afresh.
    if (synced) isConnected.value = false
    else closeSession()
    // Ends the stay of a visitor whose room is gone, also when the host left without the lock.
    // A group room is no share; a running share in another tab does not concern it.
    if (role?.kind !== 'group') void checkShareGone()
  })
  // Rejected when the session ends before; closed tells why.
  opened.synced.then(
    () => {
      synced = true
      peopleLog.settle()
      log(`Connected to ${place} · ${rightsText(opened.mayWrite)}`, 'connected')
    },
    () => undefined
  )
  unbind = bindGraph(graph, opened, log, (keys, edits) => logChange(authorOf(keys), edits))
  stopConflicts = showConflicts(graph, opened, log)
  stopShare = watchShare(opened)
  // On ending a share the host locks the room; a rebase in the middle of it would be one run too many.
  stopCheckpoints = watchCheckpoints(
    opened,
    () => shareDialog.value === 'quit',
    (by, label) => {
      if (!label) {
        logPerson('saved', by, 'saved')
        return
      }
      logPerson('release', by, `created release ${label}`)
      announceRelease({ by, label })
    }
  )
  lastOnline = ''
  stopPresence = startPresence(graph, opened, (list, clients) => {
    people.value = list
    peopleLog.update(list)
    // Selections change often; the log notes only who is there and how many clients announce themselves.
    const online = `${list.map((person) => (person.self ? `${person.name} (you)` : person.name)).join(', ') || 'nobody'} · ${clients} clients`
    if (online === lastOnline) return
    lastOnline = online
    log(`online · ${online}`)
  })
  isConnected.value = true
}

/** The button under the ID field: connects to the ID typed in, or disconnects. */
const toggleConnection = () => {
  if (isConnected.value) {
    // Only the connection goes; edits made meanwhile go out on connect.
    away = true
    log(`Disconnected from ${place}`, 'closed')
    session?.disconnect()
    isConnected.value = false
    return
  }
  const id = workpieceId.value.trim()
  if (!id) {
    notifyWarning('Enter a workpiece ID.')
    return
  }
  void connect(id)
}

/** The connection as the sync sidebar shows it, and opening the models of rooms. */
export const useCollabConnection = () => {
  const router = useRouter()
  const route = useRoute()
  const workspace = useModelWorkspaceStore()

  /**
   * The workpiece the open model shares, if it is one of a room. None while the store still holds
   * the model before: the editor mounts first and loads its model only then.
   */
  const linkedWorkpieceId = computed(() => (workspace.model && workspace.model.id === route.params.modelId ? linkOf(workspace.model.preferences)?.workpieceId ?? null : null))

  /** A model of a room: the open one just connects, any other opens the own model of it. */
  const openFromRoom = async (room: Room, workpiece: Workpiece) => {
    if (linkedWorkpieceId.value === workpiece._id) {
      await connect(workpiece._id)
      return
    }
    closeSession()
    try {
      await openWorkpiece(router, room, workpiece)
    } catch (error) {
      notifyError(`The model could not be opened: ${(error as Error).message}`)
    }
  }

  return { isConnected, connecting, workpieceId, linkedWorkpieceId, logEntries, people, anonymous, recentRelease, toggleConnection, openFromRoom }
}

/**
 * Called by the editor: binds its graph, connects by itself to the workpiece of a model of a room,
 * and lets go when the editor goes, whichever sidebar tab is shown meanwhile.
 */
export const holdCollabConnection = (graph: Ref<Graph | undefined>) => {
  const { linkedWorkpieceId } = useCollabConnection()

  // The graph comes only once the canvas has mounted, after this component.
  watch(graph, (current) => (editorGraph.value = current), { immediate: true })
  watch(
    [linkedWorkpieceId, editorGraph],
    ([id, current]) => {
      // Another model in the editor ends the session of the one before, so its state never lands in this one.
      if (session && session.workpieceId !== id) closeSession()
      if (id && current && !isConnected.value) void connect(id)
    },
    { immediate: true }
  )

  // Marks the page while edits go live to collab-kit, so the sync tab shows it whichever tab is open.
  watch(isConnected, (live) => document.body.classList.toggle(LIVE_CLASS, live), { immediate: true })

  // A model of a room shows the shared state, whatever the Copilot kept of its own. Runs before the
  // action: the local draft goes before the editor offers it, and a restore is explained, as the
  // shared state replaces it at once. Changed languages go to the workpiece after their action.
  const workspace = useModelWorkspaceStore()
  workspace.$onAction(({ name, after }) => {
    const id = linkedWorkpieceId.value
    if (!id) return
    if (name === 'getRecoverySnapshot') void workspace.discardRecoveryDraft()
    else if (name === 'restoreSnapshot') notifyWarning('This model is shared through a room, so the shared state comes back at once. Branch from the timeline to keep this state.')
    else if (LANGUAGE_ACTIONS.has(name)) after(() => writeLanguages(id, cloneJson(workspace.languages)))
  })

  onBeforeUnmount(() => {
    closeSession()
    editorGraph.value = undefined
    document.body.classList.remove(LIVE_CLASS)
  })
}
