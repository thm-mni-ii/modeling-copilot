import type { Graph } from '@maxgraph/core'
import { exportModelAsXml, importModelFromXml } from '@/utils/modelPersistence'
import type { Session } from '@/collab/connection/collabKitV1'
import { watchGraphChanges } from './graphChanges'
import { joinModel, splitModel, type SharedCell } from './modelCells'

/** Keeps the model in the units of the session one cell per key, so edits on different cells merge. */
export const bindGraph = (graph: Graph, session: Session<SharedCell>, log: (text: string) => void) => {
  const model = graph.getDataModel()
  let stopRemote: (() => void) | null = null
  let ready = false
  let applyingRemote = false
  let stopped = false

  const known = () => new Map(session.units.entries())

  // Cells created in this session get IDs no one else creates; maxGraph's counter follows only numeric IDs.
  model.prefix = `${session.clientId}-`

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

  // Compared with the shared cells, so only what differs goes out, all in one update.
  const push = () => {
    const shared = known()
    const cells = splitModel(exportModelAsXml(graph, false), shared)
    const removed = Array.from(shared.keys()).filter((id) => !cells.has(id))
    const changed = Array.from(cells).filter(([id, cell]) => {
      const before = shared.get(id)
      return !before || before.xml !== cell.xml || before.index !== cell.index
    })
    if (changed.length === 0 && removed.length === 0) return
    session.units.update({ set: Object.fromEntries(changed), delete: removed })
    log(`${session.status === 'connected' ? 'sent' : 'kept for connect ·'} ${changed.length} of ${cells.size} cells · ${removed.length} removed`)
  }

  // A remote model is imported under applyingRemote, so its change is not sent back.
  // Without edit units.update throws, so a reader sends nothing.
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

  // Nothing goes out before the state of collab-kit is in; the first one in fills an empty workpiece.
  void session.synced.then(
    () => {
      if (stopped) return
      const cells = known()
      if (cells.size > 0) applyRemote(`received model · ${cells.size} cells`)
      else if (session.mayWrite) push()
      stopRemote = session.units.onChange((keys, remote) => {
        if (remote) applyRemote(`received ${keys.length} of ${session.units.entries().length} cells`)
      })
      ready = true
    },
    () => undefined
  )

  return () => {
    stopped = true
    stopWatching()
    stopRightsWatch()
    stopRemote?.()
    model.prefix = ''
  }
}
