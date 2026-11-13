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
import { bindGraph, type RemoteEdit } from '@/collab/graph/graphBinding'
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
const logEntries = ref<LogEntry[]>([])
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
// Die Personen, wie die Presence sie zuletzt nannte; null bis zur ersten Liste nach dem Verbinden.
let lastPeople: Map<string, Person> | null = null
// Wer gegangen ist, bis das left fällig wird; kommt die Person vorher zurück, war sie nie weg.
const leaving = new Map<string, ReturnType<typeof setTimeout>>()
// Ob die Verbindung weg ist, verloren oder getrennt; das nächste connected meldet sie dann wieder.
let away = false

/** Die Art eines Eintrags im Log. */
export type LogKind = 'failed' | 'joined' | 'left' | RemoteEdit['kind'] | 'saved' | 'release' | 'conflict' | 'connected' | 'offline' | 'closed' | 'rights' | 'undo'
export interface LogEntry {
  kind: LogKind
  /** Bei Einträgen einer Person nur, was sie tat; ihr Name steht im Log über ihrem Block. */
  text: string
  at: number
  /** Wer es war, soweit bekannt, mit der Farbe, die die Person im Modell trägt. */
  by?: string
  color?: string
  /** Bei Änderungen: was alles zusammengefasst ist. */
  edits?: RemoteEdit[]
}
/** Ohne Art ist es Technik: sie geht nur in die Konsole, Studierende brauchen sie nicht. */
export type Log = (text: string, kind?: LogKind) => void

/** Reiht einen Eintrag nach seiner Zeit ein, das Neueste oben; meist ist er selbst der neueste. */
const addEntry = (entry: LogEntry) => {
  const index = logEntries.value.findIndex(({ at }) => at <= entry.at)
  logEntries.value.splice(index < 0 ? logEntries.value.length : index, 0, entry)
}

const log: Log = (text, kind) => {
  if (kind) addEntry({ kind, text, at: Date.now() })
  else console.debug(`[collab] ${text}`)
}

/** Ein Eintrag einer Person; ohne Farbe die, die sie gerade im Modell trägt. */
const logBy = (kind: LogKind, by: string, text: string, at = Date.now(), color = people.value.find((person) => person.name === by)?.color) => addEntry({ kind, text, at, by, color })

/** Wie lange nach dem Sync die Presence der anderen noch eintrifft und als Stand beim Verbinden gilt. */
const SETTLE_MS = 3000
/** Wie lange eine Person weg sein muss, bis sie als gegangen gilt; Hintergrund-Tabs melden sich gedrosselt nur etwa jede Minute. */
const LEAVE_MS = 90_000

/** Wie lange Änderungen derselben Person in einem Eintrag zusammenlaufen. */
const MERGE_MS = 2 * 60_000
/**
 * Wer eine Änderung gemacht hat; collab-kit sagt es nicht. Gesperrt ist, was ein anderer ausgewählt hat, also
 * war es die eine andere Person, deren Auswahl in der Presence eine der Zellen hat. Sonst, etwa nach einem
 * Löschen mit schon leerer Auswahl, die einzige andere Person, wenn nur eine da ist.
 */
const authorOf = (keys: string[]) => {
  const others = people.value.filter((person) => !person.self)
  const changed = new Set(keys)
  const selecting = (session?.presence.people() ?? []).filter((person) => !person.self && person.clients.some(({ state }) => Array.isArray(state.selection) && state.selection.some((id) => changed.has(id))))
  if (selecting.length === 1) return others.find((person) => person.id === selecting[0].id)
  return selecting.length === 0 && others.length === 1 ? others[0] : undefined
}

/** Ein Element beim Namen, ohne einen allgemein. */
export const elementName = ({ name, edge }: { name?: string; edge: boolean }) => name || (edge ? 'a connection' : 'an element')

/** Ein Element nennt es beim Namen, mehrere zählt es; ein Umbenennen zeigt den ersten und den letzten Namen. */
const editText = (kind: RemoteEdit['kind'], edits: RemoteEdit[]) => {
  const elements = new Set(edits.map(({ id }) => id)).size
  if (elements > 1) return `${kind} ${elements} elements`
  const last = edits[edits.length - 1]
  return kind === 'renamed' ? `renamed ${elementName({ ...last, name: edits[0].from })} to ${elementName(last)}` : `${kind} ${elementName(last)}`
}

/** Eine Änderung eines anderen, ein Eintrag je Art; gleiche Art derselben Person kurz davor läuft dort weiter. */
const logChange = (keys: string[], edits: RemoteEdit[]) => {
  const author = authorOf(keys)
  const now = Date.now()
  for (const kind of new Set(edits.map((edit) => edit.kind))) {
    const index = logEntries.value.findIndex((entry) => entry.kind === kind && entry.by === author?.name && now - entry.at < MERGE_MS)
    const merged = [...(logEntries.value[index]?.edits ?? []), ...edits.filter((edit) => edit.kind === kind)]
    if (index >= 0) logEntries.value.splice(index, 1)
    logEntries.value.unshift({ kind, text: editText(kind, merged), at: now, by: author?.name, color: author?.color, edits: merged })
  }
}

