import { CellHighlight, type Graph } from '@maxgraph/core'
import { notifyWarning } from '@/composables/useNotifications'
import type { Session } from '@/collab/kit/collabKitV1'
import type { Log } from '@/collab/connection/useCollabConnection'

/** How long a framed cell stays framed. */
const FRAME_MS = 4000

/**
 * Frames a cell for a while, or until taken away with ms Infinity; also the log shows its elements so. Returns what takes the frame away before,
 * or null when the cell is not shown.
 */
export const frameCell = (graph: Graph, id: string, color: string, ms = FRAME_MS) => {
  const cell = graph.getDataModel().getCell(id)
  const state = cell ? graph.view.getState(cell) : null
  if (!state) return null
  // Dashed and outside the frame of a person who selects the cell, so it is neither taken for nor hidden by it.
  const frame = new CellHighlight(graph, color, 3, true)
  frame.spacing = 6
  frame.highlight(state)
  // Ohne Zeit bleibt er, bis ihn der Aufrufer wegnimmt.
  const timer = Number.isFinite(ms) ? setTimeout(() => frame.destroy(), ms) : undefined
  return () => {
    clearTimeout(timer)
    frame.destroy()
  }
}

/** Tells of every change lost at the workpiece in the log; the one who lost also gets a notice and the cell framed. */
export const showConflicts = (graph: Graph, session: Session, log: Log) => {
  const frames = new Set<() => void>()
  let stopped = false

  const stop = session.on('conflict', ({ unit, cause, loser, winner, mine, names }) => {
    const name = (id: string) => names[id] ?? id
    log(`conflict · ${cause} · cell ${unit ?? '?'} · ${name(loser)} lost to ${name(winner)}`)
    // Das Element mit seiner Beschriftung, wie maxGraph sie zeigt; ohne eine bleibt es allgemein.
    const cell = unit ? graph.getDataModel().getCell(unit) : null
    const label = cell ? graph.convertValueToString(cell).trim() : ''
    const element = label ? `"${label}"` : 'an element'
    log(`${mine ? 'Your' : `${name(loser)}'s`} change to ${element} was overwritten by ${name(winner)}`, 'conflict')
    if (!mine) return
    notifyWarning(`Your change was overwritten by ${name(winner)}`)
    // The winning value may still be on its way into the graph.
    if (!unit) return
    setTimeout(() => {
      const unframe = stopped ? null : frameCell(graph, unit, '#d32f2f')
      if (unframe) frames.add(unframe)
    })
  })

  return () => {
    stopped = true
    stop()
    for (const unframe of frames) unframe()
  }
}
