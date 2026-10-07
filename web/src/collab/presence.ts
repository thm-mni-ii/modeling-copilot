import { CellHighlight, InternalEvent, type Graph } from '@maxgraph/core'
import authService from '@/services/auth/auth.service'
import type { TokenClaims } from '@/services/api/types/auth'
import type { CollabSession } from './collabSession'
import { startCursors } from './cursors'

/** One person at the workpiece, once however many tabs they have open. */
export interface Person {
  id: string
  name: string
  color: string
  self: boolean
}

/** What every client announces of itself. */
interface PresenceState {
  user?: { id: string; name: string }
  selection?: string[]
}

const COLORS = ['#e53935', '#1e88e5', '#43a047', '#8e24aa', '#fb8c00', '#00897b', '#d81b60', '#6d4c41']

/** The same color for the same person on every screen. */
const colorOf = (id: string) => COLORS[Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0) % COLORS.length]

/** Announces who this tab is and what it selects, and frames what the others select. */
/** Reports the people at the workpiece, and how many clients announce themselves there, own one included. */
export const startPresence = (graph: Graph, session: CollabSession, onPeople: (people: Person[], clients: number) => void) => {
  const { awareness } = session
  const model = graph.getDataModel()
  const selectionModel = graph.getSelectionModel()
  let frames: CellHighlight[] = []
  let stopped = false

  const states = () => Array.from(awareness.getStates() as Map<number, PresenceState>)

  const sendSelection = () => {
    awareness.setLocalStateField(
      'selection',
      graph.getSelectionCells().flatMap((cell) => cell.getId() ?? [])
    )
  }

  // Frames are drawn in the view only, so they never reach the model and are never synced.
  const drawFrames = () => {
    for (const frame of frames) frame.destroy()
    frames = []
    if (stopped) return
    for (const [clientId, state] of states()) {
      if (clientId === awareness.clientID || !state.user) continue
      for (const id of state.selection ?? []) {
        const cell = model.getCell(id)
        const view = cell ? graph.view.getState(cell) : null
        if (!view) continue
        const frame = new CellHighlight(graph, colorOf(state.user.id), 3)
        frame.highlight(view)
        frames.push(frame)
      }
    }
  }

  const listPeople = () => {
    const people = new Map<string, Person>()
    for (const [clientId, { user }] of states()) {
      if (!user) continue
      const self = clientId === awareness.clientID || people.get(user.id)?.self === true
      people.set(user.id, { id: user.id, name: user.name, color: colorOf(user.id), self })
    }
    return Array.from(people.values()).sort((a, b) => Number(b.self) - Number(a.self) || a.name.localeCompare(b.name))
  }

  // Pointers move many times a second; list and frames follow only who is there and what they select.
  let shown = ''
  const onChange = () => {
    const seen = JSON.stringify(states().map(([clientId, { user, selection }]) => [clientId, user, selection]))
    if (seen === shown) return
    shown = seen
    onPeople(listPeople(), awareness.getStates().size)
    drawFrames()
  }

  // After a remote model is loaded the cells are new objects, and deleted ones lose their frame.
  // Drawn after the event: a frame adds and removes model listeners, which maxGraph runs in place.
  const redrawLater = () => queueMicrotask(drawFrames)

  awareness.on('change', onChange)
  const stopCursors = startCursors(graph, awareness, colorOf)
  selectionModel.addListener(InternalEvent.CHANGE, sendSelection)
  model.addListener(InternalEvent.CHANGE, redrawLater)

  // The name comes from the token; without it the others just do not see this tab.
  void authService
    .getMe()
    .then(({ data }) => {
      if (stopped) return
      const claims = data as TokenClaims & { name?: string }
      const id = String(claims.id)
      awareness.setLocalState({ user: { id, name: claims.name || claims.username || `Person ${id}` } })
      sendSelection()
    })
    .catch(() => undefined)

  return () => {
    stopped = true
    stopCursors()
    awareness.off('change', onChange)
    selectionModel.removeListener(sendSelection)
    model.removeListener(redrawLater)
    awareness.setLocalState(null)
    for (const frame of frames) frame.destroy()
    frames = []
    onPeople([], 0)
  }
}
