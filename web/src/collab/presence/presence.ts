import { watch } from 'vue'
import { CellHighlight, InternalEvent, type Cell, type EventObject, type Graph, type InternalMouseEvent } from '@maxgraph/core'
import { notifyWarning } from '@/composables/useNotifications'
import { isPseudonym } from '@/collab/kit/collabKit'
import { compareNames } from '@/utils/sorting'
import type { Session } from '@/collab/kit/collabKitV1'
import { announcedRights, currentShare, hostPresenting, personColors, presenting, settingsLoaded, shareSettings } from '@/collab/sharing/shareModel'
import { roomRole } from '@/collab/rooms/roomRole'
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
  /** When this client selected each cell, so the earliest selection holds the lock. */
  selectedSince?: Record<string, number>
  idle?: boolean
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

/** After this long without input a client gives up its selection, and with it the locks. */
const IDLE_MS = 90_000

const hostId = () => currentShare.value?.hostId ?? ''

/** The host's color, else what the host handed out; without the host a hash, so a person still has the same color on every screen. */
const colorOf = (id: string) => (id !== '' && id === hostId() ? HOST_COLOR : personColors.value[id] ?? PALETTE[Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0) % PALETTE.length])

/** The color worn by the fewest of those present; the first on a tie, so the choice is always the same. */
const leastUsed = (assigned: Record<string, string>, present: Set<string>) => {
  const counts = new Map(PALETTE.map((color) => [color, 0]))
  for (const [id, color] of Object.entries(assigned)) if (present.has(id)) counts.set(color, (counts.get(color) ?? 0) + 1)
  return PALETTE.reduce((best, color) => ((counts.get(color) ?? 0) < (counts.get(best) ?? 0) ? color : best))
}

/** Ob der Raum zuletzt als anonym angekündigt war; null, bis der Host das erste Mal angekündigt hat. */
let lastAnnounced: boolean | null = null

/**
 * Der Name, wie die Oberfläche ihn zeigt. Ist der Raum anonym, erscheinen andere außer dem Host nur unter
 * Pseudonym, auch wenn collab-kit den Namen schickt: Wer überall verwalten darf (etwa ein FBS-Admin), sieht
 * dort sonst durch. Die Nummer folgt fest aus der ID, bleibt für diesen Betrachter also gleich, ist aber
 * nicht die von collab-kit. Host: seine Einstellung, maskiert bis sie geladen ist. Visitor: die letzte
 * Ankündigung des Hosts, maskiert bis die erste da ist; so blitzt kein Name auf, und ein kurz fehlender
 * Host ändert nichts. Im Gruppenraum kündigt niemand etwas an: Dort gilt, was collab-kit schickt, bei
 * anonymer Freigabe also sein Pseudonym.
 */
