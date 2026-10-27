import type { Graph } from '@maxgraph/core'
import { computed, onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, Room, Session, Workpiece } from '@/collab/kit/collabKitV1'
import { showConflicts } from '@/collab/editing/conflicts'
import { bindGraph } from '@/collab/editing/graphBinding'
import type { SharedCell } from '@/collab/storage/modelCells'
import { CELLS_MAP, linkOf } from '@/collab/storage/workpiece'
import { openWorkpiece } from './openWorkpiece'
import { startPresence, type Person } from '@/collab/presence/presence'

const WORKPIECE_KEY = 'collabWorkpieceId'
const LIVE_CLASS = 'collab-live'

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
let session: Session<SharedCell> | null = null
let lastLiveStatus = ''
let lastOnline = ''

const log = (text: string) => logEntries.value.unshift(`${new Date().toLocaleTimeString()} ${text}`)

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
  session?.close()
  session = null
  isConnected.value = false
  anonymous.value = false
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
  connecting.value = true
  try {
    ck = await loadCollabKit()
    const me = await ck.me.who()
    log(`collab-kit · library v1 · ${me.label ?? 'no name'} (${me.actorId})`)
    const workpiece = await ck.workpieces.get(id)
    anonymousHere = await ck.me.anonymous({ kind: 'workpiece', id })
    log(`collab-kit · workpiece "${workpiece.name}"${anonymousHere ? ' · anonymous' : ''}`)
  } catch (error) {
    log(`collab-kit · workpiece ${id}: ${collabErrorMessage(error)}`)
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
  // The session asks for token and rights itself before every connection.
  const opened = ck.open<SharedCell>(id, { map: CELLS_MAP })
  session = opened
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

  return { isConnected, connecting, workpieceId, linkedWorkpieceId, logEntries, people, anonymous, toggleConnection, openFromRoom }
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
  // shared state replaces it at once.
  const workspace = useModelWorkspaceStore()
  workspace.$onAction(({ name }) => {
    if (!linkedWorkpieceId.value) return
    if (name === 'getRecoverySnapshot') void workspace.discardRecoveryDraft()
    else if (name === 'restoreSnapshot') notifyWarning('This model is shared through a room, so the shared state comes back at once. Branch from the timeline to keep this state.')
  })

  onBeforeUnmount(() => {
    if (session) log('left the editor · closed')
    closeSession()
    editorGraph.value = undefined
    document.body.classList.remove(LIVE_CLASS)
  })
}
