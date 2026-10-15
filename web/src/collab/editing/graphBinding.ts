import type { Graph } from '@maxgraph/core'
import type { Doc, YMapEvent } from 'yjs'
import { exportModelAsXml, importModelFromXml } from '@/utils/modelPersistence'
import { CELLS_MAP } from '@/collab/connection/collabApi'
import type { Session } from '@/collab/connection/collabKitV1'
import { watchGraphChanges } from './graphChanges'
import { joinModel, splitModel, type SharedCell } from './modelCells'

/** Keeps the model in the Yjs document one cell per entry, so edits on different cells merge. */
export const bindGraph = (graph: Graph, session: Session<SharedCell>, log: (text: string) => void) => {
  // The library's own Yjs; import type keeps a second one out of the build.
  const doc = session.yjs.doc as Doc
  const shared = doc.getMap<SharedCell>(CELLS_MAP)
  const model = graph.getDataModel()
  let ready = false
  let applyingRemote = false
  let stopped = false

  // Cells created in this session get IDs no one else creates; maxGraph's counter follows only numeric IDs.
  model.prefix = `${session.clientId}-`

  const applyRemote = (what: string) => {
    const xml = joinModel(shared)
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

  // Compared with the shared cells, so only what differs goes out, all in one update.
  const push = () => {
    const cells = splitModel(exportModelAsXml(graph, false))
    const removed = Array.from(shared.keys()).filter((id) => !cells.has(id))
    const changed = Array.from(cells).filter(([id, cell]) => {
      const known = shared.get(id)
      return !known || known.xml !== cell.xml || known.index !== cell.index
    })
    if (changed.length === 0 && removed.length === 0) return
    doc.transact(() => {
      for (const id of removed) shared.delete(id)
      for (const [id, cell] of changed) shared.set(id, cell)
    })
    log(`sent ${changed.length} of ${cells.size} cells · ${removed.length} removed`)
  }

  // A remote model is imported under applyingRemote, so its change is not sent back.
  // Without edit collab-kit would close the connection for every change sent.
  // The Copilot swaps the whole model when it loads one, restores a version or takes a draft back;
  // that is no edit to share, so the shared state is shown again once the Copilot is done with it.
  const stopWatching = watchGraphChanges(graph, (_cellCount, replaced) => {
    if (!ready || applyingRemote) return
    if (!replaced) {
      if (session.mayWrite) push()
      return
    }
    setTimeout(() => {
      if (!stopped) applyRemote('model replaced locally · shared state restored')
    })
  })
  // The library asks for the rights again on every reconnect and keeps mayWrite up to date.
  const stopRightsWatch = session.on('rightsChanged', (mayWrite) => log(`rights changed · ${mayWrite ? 'may edit' : 'read only'}`))
  const onRemote = (event: YMapEvent<SharedCell>) => {
    if (!event.transaction.local) applyRemote(`received ${event.keysChanged.size} of ${shared.size} cells`)
  }

  // Nothing goes out before the state of collab-kit is in; the first one in fills an empty workpiece.
  void session.synced.then(
    () => {
      if (stopped) return
      if (shared.size > 0) applyRemote(`received model · ${shared.size} cells`)
      else if (session.mayWrite) push()
      shared.observe(onRemote)
      ready = true
    },
    () => undefined
  )

  return () => {
    stopped = true
    stopWatching()
    stopRightsWatch()
    if (ready) shared.unobserve(onRemote)
    model.prefix = ''
  }
}
