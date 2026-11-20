import { cellArrayUtils, type Graph } from '@maxgraph/core'

function gridTarget(coordinate: number, direction: number, gridSize: number): number {
  const position = coordinate / gridSize
  // Treat floating-point residue at a grid line as an exact grid position.
  const nearest = Math.round(position)
  const normalized = Math.abs(position - nearest) < 1e-9 ? nearest : position
  if (direction < 0) return (Math.ceil(normalized) - 1) * gridSize
  if (direction > 0) return (Math.floor(normalized) + 1) * gridSize
  return nearest * gridSize
}

/** Move each selected origin to the next absolute grid point, or by one model pixel. */
export function nudgeSelectedCells(graph: Graph, dx: number, dy: number): boolean {
  if (!graph.isEnabled() || graph.isEditing()) return false

  const cells = cellArrayUtils.getTopmostCells(graph.getMovableCells(graph.getSelectionCells()))
  const view = graph.getView()
  const gridSize = graph.getGridSize()
  const snap = graph.isGridEnabled() && Number.isFinite(gridSize) && gridSize > 0
  const moves = cells.flatMap((cell) => {
    // Attached edges follow their terminals; only fully dangling edges move independently.
    if (cell.isEdge() && (cell.getTerminal(true) || cell.getTerminal(false))) return []
    const state = view.getState(cell)
    if (!state || !cell.getGeometry()) return []

    // State bounds include ancestor offsets. Remove zoom and view translation so
    // nested cells and free edges use the same origin as the visible model grid.
    const x = state.x / view.scale - view.translate.x
    const y = state.y / view.scale - view.translate.y
    return [{ cell, dx: snap ? gridTarget(x, dx, gridSize) - x : dx, dy: snap ? gridTarget(y, dy, gridSize) - y : dy }]
  })
  if (!moves.length) return false

  // Keep the complete selection movement in one undo/collaboration transaction.
  graph.batchUpdate(() => {
    for (const move of moves) graph.moveCells([move.cell], move.dx, move.dy)
  })
  return true
}
