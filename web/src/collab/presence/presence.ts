import { watch } from 'vue'
import { CellHighlight, InternalEvent, type Graph } from '@maxgraph/core'
import { isPseudonym } from '@/collab/kit/collabKit'
import type { Session } from '@/collab/kit/collabKitV1'
import { announcedRights, currentShare, hostPresenting, personColors, presenting, settingsLoaded, shareSettings } from '@/collab/sharing/shareModel'
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
  presenting?: boolean
  visitors?: { edit: boolean; comment: boolean; anonymous: boolean }
  colors?: Record<string, string>
}

/** The host is the only one in red, so the presenter is known at a glance. */
const HOST_COLOR = '#cf5c58'
// Sixteen colors measured to tell apart well (CIEDE2000, also for red-green color blindness), none of them red, which is the host's.
// The first ones lie farthest apart, so the first people in a room get the most distinct colors.
const PALETTE = ['#c29ed7', '#214b25', '#ee9813', '#0e26dc', '#12c19f', '#652f55', '#715c00', '#6e83b7', '#1d8a85', '#8f4ef1', '#6f5d8d', '#f657f2', '#194b78', '#8605a8', '#41a8ba', '#2da0fb']

const hostId = () => currentShare.value?.hostId ?? ''

/** The host's color, else what the host handed out; without the host a hash, so a person still has the same color on every screen. */
const colorOf = (id: string) => (id !== '' && id === hostId() ? HOST_COLOR : personColors.value[id] ?? PALETTE[Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0) % PALETTE.length])

/** The color worn by the fewest of those present; the first on a tie, so the choice is always the same. */
const leastUsed = (assigned: Record<string, string>, present: Set<string>) => {
  const counts = new Map(PALETTE.map((color) => [color, 0]))
  for (const [id, color] of Object.entries(assigned)) if (present.has(id)) counts.set(color, (counts.get(color) ?? 0) + 1)
  return PALETTE.reduce((best, color) => ((counts.get(color) ?? 0) < (counts.get(best) ?? 0) ? color : best))
}

/** The name collab-kit has from the token; a pseudonym shows as it is, a token without a name shows the ID. */
const nameOf = (person: { id: string; name?: string }) => person.name ?? (isPseudonym(person.id) ? person.id : `Person ${person.id}`)

/** Whether the host presents. */
const presenterActive = (session: Session) => session.presence.people().some((person) => person.id === hostId() && person.clients.some(({ state }) => (state as PresenceState).presenting === true))

/** What the host announced for the visitors; none while the host is not there or has not read the settings yet. */
const announcedBy = (session: Session) => {
  const host = session.presence.people().find((person) => person.id === hostId())
  return host?.clients.map(({ state }) => (state as PresenceState).visitors).find((visitors) => visitors !== undefined) ?? null
}

/** The colors the host handed out; none while the host is not there. */
const colorsBy = (session: Session) => {
  const host = session.presence.people().find((person) => person.id === hostId())
  return host?.clients.map(({ state }) => (state as PresenceState).colors).find((colors) => colors !== undefined) ?? null
}

/** Whether the cursor and selection of a person show: all do, until the host presents, then only the host's. */
const shows = (session: Session, id: string) => !presenterActive(session) || id === hostId()

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
  // Only the host presents and announces what visitors may; a new client after a change of anonymity announces it again.
  // The settings go out once they are read and set, so the visitors see them at once, with no wait for a reconnect.
  const sendHostState = () => {
    if (stopped || !currentShare.value?.privateModelId) return
    const { edit, comment, anonymous } = shareSettings
    session.presence.set({ presenting: presenting.value, colors: personColors.value, ...(settingsLoaded.value ? { visitors: { edit, comment, anonymous } } : {}) })
  }

  // Only the host hands out colors; each newcomer gets the one worn by the fewest of those present.
  const assignColors = (people: { id: string }[]) => {
    if (!currentShare.value?.privateModelId) return
    const present = new Set(people.map(({ id }) => id))
    const next = { ...personColors.value }
    let changed = false
    for (const { id } of people) {
      if (id === hostId() || next[id]) continue
      next[id] = leastUsed(next, present)
      changed = true
    }
    if (!changed) return
    personColors.value = next
    sendHostState()
  }

  // Frames are drawn in the view only, so they never reach the model and are never synced.
  const drawFrames = () => {
    for (const frame of frames) frame.destroy()
    frames = []
    if (stopped) return
    for (const person of session.presence.people()) {
      if (!shows(session, person.id)) continue
      for (const { clientId, state } of person.clients) {
        // The presenting host sees the own selection framed too, as the others see it.
        if (clientId === session.clientId && !presenting.value) continue
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
    hostPresenting.value = presenterActive(session)
    announcedRights.value = announcedBy(session)
    if (currentShare.value?.privateModelId) assignColors(people)
    else personColors.value = colorsBy(session) ?? {}
    const seen = JSON.stringify([people.map(({ id, name, clients }) => [id, name, clients.map(({ clientId, state }) => [clientId, (state as PresenceState).selection, (state as PresenceState).readOnly, (state as PresenceState).presenting, (state as PresenceState).visitors])]), personColors.value])
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
  const stopCursors = startCursors(graph, session, colorOf, nameOf, (id) => shows(session, id))
  selectionModel.addListener(InternalEvent.CHANGE, sendSelection)
  model.addListener(InternalEvent.CHANGE, redrawLater)
  sendSelection()
  // The rights are known once connected; the first answer is no change, so synced tells it.
  const stopRightsWatch = session.on('rightsChanged', sendRights)
  void session.synced.then(sendRights, () => undefined)
  sendHostState()
  const stopPresentingWatch = watch([presenting, settingsLoaded, () => ({ ...shareSettings })], sendHostState)
  const stopAnonymityWatch = session.on('anonymityChanged', sendHostState)

  return () => {
    stopped = true
    stopCursors()
    stopListening()
    stopRightsWatch()
    stopPresentingWatch()
    stopAnonymityWatch()
    announcedRights.value = null
    personColors.value = {}
    hostPresenting.value = false
    selectionModel.removeListener(sendSelection)
    model.removeListener(redrawLater)
    for (const frame of frames) frame.destroy()
    frames = []
    onPeople([], 0)
  }
}
