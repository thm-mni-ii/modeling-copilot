import { CellHighlight, type Graph } from '@maxgraph/core'
import { notifyWarning } from '@/composables/useNotifications'
import type { Session } from '@/collab/connection/collabKitV1'

/** How long a cell whose change was lost stays framed. */
const FRAME_MS = 4000

/** Tells of every change lost at the workpiece in the log; the one who lost also gets a notice and the cell framed. */
export const showConflicts = (graph: Graph, session: Session, log: (text: string) => void) => {
  const frames = new Map<CellHighlight, ReturnType<typeof setTimeout>>()
  let stopped = false

  const unframe = (frame: CellHighlight) => {
    clearTimeout(frames.get(frame))
    frame.destroy()
    frames.delete(frame)
  }

  const frameCell = (id: string) => {
    if (stopped) return
    const cell = graph.getDataModel().getCell(id)
    const state = cell ? graph.view.getState(cell) : null
    if (!state) return
    // Dashed and outside the frame of a person who selects the cell, so it is neither taken for nor hidden by it.
    const frame = new CellHighlight(graph, '#d32f2f', 3, true)
    frame.spacing = 6
    frame.highlight(state)
    frames.set(
      frame,
      setTimeout(() => unframe(frame), FRAME_MS)
    )
  }

  const stop = session.on('conflict', ({ unit, cause, loser, winner, mine, names }) => {
    const name = (id: string) => names[id] ?? id
    log(`conflict · ${cause} · cell ${unit ?? '?'} · ${name(loser)} lost to ${name(winner)}`)
    if (!mine) return
    notifyWarning(`Your change was overwritten by ${name(winner)}`)
    // The winning value may still be on its way into the graph.
    if (unit) setTimeout(() => frameCell(unit))
  })

  return () => {
    stopped = true
    stop()
    for (const frame of [...frames.keys()]) unframe(frame)
  }
}
