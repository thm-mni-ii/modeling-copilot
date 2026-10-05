import type { Graph } from '@maxgraph/core'
import type { YMapEvent } from 'yjs'
import { exportModelAsXml, importModelFromXml } from '@/utils/modelPersistence'
import type { CollabSession } from './collabSession'
import { countCells, watchGraphChanges } from './graphChanges'

/** Keeps the whole model XML in the Yjs document: last write wins, enough for a first test. */
export const bindGraph = (graph: Graph, session: CollabSession, canWrite: boolean, log: (text: string) => void) => {
  const shared = session.doc.getMap<string>('model')
  let ready = false
  let applyingRemote = false
  let stopped = false

  const applyRemote = () => {
    const xml = shared.get('xml')
    if (!xml) return
    applyingRemote = true
    try {
      importModelFromXml(graph, xml)
    } finally {
      applyingRemote = false
    }
    log(`received model · ${countCells(graph)} cells`)
  }

  const push = () => {
    const xml = exportModelAsXml(graph, false)
    if (xml === shared.get('xml')) return
    shared.set('xml', xml)
    log(`sent model · ${countCells(graph)} cells`)
  }

  // A remote model is imported under applyingRemote, so its change is not sent back.
  // Without edit collab-kit would close the connection for every change sent.
  const stopWatching = watchGraphChanges(graph, () => {
    if (ready && canWrite && !applyingRemote) push()
  })
  const onRemote = (event: YMapEvent<string>) => {
    if (!event.transaction.local) applyRemote()
  }

  // Nothing goes out before the state of collab-kit is in; the first one in fills an empty workpiece.
  void session.synced.then(() => {
    if (stopped) return
    if (shared.has('xml')) applyRemote()
    else if (canWrite) push()
    shared.observe(onRemote)
    ready = true
  })

  return () => {
    stopped = true
    stopWatching()
    if (ready) shared.unobserve(onRemote)
  }
}