export const shownName = (id: string, name: string | undefined, self = false) => {
  if (isPseudonym(id)) return id
  if (roomRole.value?.kind === 'group') return name ?? `Person ${id}`
  const anonymous = currentShare.value?.privateModelId ? !settingsLoaded.value || shareSettings.anonymous : lastAnnounced ?? true
  if (anonymous && !self && id !== hostId()) return `anonymous-${1000 + ((Array.from(id).reduce((hash, char) => hash * 31 + char.charCodeAt(0), 7) >>> 0) % 9000)}`
  return name ?? `Person ${id}`
}
const nameOf = (person: { id: string; name?: string; self?: boolean }) => shownName(person.id, person.name, person.self)

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
  let badges: SVGElement[] = []
  let stopped = false

  // Cells locked for this client because another person selected them; set in onChange from the presence.
  let locked = new Set<string>()
  // Who holds a locked cell, by client ID; only the holder's frame gets the lock.
  let holderOf = new Map<string, number>()
  let selectedSince: Record<string, number> = {}

  // Whoever does nothing for a while is announced as idle: the frame stays, but the lock is released.
  let idle = false
  let lastActive = Date.now()

  const sendSelection = () => {
    const selection = graph.getSelectionCells().flatMap((cell) => cell.getId() ?? [])
    // A cell that stays selected keeps its time; only newly selected cells get the current one.
    selectedSince = Object.fromEntries(selection.map((id) => [id, selectedSince[id] ?? Date.now()]))
    session.presence.set({ selection, selectedSince, idle })
  }

  // The whole element of a cell: up to the cell right below the layer. A selected child locks and marks all of it.
  // Native: isLayer in GraphDataModel.js (node_modules/@maxgraph/core/lib/esm/view)
  const topOf = (cell: Cell) => {
    let top = cell
    for (let parent = top.getParent(); parent && !model.isLayer(parent); parent = top.getParent()) top = parent
    return top
  }

  /**
   * The cells another person holds by selecting them. Per cell the earliest selection wins, on a tie
   * the lower client ID. Read-only clients hold nothing, and nothing is locked while the host presents.
   */
  const lockedCells = () => {
    const holders = new Map<string, { since: number; clientId: number; self: boolean }>()
    if (!presenterActive(session)) {
      for (const person of session.presence.people()) {
        for (const { clientId, state } of person.clients) {
          const { selection = [], selectedSince: since = {}, readOnly, idle: away } = state as PresenceState
          if (readOnly || away) continue
          for (const id of selection) {
            const claim = { since: since[id] ?? 0, clientId, self: person.self }
            const held = holders.get(id)
            if (!held || claim.since < held.since || (claim.since === held.since && claim.clientId < held.clientId)) holders.set(id, claim)
          }
        }
      }
    }
    // A locked cell locks everything below it too, such as the attributes of an entity.
    const result = new Set<string>()
    const lockWithChildren = (cell: Cell) => {
      result.add(cell.getId() ?? '')
      for (const child of cell.getChildren()) lockWithChildren(child)
    }
    holderOf = new Map()
    for (const [id, { self, clientId }] of holders) {
      const cell = model.getCell(id)
      if (self || !cell) continue
      holderOf.set(id, clientId)
      lockWithChildren(topOf(cell))
    }
    return result
  }

  // Whether the cell, one below it or an edge at it is locked; deleting would take those along.
  const touchesLocked = (cell: Cell): boolean => locked.has(cell.getId() ?? '') || cell.getChildren().some(touchesLocked) || cell.getEdges().some((edge) => locked.has(edge.getId() ?? ''))
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

  // A small lock at the top right of the frame, in the holder's color; it goes when the lock ends.
  const drawLock = (x: number, y: number, color: string) => {
    const ns = 'http://www.w3.org/2000/svg'
    const badge = document.createElementNS(ns, 'g')
    badge.setAttribute('transform', `translate(${x} ${y})`)
    badge.setAttribute('pointer-events', 'none')
    const disc = document.createElementNS(ns, 'circle')
    disc.setAttribute('r', '9')
    disc.setAttribute('fill', color)
    const body = document.createElementNS(ns, 'rect')
    for (const [name, value] of Object.entries({ x: -4, y: -1, width: 8, height: 6, rx: 1, fill: '#fff' })) body.setAttribute(name, String(value))
    const shackle = document.createElementNS(ns, 'path')
    for (const [name, value] of Object.entries({ d: 'M-2.5 -1 V-3 a2.5 2.5 0 0 1 5 0 V-1', fill: 'none', stroke: '#fff', 'stroke-width': 1.5 })) shackle.setAttribute(name, String(value))
    badge.append(disc, body, shackle)
    graph.view.getOverlayPane().appendChild(badge)
    return badge
  }

  // Marks a whole element in the holder's color: the top cell with a thick frame and, only for the holder, the lock;
  // the cells right below it with a 2px frame and a light tint, whichever cell of it was selected.
  const drawElement = (top: Cell, held: boolean, color: string) => {
    const frame = (cell: Cell, width: number, tinted: boolean) => {
      const view = graph.view.getState(cell)
      if (!view) return
      if (!tinted) {
        const highlight = new CellHighlight(graph, color, width)
        // No gap to the cell, so the frame covers its black border instead of showing it through.
        // Native: spacing in CellHighlight.js (default 2).
        highlight.spacing = 0
        highlight.highlight(view)
        frames.push(highlight)
        return
      }
      // The highlight keeps a gap to the cell and never paints a fill, so two neighbors show two lines.
      // A plain rectangle on the exact bounds draws one shared line and the tint; clicks pass through it.
      const box = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
      for (const [name, value] of Object.entries({ x: view.x, y: view.y, width: view.width, height: view.height, fill: color, 'fill-opacity': 0.1, stroke: color, 'stroke-width': width, 'pointer-events': 'none' })) box.setAttribute(name, String(value))
      graph.view.getOverlayPane().appendChild(box)
      badges.push(box)
    }
    frame(top, 3, false)
    // Only the level right below the top: an entity holds a dashed section that holds the attributes, and
    // framing both would lay two tints and two lines on top of each other.
    // An empty list (a swimlane such as the attributes of an entity) stays unmarked: nothing in it belongs to the element yet.
    for (const child of top.getChildren()) if (child.getChildCount() > 0 || !graph.isSwimlane(child)) frame(child, 2, true)
    const view = graph.view.getState(top)
    if (held && view) badges.push(drawLock(view.x + view.width, view.y, color))
  }

  // A small disc with a letter in a person's color; the others who selected the element sit in a row at its top left.
  const drawMark = (x: number, y: number, color: string, text: string) => {
    const ns = 'http://www.w3.org/2000/svg'
    const badge = document.createElementNS(ns, 'g')
    badge.setAttribute('transform', `translate(${x} ${y})`)
    badge.setAttribute('pointer-events', 'none')
    const disc = document.createElementNS(ns, 'circle')
    disc.setAttribute('r', '9')
    disc.setAttribute('fill', color)
    const letter = document.createElementNS(ns, 'text')
    for (const [name, value] of Object.entries({ 'text-anchor': 'middle', 'dominant-baseline': 'central', 'font-size': 10, 'font-weight': 500, fill: '#fff' })) letter.setAttribute(name, String(value))
    letter.textContent = text
    badge.append(disc, letter)
    graph.view.getOverlayPane().appendChild(badge)
    badges.push(badge)
  }

  type Claim = { person: { id: string; name?: string }; held: boolean; since: number; clientId: number }

  // Frames are drawn in the view only, so they never reach the model and are never synced.
  const drawFrames = () => {
    for (const frame of frames) frame.destroy()
    for (const badge of badges) badge.remove()
    frames = []
    badges = []
    if (stopped) return
    // Per element everyone who selected it, one claim per person; held if any of their cells is held.
    const claims = new Map<Cell, Map<string, Claim>>()
    for (const person of session.presence.people()) {
      if (!shows(session, person.id)) continue
      for (const { clientId, state } of person.clients) {
        // The presenting host sees the own selection framed too, as the others see it.
        if (clientId === session.clientId && !presenting.value) continue
        const { selection = [], selectedSince: since = {} } = state as PresenceState
        for (const id of selection) {
          const cell = model.getCell(id)
          if (!cell) continue
          const top = topOf(cell)
          const claim: Claim = { person, held: holderOf.get(id) === clientId, since: since[id] ?? 0, clientId }
          const byPerson = claims.get(top) ?? new Map<string, Claim>()
          const known = byPerson.get(person.id)
          byPerson.set(person.id, known ? { ...known, held: known.held || claim.held, since: Math.min(known.since, claim.since), clientId: Math.min(known.clientId, claim.clientId) } : claim)
          claims.set(top, byPerson)
        }
      }
    }
    for (const [top, byPerson] of claims) {
      // The frame and the lock belong to the holder, else to the earliest; the others show as marks at the top left.
      const [main, ...others] = [...byPerson.values()].sort((a, b) => Number(b.held) - Number(a.held) || a.since - b.since || a.clientId - b.clientId)
      drawElement(top, main.held, colorOf(main.person.id))
      const view = graph.view.getState(top)
      if (!view) continue
      others.slice(0, 2).forEach((other, at) => drawMark(view.x + at * 17, view.y, colorOf(other.person.id), Array.from(nameOf(other.person))[0]?.toUpperCase() ?? '?'))
      if (others.length > 2) drawMark(view.x + 2 * 17, view.y, '#888780', `+${others.length - 2}`)
    }
  }

  // Pointers move many times a second; list and frames follow only who is there and what they select.
  let shown = ''
  const onChange = () => {
    const people = session.presence.people()
    hostPresenting.value = presenterActive(session)
    announcedRights.value = announcedBy(session)
    if (announcedRights.value) lastAnnounced = announcedRights.value.anonymous
    if (currentShare.value?.privateModelId) assignColors(people)
    else personColors.value = colorsBy(session) ?? {}
    const seen = JSON.stringify([people.map(({ id, name, clients }) => [id, name, clients.map(({ clientId, state }) => [clientId, (state as PresenceState).selection, (state as PresenceState).selectedSince, (state as PresenceState).idle, (state as PresenceState).readOnly, (state as PresenceState).presenting, (state as PresenceState).visitors])]), personColors.value])
    if (seen === shown) return
    shown = seen
    locked = lockedCells()
    const list = people.map((person) => ({
      id: person.id,
      name: nameOf(person),
      color: colorOf(person.id),
      self: person.self,
      readOnly: person.clients.some(({ state }) => (state as PresenceState).readOnly === true),
      tabs: person.clients.length
    }))
    list.sort((a, b) => Number(b.self) - Number(a.self) || compareNames(a.name, b.name))
    onPeople(
      list,
      people.reduce((count, person) => count + person.clients.length, 0)
    )
    drawFrames()
  }

  // After a remote model is loaded the cells are new objects, and deleted ones lose their frame.
  // Drawn after the event: a frame adds and removes model listeners, which maxGraph runs in place.
  const redrawLater = () => queueMicrotask(drawFrames)

  // Locking by presence: an element another person selected cannot be moved, resized, edited or
  // deleted, nor can its children. Edges that end at it still follow when it is moved.
  // Native hooks: isCellLocked/isCellDeletable in CellsMixin.js, isCellEditable in EditingMixin.js
  // (node_modules/@maxgraph/core/lib/esm/view/mixin). Wrapped on the instance, restored on stop.
  const { isCellLocked, isCellEditable, isCellDeletable } = graph
  graph.isCellLocked = (cell) => locked.has(cell.getId() ?? '') || isCellLocked.call(graph, cell)
  graph.isCellEditable = (cell) => !locked.has(cell.getId() ?? '') && isCellEditable.call(graph, cell)
  graph.isCellDeletable = (cell) => !touchesLocked(cell) && isCellDeletable.call(graph, cell)

  // Tells who holds the element when someone tries to change it; at most once every few seconds.
  // Only attempts count (drag, double click, delete), because maxGraph also asks the hooks above while drawing.
  let lastWarned = 0
  const warnLocked = (cell: Cell) => {
    if (Date.now() - lastWarned < 3000) return
    lastWarned = Date.now()
    const holder = [...holderOf].find(([id]) => topOf(model.getCell(id) ?? cell) === topOf(cell))
    const person = holder && session.presence.people().find(({ clients }) => clients.some(({ clientId }) => clientId === holder[1]))
    notifyWarning(person ? `This element is locked. ${nameOf(person)} is editing it.` : 'This element is locked. Someone else is editing it.')
  }
  // Native: getDeletableCells in CellsMixin.js is called only when deleting.
  const { getDeletableCells } = graph
  graph.getDeletableCells = (cells) => {
    const blocked = cells.find(touchesLocked)
    if (blocked) warnLocked(blocked)
    return getDeletableCells.call(graph, cells)
  }
  // A drag that starts on a locked element; a plain click only selects and stays quiet.
  let pressed: { cell: Cell; x: number; y: number } | null = null
  const lockWatcher = {
    mouseDown: (_sender: unknown, me: InternalMouseEvent) => {
      const cell = me.getCell()
      pressed = cell && locked.has(cell.getId() ?? '') ? { cell, x: me.getGraphX(), y: me.getGraphY() } : null
    },
    mouseMove: (_sender: unknown, me: InternalMouseEvent) => {
      if (!pressed || Math.hypot(me.getGraphX() - pressed.x, me.getGraphY() - pressed.y) <= graph.getEventTolerance()) return
      warnLocked(pressed.cell)
      pressed = null
    },
    mouseUp: () => {
      pressed = null
    }
  }
  graph.addMouseListener(lockWatcher)
  const onDoubleClick = (_sender: unknown, evt: EventObject) => {
    const cell = evt.getProperty('cell') as Cell | null
    if (cell && locked.has(cell.getId() ?? '')) warnLocked(cell)
  }
  graph.addListener(InternalEvent.DOUBLE_CLICK, onDoubleClick)

  const stopListening = session.presence.onChange(onChange)
  const stopCursors = startCursors(graph, session, colorOf, nameOf, (id) => shows(session, id))
  selectionModel.addListener(InternalEvent.CHANGE, sendSelection)
  model.addListener(InternalEvent.CHANGE, redrawLater)
  // The lock sits in absolute view coordinates, so it follows zoom and scrolling.
  graph.view.addListener(InternalEvent.SCALE_AND_TRANSLATE, redrawLater)
  graph.view.addListener(InternalEvent.SCALE, redrawLater)
  graph.view.addListener(InternalEvent.TRANSLATE, redrawLater)
  sendSelection()
  const onActivity = () => {
    lastActive = Date.now()
    if (!idle) return
    idle = false
    sendSelection()
  }
  const idleCheck = setInterval(() => {
    if (idle || Date.now() - lastActive < IDLE_MS) return
    idle = true
    sendSelection()
  }, 5000)
  const activityEvents = ['pointerdown', 'keydown', 'wheel'] as const
  for (const type of activityEvents) window.addEventListener(type, onActivity, { passive: true })
  // The rights are known once connected; the first answer is no change, so synced tells it.
  const stopRightsWatch = session.on('rightsChanged', sendRights)
  void session.synced.then(sendRights, () => undefined)
  sendHostState()
  const stopPresentingWatch = watch([presenting, settingsLoaded, () => ({ ...shareSettings })], sendHostState)
  const stopAnonymityWatch = session.on('anonymityChanged', sendHostState)

  return () => {
    stopped = true
    clearInterval(idleCheck)
    for (const type of activityEvents) window.removeEventListener(type, onActivity)
    graph.isCellLocked = isCellLocked
    graph.isCellEditable = isCellEditable
    graph.isCellDeletable = isCellDeletable
    graph.getDeletableCells = getDeletableCells
    graph.removeMouseListener(lockWatcher)
    graph.removeListener(onDoubleClick)
    locked = new Set()
    stopCursors()
    stopListening()
    stopRightsWatch()
    stopPresentingWatch()
    stopAnonymityWatch()
    announcedRights.value = null
    lastAnnounced = null
    personColors.value = {}
    hostPresenting.value = false
    selectionModel.removeListener(sendSelection)
    model.removeListener(redrawLater)
    graph.view.removeListener(redrawLater)
    for (const badge of badges) badge.remove()
    badges = []
    for (const frame of frames) frame.destroy()
    frames = []
    onPeople([], 0)
  }
}
