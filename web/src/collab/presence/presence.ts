import { CellHighlight, InternalEvent, type Graph } from '@maxgraph/core'
import type { Session } from '@/collab/connection/collabKitV1'
import { startCursors } from './cursors'

/** One person at the workpiece, once however many tabs they have open. */
export interface Person {
  id: string
  name: string
  color: string
  self: boolean
  /** Whether a session of the person may only read; each announces it, CK tells no one the rights of others. */
  readOnly: boolean
  /** How many sessions the person has open, such as tabs. */
  tabs: number
}

/** What every client announces of itself besides the person the library puts in. */
interface PresenceState {
  selection?: string[]
  readOnly?: boolean
}

const COLORS = ['#e53935', '#1e88e5', '#43a047', '#8e24aa', '#fb8c00', '#00897b', '#d81b60', '#6d4c41']

/** The same color for the same person on every screen. */
const colorOf = (id: string) => COLORS[Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0) % COLORS.length]

/** The name collab-kit has from the token; a token without one shows the ID. */
const nameOf = (person: { id: string; name?: string }) => person.name ?? `Person ${person.id}`

/**
 * Announces what this tab selects and whether it may only read, frames what the others select,
 * and reports the people at the workpiece and how many clients announce themselves there, own
 * one included.
 */
export const startPresence = (graph: Graph, session: Session, onPeople: (people: Person[], clients: number) => void) => {
  const model = graph.getDataModel()
  const selectionModel = graph.getSelectionModel()
  let frames: CellHighlight[] = []
  let stopped = false

  const sendSelection = () => {
    session.presence.set({ selection: graph.getSelectionCells().flatMap((cell) => cell.getId() ?? []) })
  }
  const sendRights = () => {
    if (!stopped) session.presence.set({ readOnly: !session.mayWrite })
  }

  // Frames are drawn in the view only, so they never reach the model and are never synced.
  const drawFrames = () => {
    for (const frame of frames) frame.destroy()
    frames = []
    if (stopped) return
    for (const person of session.presence.people()) {
      for (const { clientId, state } of person.clients) {
        if (clientId === session.clientId) continue
        for (const id of (state as PresenceState).selection ?? []) {
          const cell = model.getCell(id)
          const view = cell ? graph.view.getState(cell) : null
          if (!view) continue
          const frame = new CellHighlight(graph, colorOf(person.id), 3)
          frame.highlight(view)
          frames.push(frame)
        }
      }
    }
  }

  // Pointers move many times a second; list and frames follow only who is there and what they select.
  let shown = ''
  const onChange = () => {
    const people = session.presence.people()
    const seen = JSON.stringify(people.map(({ id, name, clients }) => [id, name, clients.map(({ clientId, state }) => [clientId, (state as PresenceState).selection, (state as PresenceState).readOnly])]))
    if (seen === shown) return
    shown = seen
    const list = people.map((person) => ({
      id: person.id,
      name: nameOf(person),
      color: colorOf(person.id),
      self: person.self,
      readOnly: person.clients.some(({ state }) => (state as PresenceState).readOnly === true),
      tabs: person.clients.length
    }))
    list.sort((a, b) => Number(b.self) - Number(a.self) || a.name.localeCompare(b.name))
    onPeople(
      list,
      people.reduce((count, person) => count + person.clients.length, 0)
    )
    drawFrames()
  }

  // After a remote model is loaded the cells are new objects, and deleted ones lose their frame.
  // Drawn after the event: a frame adds and removes model listeners, which maxGraph runs in place.
  const redrawLater = () => queueMicrotask(drawFrames)

  const stopListening = session.presence.onChange(onChange)
  const stopCursors = startCursors(graph, session, colorOf, nameOf)
  selectionModel.addListener(InternalEvent.CHANGE, sendSelection)
  model.addListener(InternalEvent.CHANGE, redrawLater)
  sendSelection()
  // The rights are known once connected; the first answer is no change, so synced tells it.
  const stopRightsWatch = session.on('rightsChanged', sendRights)
  void session.synced.then(sendRights, () => undefined)

  return () => {
    stopped = true
    stopCursors()
    stopListening()
    stopRightsWatch()
    selectionModel.removeListener(sendSelection)
    model.removeListener(redrawLater)
    for (const frame of frames) frame.destroy()
    frames = []
    onPeople([], 0)
  }
}
