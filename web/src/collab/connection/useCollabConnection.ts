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
import { showConflicts } from '@/collab/graph/conflicts'
import { bindGraph } from '@/collab/graph/graphBinding'
import { LANGUAGES_KEY, languagesChange, type ModelUnit } from '@/collab/converters/model/modelUnits'
import { CELLS_MAP, linkOf } from '@/collab/storage/workpiece'
import { checkShareGone, resumeShare, shareDialog } from '@/collab/sharing/shareModel'
import { watchCheckpoints } from '@/collab/storage/workpieceVersions'
import { watchShare } from '@/collab/sharing/watchShare'
import { roleOf, roomRole, type RoomRole } from '@/collab/rooms/roomRole'
import { openWorkpiece } from './openWorkpiece'
import { startPresence, type Person } from '@/collab/presence/presence'

const WORKPIECE_KEY = 'collabWorkpieceId'
const LIVE_CLASS = 'collab-live'
/** The actions of the workspace that change the languages of the model. */
const LANGUAGE_ACTIONS = new Set(['addLanguage', 'changeLanguageVersion', 'removeLanguage', 'moveLanguage', 'importFile'])

// One connection for the page: the editor holds it, the sync sidebar only shows it.
const isConnected = ref(false)
const connecting = ref(false)
const workpieceId = ref(localStorage.getItem(WORKPIECE_KEY) ?? '')
const logEntries = ref<string[]>([])
const people = ref<Person[]>([])
// Whether the own person writes anonymously at the workpiece, so others see a pseudonym.
const anonymous = ref(false)
const editorGraph = shallowRef<Graph>()
let unbind: (() => void) | null = null
let stopPresence: (() => void) | null = null
let stopConflicts: (() => void) | null = null
let stopShare: (() => void) | null = null
let stopCheckpoints: (() => void) | null = null
let session: Session<ModelUnit> | null = null
let lastLiveStatus = ''
let lastOnline = ''

const log = (text: string) => logEntries.value.unshift(`${new Date().toLocaleTimeString()} ${text}`)

/** Wie lange die Leiste über dem Modell ein Release eines anderen zeigt. */
const RELEASE_NOTICE_MS = 10_000
/** Das Release, das ein anderer eben gemacht hat; die Leiste zeigt es kurz, das Log behält es. */
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
  session?.close()
  session = null
  holdSession(null)
  isConnected.value = false
  anonymous.value = false
  roomRole.value = null
}

/** Der Raum des offenen Modells, wenn es mit diesem Werkstück verknüpft ist; das Modell kennt ihn aus seiner Verknüpfung. */
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

  let ck: CollabKitApi
  let anonymousHere = false
  let role: RoomRole | null = null
  connecting.value = true
  try {
    ck = await loadCollabKit()
    const me = await ck.me.who()
    log(`collab-kit · library v1 · ${me.label ?? 'no name'} (${me.actorId})`)
    const workpiece = await ck.workpieces.get(id)
    anonymousHere = await ck.me.anonymous({ kind: 'workpiece', id })
    log(`collab-kit · workpiece "${workpiece.name}"${anonymousHere ? ' · anonymous' : ''}`)
    // Ohne lesbaren Raum bleibt es beim Verhalten der Share; die Verbindung hängt nicht daran.
    const roomId = roomIdOf(id)
    role = roomId ? await ck.rooms.get(roomId).then(roleOf, () => null) : null
    if (role) log(`collab-kit · room "${role.name}" · ${role.kind === 'group' ? 'group room' : 'shared'}`)
    // A host who is back wakes the sweep of the backend, which then opens a room it had locked.
    // Im Gruppenraum gibt es keine Share, die das Backend wecken könnte.
    if (role?.kind !== 'group') void resumeShare()
  } catch (error) {
    log(`collab-kit · workpiece ${id}: ${collabErrorMessage(error)}`)
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
  // Vor der Presence, denn die Namen hängen an der Rolle.
  roomRole.value = role
  // The session asks for token and rights itself before every connection.
  const opened = ck.open<ModelUnit>(id, { map: CELLS_MAP })
  session = opened
  holdSession(opened)
  anonymous.value = anonymousHere
  let synced = false
  opened.on('status', logLiveStatus)
  // The library asks again on every reconnect and tells the new value only when it changed.
  opened.on('anonymityChanged', (value) => (anonymous.value = value))
  opened.on('closed', ({ code, reason }) => {
    log(`closed by collab-kit · ${code} ${reason}`)
    // Before synced the doc never held the state of collab-kit, so the next connect starts afresh.
    if (synced) isConnected.value = false
    else closeSession()
    // Ends the stay of a visitor whose room is gone, also when the host left without the lock.
    // Ein Gruppenraum ist keine Share; eine laufende Share in einem anderen Tab geht ihn nichts an.
    if (role?.kind !== 'group') void checkShareGone()
  })
  // Rejected when the session ends before; closed tells why.
  opened.synced.then(
    () => {
      synced = true
      log(`live · synced · ${opened.mayWrite ? 'may edit' : 'read only'}`)
    },
    () => undefined
  )
  unbind = bindGraph(graph, opened, log)
  stopConflicts = showConflicts(graph, opened, log)
  stopShare = watchShare(opened)
  // Beim Beenden einer Share sperrt der Host den Raum; ein Abgleich mittendrin wäre ein Ablauf zu viel.
  stopCheckpoints = watchCheckpoints(
    opened,
    () => shareDialog.value === 'quit',
    (by, label) => {
      log(`${by} created release ${label}`)
      announceRelease({ by, label })
    }
  )
  lastOnline = ''
  stopPresence = startPresence(graph, opened, (list, clients) => {
    people.value = list
    // Selections change often; the log notes only who is there and how many clients announce themselves.
    const online = `${list.map((person) => (person.self ? `${person.name} (you)` : person.name)).join(', ') || 'nobody'} · ${clients} clients`
    if (online === lastOnline) return
    lastOnline = online
    log(`online · ${online}`)
  })
  isConnected.value = true
  log('connected')
}

/** The button under the ID field: connects to the ID typed in, or disconnects. */
const toggleConnection = () => {
  if (isConnected.value) {
    // Only the connection goes; edits made meanwhile go out on connect.
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
      if (session && session.workpieceId !== id) {
        log('other model in the editor · closed')
        closeSession()
      }
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
    if (session) log('left the editor · closed')
    closeSession()
    editorGraph.value = undefined
    document.body.classList.remove(LIVE_CLASS)
  })
}
