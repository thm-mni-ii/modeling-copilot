import { InternalEvent, type Cell, type Graph } from '@maxgraph/core'
import { notifyWarning } from '@/composables/useNotifications'
import { exportModelAsXml, importModelFromXml } from '@/utils/modelPersistence'
import type { Session } from '@/collab/connection/collabKitV1'
import { applyCells, cellsOfUndoneEdit, type HeldText } from './applyCells'
import { watchGraphChanges } from './graphChanges'
import { joinModel, splitModel, type SharedCell } from './modelCells'
import { lockGraph } from './readOnly'
import { sharedHistory } from './sharedHistory'

/** Keeps the model in the units of the session one cell per key, so edits on different cells merge. */
export const bindGraph = (graph: Graph, session: Session<SharedCell>, log: (text: string) => void) => {
  const model = graph.getDataModel()
  let stopRemote: (() => void) | null = null
  let ready = false
  let applyingRemote = false
  let stopped = false
  let unlock: (() => void) | null = null
  let warned = false
  // Text another changed while it is edited here, with the text before; the own text wins.
  const heldBack = new Map<Cell, unknown>()

  const known = () => new Map(session.units.entries())

  // Cells created in this session get IDs no one else creates; maxGraph's counter follows only numeric IDs.
  // A new client comes with a change of the own anonymity, so new cells never tie the open and the anonymous one.
  const takePrefix = () => {
    model.prefix = `${session.clientId}-`
  }
  takePrefix()

  const applyRemote = (what: string) => {
    const xml = joinModel(known())
    if (!xml) return
    // Loading replaces every cell, so the selection is taken over by ID to what still exists.
    const selected = graph.getSelectionCells().flatMap((cell) => cell.getId() ?? [])
    applyingRemote = true
    try {
      importModelFromXml(graph, xml)
      graph.setSelectionCells(selected.flatMap((id) => model.getCell(id) ?? []))
    } finally {
      applyingRemote = false
    }
    log(what)
  }

  // Only the cells a change touched, so the selection and an edit in progress stay; what it cannot read loads the whole model.
  const applyChanged = (keys: string[], what: string) => {
    applyingRemote = true
    let held: HeldText | null
    try {
      held = applyCells(graph, keys, known())
    } catch {
      applyingRemote = false
      applyRemote(`${what} · full reload`)
      return
    }
    applyingRemote = false
    if (held && !heldBack.has(held.cell)) {
      heldBack.set(held.cell, held.before)
      notifyWarning('Someone else changed this text while you edit it. Yours replaces it when you finish; Esc keeps theirs.')
    }
    log(what)
  }

  // Held-back text whose edit has ended: left as it was, theirs comes in; changed, it went out as own text.
  const takeOverHeld = () => {
    if (stopped) return
    const ids: string[] = []
    for (const [cell, before] of heldBack) {
      if (graph.isEditing(cell)) continue
      heldBack.delete(cell)
      const id = cell.getId()
      if (id && model.getCell(id) === cell && cell.value === before) ids.push(id)
    }
    if (ids.length > 0) applyChanged(ids, `took over ${ids.length} text changed meanwhile`)
  }
  // Fired once the editor wrote its text, if any; it may come from within a model change, so taken over after it.
  const onEditingStopped = () => setTimeout(takeOverHeld)
  graph.addListener(InternalEvent.EDITING_STOPPED, onEditingStopped)

  // Undo and redo take back only own steps; what comes back is taken in like a change from outside.
  const step = (back: boolean) => {
    if (stopped || !session.mayWrite) return
    if (back) session.units.undo()
    else session.units.redo()
    showHistory()
  }
  // Read after update, undo and redo; within onChange the library still tells the state before.
  // A reader gets it too, with nothing to undo, so the editor's own history stays out.
  const showHistory = () => {
    if (stopped) return
    const mayWrite = session.mayWrite
    sharedHistory.value = { undo: () => step(true), redo: () => step(false), canUndo: mayWrite && session.units.canUndo(), canRedo: mayWrite && session.units.canRedo() }
  }

  // Compared with the shared cells, so only what differs goes out, all in one update and one step to undo.
  // Held-back text stays out while unchanged, as it would overwrite the newer one of another.
  const push = (undoable = true) => {
    for (const [cell, before] of heldBack) if (cell.value !== before) heldBack.delete(cell)
    const holding = new Set([...heldBack.keys()].flatMap((cell) => cell.getId() ?? []))
    const shared = known()
    const cells = splitModel(exportModelAsXml(graph, false), shared)
    const removed = Array.from(shared.keys()).filter((id) => !cells.has(id))
    const changed = Array.from(cells).filter(([id, cell]) => {
      const before = shared.get(id)
      return !holding.has(id) && (!before || before.xml !== cell.xml || before.index !== cell.index)
    })
    if (changed.length === 0 && removed.length === 0) return
    session.units.update({ set: Object.fromEntries(changed), delete: removed }, { undoable })
    log(`${session.status === 'connected' ? 'sent' : 'kept for connect ·'} ${changed.length} of ${cells.size} cells · ${removed.length} removed`)
    showHistory()
  }

  // A reader works on a locked graph; unlocked again, the warning comes again with the next lock.
  const setReadOnly = (readOnly: boolean) => {
    if (readOnly && !unlock) unlock = lockGraph(graph)
    if (!readOnly && unlock) {
      unlock()
      unlock = null
      warned = false
    }
  }

  // A remote model is imported under applyingRemote, so its change is not sent back.
  // The Copilot swaps the whole model when it loads one, restores a version or takes a draft back;
  // that is no edit to share, so the shared state is shown again once the Copilot is done with it.
  // A reader's edit passes the lock only through the Copilot's own buttons, and is taken back the same way.
  const stopWatching = watchGraphChanges(graph, (_cellCount, replaced, edit) => {
    if (!ready || applyingRemote) return
    // The Copilot's undo took back a change of another; nothing goes out, the shared state of those cells comes back.
    const undone = cellsOfUndoneEdit(edit)
    if (undone) {
      setTimeout(() => {
        if (!stopped) applyChanged(undone, 'undo of a change from outside · shared state restored')
      })
      return
    }
    if (!replaced && session.mayWrite) {
      push()
      // An edit may end without telling; the next change of its own then lets held-back text in.
      if (heldBack.size > 0) setTimeout(takeOverHeld)
      return
    }
    if (!replaced && !warned) {
      warned = true
      notifyWarning('You may only view this model.')
    }
    setTimeout(() => {
      if (!stopped) applyRemote(replaced ? 'model replaced locally · shared state restored' : 'read only · own change taken back')
    })
  })
  // The library asks for the rights again on every reconnect and keeps mayWrite up to date.
  const stopRightsWatch = session.on('rightsChanged', (mayWrite) => {
    log(`rights changed · ${mayWrite ? 'may edit' : 'read only'}`)
    if (stopped) return
    setReadOnly(!mayWrite)
    showHistory()
  })
  // Told once the library made the new client, so its ID is already the new one.
  const stopAnonymityWatch = session.on('anonymityChanged', (anonymous) => {
    log(`anonymity changed · ${anonymous ? 'anonymous' : 'by name'} · new cells ${session.clientId}-…`)
    if (!stopped) takePrefix()
  })

  // From the start, so the editor's own history is out even before the state of collab-kit is in.
  showHistory()

  // Nothing goes out before the state of collab-kit is in; the first one in fills an empty workpiece.
  void session.synced.then(
    () => {
      if (stopped) return
      // The rights came before the connection; they change later only with rightsChanged.
      setReadOnly(!session.mayWrite)
      const cells = known()
      // A whole state is no step to undo, else an undo would empty the workpiece again.
      if (cells.size > 0) applyRemote(`received model · ${cells.size} cells`)
      else if (session.mayWrite) push(false)
      stopRemote = session.units.onChange((keys, remote) => {
        if (!remote) return
        applyChanged(keys, `received ${keys.length} of ${session.units.entries().length} cells`)
        if (heldBack.size > 0) takeOverHeld()
      })
      ready = true
      showHistory()
    },
    () => undefined
  )

  return () => {
    stopped = true
    stopWatching()
    graph.removeListener(onEditingStopped)
    stopRightsWatch()
    stopAnonymityWatch()
    stopRemote?.()
    unlock?.()
    sharedHistory.value = null
    model.prefix = ''
  }
}
