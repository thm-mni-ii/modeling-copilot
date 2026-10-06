import type { Graph } from '@maxgraph/core'
import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { collabErrorMessage, getRights, getWorkpiece, type CollabRoom, type CollabWorkpiece } from './collabApi'
import { openCollabSession, type CollabSession } from './collabSession'
import { bindGraph } from './graphBinding'
import { linkOf, openWorkpiece } from './openWorkpiece'
import { startPresence, type Person } from './presence'

const WORKPIECE_KEY = 'collabWorkpieceId'

/** The live connection of the sync sidebar: connecting, the event log, and opening models of rooms. */
export const useCollabConnection = (graph: Ref<Graph | undefined>) => {
  const router = useRouter()
  const workspace = useModelWorkspaceStore()

  const isConnected = ref(false)
  const connecting = ref(false)
  const workpieceId = ref(localStorage.getItem(WORKPIECE_KEY) ?? '')
  const logEntries = ref<string[]>([])
  const people = ref<Person[]>([])
  let unbind: (() => void) | null = null
  let stopPresence: (() => void) | null = null
  let session: CollabSession | null = null
  let lastLiveStatus = ''

  /** The workpiece the open model shares, if it is one of a room. */
  const linkedWorkpieceId = computed(() => linkOf(workspace.model?.preferences)?.workpieceId ?? null)

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
    if (!graph.value) {
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
    // Opening another model meanwhile unmounts the sidebar; its graph is then no longer this one.
    if (!graph.value || isConnected.value) return

    workpieceId.value = id
    localStorage.setItem(WORKPIECE_KEY, id)
    lastLiveStatus = ''
    session = openCollabSession(id, logLiveStatus)
    session.onClosed((reason) => {
      disconnect()
      log(`disconnected by collab-kit · ${reason}`)
    })
    unbind = bindGraph(graph.value, session, canWrite, log)
    stopPresence = startPresence(graph.value, session, (list) => (people.value = list))
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

  // A model of a room connects by itself as soon as the sync sidebar shows it.
  watch(
    linkedWorkpieceId,
    (id) => {
      if (id && !isConnected.value) void connect(id)
    },
    { immediate: true }
  )

  onBeforeUnmount(disconnect)

  return { isConnected, connecting, workpieceId, linkedWorkpieceId, logEntries, people, toggleConnection, openFromRoom }
}
