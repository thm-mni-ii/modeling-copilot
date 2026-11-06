import type { Graph } from '@maxgraph/core'

/**
 * Locks the cells against moving, resizing, editing, deleting and connecting. Selection and zoom
 * stay, as the others see what a reader selects. Gives back how to unlock to what was set before.
 */
export const lockGraph = (graph: Graph) => {
  const before = { locked: graph.isCellsLocked(), deletable: graph.isCellsDeletable(), cloneable: graph.isCellsCloneable(), connectable: graph.isConnectable() }
  graph.stopEditing(true)
  graph.setCellsLocked(true)
  graph.setCellsDeletable(false)
  graph.setCellsCloneable(false)
  graph.setConnectable(false)
  return () => {
    graph.setCellsLocked(before.locked)
    graph.setCellsDeletable(before.deletable)
    graph.setCellsCloneable(before.cloneable)
    graph.setConnectable(before.connectable)
  }
}
