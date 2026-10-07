import type { Graph } from '@maxgraph/core'
import type { YMapEvent } from 'yjs'
import { exportModelAsXml, importModelFromXml } from '@/utils/modelPersistence'
import { getRights } from './collabApi'
import type { CollabSession } from './collabSession'
import { watchGraphChanges } from './graphChanges'
import { joinModel, splitModel, type SharedCell } from './modelCells'

/** Keeps the model in the Yjs document one cell per entry, so edits on different cells merge. */
export const bindGraph = (graph: Graph, session: CollabSession, mayWrite: boolean, log: (text: string) => void) => {
  const shared = session.doc.getMap<SharedCell>('cells')
  const model = graph.getDataModel()
  let canWrite = mayWrite
  let ready = false
  let applyingRemote = false
  let stopped = false

  // Cells created in this session get IDs no one else creates; maxGraph's counter follows only numeric IDs.
  model.prefix = `${session.doc.clientID}-`

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
    session.doc.transact(() => {
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
      if (canWrite) push()
      return
    }
    setTimeout(() => {
      if (!stopped) applyRemote('model replaced locally · shared state restored')
    })
  })
  // A reader that kept sending would be closed with 1008 on every reconnect, so the rights are asked again.
  const stopRightsWatch = session.onRightsChanged(() => {
    getRights({ kind: 'workpiece', id: session.workpieceId })
      .then(({ data }) => {
        if (stopped) return
        canWrite = data.includes('edit')
        log(`rights changed · ${canWrite ? 'may edit' : 'read only'}`)
      })
      .catch(() => log('rights changed · could not ask collab-kit again'))
  })
  const onRemote = (event: YMapEvent<SharedCell>) => {
    if (!event.transaction.local) applyRemote(`received ${event.keysChanged.size} of ${shared.size} cells`)
  }

  // Nothing goes out before the state of collab-kit is in; the first one in fills an empty workpiece.
  void session.synced.then(() => {
    if (stopped) return
    if (shared.size > 0) applyRemote(`received model · ${shared.size} cells`)
    else if (canWrite) push()
    shared.observe(onRemote)
    ready = true
  })

  return () => {
    stopped = true
    stopWatching()
    stopRightsWatch()
    if (ready) shared.unobserve(onRemote)
    model.prefix = ''
  }
}
