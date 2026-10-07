import type { Graph } from '@maxgraph/core'
import { computed, onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { collabErrorMessage, getRights, getWorkpiece, type CollabRoom, type CollabWorkpiece } from './collabApi'
import { openCollabSession, type CollabSession } from './collabSession'
import { bindGraph } from './graphBinding'
import { linkOf, openWorkpiece } from './openWorkpiece'
import { startPresence, type Person } from './presence'

const WORKPIECE_KEY = 'collabWorkpieceId'
const LIVE_CLASS = 'collab-live'

// One connection for the page: the editor holds it, the sync sidebar only shows it.
const isConnected = ref(false)
const connecting = ref(false)
const workpieceId = ref(localStorage.getItem(WORKPIECE_KEY) ?? '')
const logEntries = ref<string[]>([])
const people = ref<Person[]>([])
const editorGraph = shallowRef<Graph>()
let unbind: (() => void) | null = null
let stopPresence: (() => void) | null = null
let session: CollabSession | null = null
let lastLiveStatus = ''
let lastOnline = ''

const log = (text: string) => logEntries.value.unshift(`${new Date().toLocaleTimeString()} ${text}`)

// Reconnect attempts repeat the same status; the log keeps only the changes.
const logLiveStatus = (status: string) => {
  if (status === lastLiveStatus) return
  lastLiveStatus = status
  log(`live · ${status}`)
}

const disconnect = () => {
  unbind?.()
  unbind = null
  stopPresence?.()
  stopPresence = null
  session?.close()
  session = null
  isConnected.value = false
}

const connect = async (id: string) => {
  if (connecting.value || isConnected.value) return
  if (!editorGraph.value) {
    notifyWarning('No graph available.')
    return
  }

  let canWrite = false
  connecting.value = true
  try {
    const workpiece = (await getWorkpiece(id)).data
    const rights = (await getRights({ kind: 'workpiece', id })).data
    canWrite = rights.includes('edit')
    log(`collab-kit · workpiece "${workpiece.name}" · rights: ${rights.join(', ') || 'none'}`)
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
  session = openCollabSession(id, logLiveStatus)
  session.onClosed((reason) => {
    disconnect()
    log(`disconnected by collab-kit · ${reason}`)
  })
  unbind = bindGraph(graph, session, canWrite, log)
  lastOnline = ''
  stopPresence = startPresence(graph, session, (list, clients) => {
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
    disconnect()
    log('disconnected')
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
  const workspace = useModelWorkspaceStore()

  /** The workpiece the open model shares, if it is one of a room. */
  const linkedWorkpieceId = computed(() => linkOf(workspace.model?.preferences)?.workpieceId ?? null)

  /** A model of a room: the open one just connects, any other opens the own model of it. */
  const openFromRoom = async (room: CollabRoom, workpiece: CollabWorkpiece) => {
    if (linkedWorkpieceId.value === workpiece._id) {
      await connect(workpiece._id)
      return
    }
    disconnect()
    try {
      await openWorkpiece(router, room, workpiece)
    } catch (error) {
      notifyError(`The model could not be opened: ${(error as Error).message}`)
    }
  }

  return { isConnected, connecting, workpieceId, linkedWorkpieceId, logEntries, people, toggleConnection, openFromRoom }
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
      if (id && current && !isConnected.value) void connect(id)
    },
    { immediate: true }
  )

  // Marks the page while edits go live to collab-kit, so the sync tab shows it whichever tab is open.
  watch(isConnected, (live) => document.body.classList.toggle(LIVE_CLASS, live), { immediate: true })

  onBeforeUnmount(() => {
    if (isConnected.value) log('left the editor · disconnected')
    disconnect()
    editorGraph.value = undefined
    document.body.classList.remove(LIVE_CLASS)
  })
}