/** Die Close-Codes von collab-kit in Worten; 4000 plus Status eines Aufrufs vor dem Verbinden. */
const CLOSE_REASONS: Record<number, string> = {
  4401: 'your sign-in expired',
  4403: 'your access was withdrawn',
  4404: 'the model no longer exists',
  4409: 'your rights changed'
}

const rightsText = (mayWrite: boolean) => (mayWrite ? 'you can edit' : 'you can only view')

/** Die Farbe für Änderungen, die keiner Person zuzuordnen sind. */
export const SOMEONE_COLOR = '#757575'
// Die Rahmen des zuletzt gezeigten Eintrags; ein neuer nimmt sie weg, die des Hoverns auch das Verlassen.
let unframeShown: (() => void)[] = []
let hovering = false

/**
 * Zeigt die Elemente eines Eintrags im Editor, eingerahmt in der Farbe der Person und nicht ausgewählt, denn
 * eine Auswahl sperrte sie für die anderen. Beim Hovern bleibt der Rahmen bis hideEdits, ein Klick scrollt hin.
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

/** Nimmt die Rahmen des Hoverns weg; die eines Klicks bleiben ihre Zeit. */
export const hideEdits = () => {
  if (!hovering) return
  unframeShown.forEach((unframe) => unframe())
  unframeShown = []
  hovering = false
}

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
  for (const timer of leaving.values()) clearTimeout(timer)
  leaving.clear()
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
    // Prüfen Anmeldung und Zugang zum Werkstück; scheitern sie, sagt es der Fehler unten.
    await ck.me.who()
    await ck.workpieces.get(id)
    anonymousHere = await ck.me.anonymous({ kind: 'workpiece', id })
    if (anonymousHere) log('collab-kit · anonymous at this workpiece')
    // Ohne lesbaren Raum bleibt es beim Verhalten der Share; die Verbindung hängt nicht daran.
    const roomId = roomIdOf(id)
    role = roomId ? await ck.rooms.get(roomId).then(roleOf, () => null) : null
    // A host who is back wakes the sweep of the backend, which then opens a room it had locked.
    // Im Gruppenraum gibt es keine Share, die das Backend wecken könnte.
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
  // Vor der Presence, denn die Namen hängen an der Rolle.
  roomRole.value = role
  // The session asks for token and rights itself before every connection.
  const opened = ck.open<ModelUnit>(id, { map: CELLS_MAP })
  session = opened
  holdSession(opened)
  anonymous.value = anonymousHere
  let synced = false
  let settledAt = Infinity
  away = false
  opened.on('status', (status) => {
    const before = lastLiveStatus
    logLiveStatus(status)
    // Das erste connected meldet synced; danach nur, wenn die Verbindung weg war.
    if (!synced) return
    if (status === 'connected' && away) {
      away = false
      log(`Connected · ${rightsText(opened.mayWrite)}`, 'connected')
    } else if ((status === 'connecting' || status === 'disconnected') && before === 'connected' && !away) {
      away = true
      log('Connection lost · reconnecting…', 'offline')
    }
  })
  // The library asks again on every reconnect and tells the new value only when it changed.
  opened.on('anonymityChanged', (value) => (anonymous.value = value))
  opened.on('closed', ({ code, reason }) => {
    log(`closed by collab-kit · ${code} ${reason}`)
    away = true
    log(`Disconnected · ${CLOSE_REASONS[code] ?? 'the connection was closed'} (${code})`, 'closed')
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
      settledAt = Date.now() + SETTLE_MS
      log(`Connected · ${rightsText(opened.mayWrite)}`, 'connected')
    },
    () => undefined
  )
  unbind = bindGraph(graph, opened, log, logChange)
  stopConflicts = showConflicts(graph, opened, log)
  stopShare = watchShare(opened)
  // Beim Beenden einer Share sperrt der Host den Raum; ein Abgleich mittendrin wäre ein Ablauf zu viel.
  stopCheckpoints = watchCheckpoints(
    opened,
    () => shareDialog.value === 'quit',
    (by, label) => {
      if (!label) {
        logBy('saved', by, 'saved')
        return
      }
      logBy('release', by, `created release ${label}`)
      announceRelease({ by, label })
    }
  )
  lastOnline = ''
  lastPeople = null
  stopPresence = startPresence(graph, opened, (list, clients) => {
    people.value = list
    // Wer kam und ging, außer einem selbst; bis kurz nach dem Sync ist es nur der Stand beim Verbinden.
    const now = new Map(list.flatMap((person) => (person.self ? [] : [[person.id, person] as const])))
    if (lastPeople && Date.now() > settledAt) {
      for (const [id, person] of now) {
        if (lastPeople.has(id)) continue
        if (!leaving.has(id)) logBy('joined', person.name, 'joined', Date.now(), person.color)
        clearTimeout(leaving.get(id))
        leaving.delete(id)
      }
      for (const [id, person] of lastPeople) {
        if (now.has(id)) continue
        const at = Date.now()
        leaving.set(
          id,
          setTimeout(() => {
            leaving.delete(id)
            logBy('left', person.name, 'left', at, person.color)
          }, LEAVE_MS)
        )
      }
    }
    lastPeople = now
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
    log('Disconnected', 'closed')
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
