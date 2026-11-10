import { Geometry } from '@maxgraph/core'
import type { Graph, Cell } from '@maxgraph/core'

export type HorizontalAlignment = 'left' | 'center' | 'right'
export type VerticalAlignment = 'top' | 'middle' | 'bottom'

function getAlignableCells(graph: Graph): Cell[] {
  return graph.getSelectionCells().filter((cell) => cell.isVertex() && cell.getGeometry() != null)
}

function getGridAwareTarget(graph: Graph, target: number, offsets: number[]): number {
  const gridSize = graph.getGridSize()
  if (!graph.isGridEnabled() || !Number.isFinite(gridSize) || gridSize <= 0) return target

  // Each offset describes where the shared alignment axis must lie modulo the grid
  // for that cell's origin to snap. Equal offsets allow every cell to snap exactly.
  const phases = offsets.map((offset) => ((offset % gridSize) + gridSize) % gridSize).sort((a, b) => a - b)
  const epsilon = gridSize * 1e-9
  let largestGap = -1
  let bestTarget = target
  let bestDistance = Infinity

  for (let i = 0; i < phases.length; i++) {
    const next = i + 1 < phases.length ? phases[i + 1] : phases[0] + gridSize
    const gap = next - phases[i]
    // The midpoint of the arc opposite the largest gap minimizes the largest
    // distance from any cell origin to the grid, keeping alignment exact.
    const phase = (next + phases[i] + gridSize) / 2
    const candidate = phase + Math.round((target - phase) / gridSize) * gridSize
    const distance = Math.abs(candidate - target)

    if (gap > largestGap + epsilon || (Math.abs(gap - largestGap) <= epsilon && (distance < bestDistance - epsilon || (Math.abs(distance - bestDistance) <= epsilon && candidate > bestTarget)))) {
      largestGap = gap
      bestTarget = candidate
      bestDistance = distance
    }
  }

  return bestTarget
}

export function alignHorizontal(graph: Graph, alignment: HorizontalAlignment): void {
  const cells = getAlignableCells(graph)
  if (cells.length < 2) return

  const model = graph.getDataModel()

  graph.batchUpdate(() => {
    if (alignment === 'left') {
      const minX = getGridAwareTarget(graph, Math.min(...cells.map((c) => c.getGeometry()!.x)), [0])
      for (const cell of cells) {
        const geo = cell.getGeometry()!.clone() as Geometry
        geo.x = minX
        model.setGeometry(cell, geo)
      }
    } else if (alignment === 'right') {
      const maxRight = getGridAwareTarget(graph, Math.max(...cells.map((c) => c.getGeometry()!.x + c.getGeometry()!.width)), cells.map((c) => c.getGeometry()!.width))
      for (const cell of cells) {
        const geo = cell.getGeometry()!.clone() as Geometry
        geo.x = maxRight - geo.width
        model.setGeometry(cell, geo)
      }
    } else {
      // center
      const minX = Math.min(...cells.map((c) => c.getGeometry()!.x))
      const maxRight = Math.max(...cells.map((c) => c.getGeometry()!.x + c.getGeometry()!.width))
      const centerX = getGridAwareTarget(graph, (minX + maxRight) / 2, cells.map((c) => c.getGeometry()!.width / 2))
      for (const cell of cells) {
        const geo = cell.getGeometry()!.clone() as Geometry
        geo.x = centerX - geo.width / 2
        model.setGeometry(cell, geo)
      }
    }
  })

  graph.refresh()
  graph.view.validate()
}

/** Aligns selected vertices using their outer bounds and the active grid. */
export function alignVertical(graph: Graph, alignment: VerticalAlignment): void {
  const cells = getAlignableCells(graph)
  if (cells.length < 2) return

  const model = graph.getDataModel()

  graph.batchUpdate(() => {
    if (alignment === 'top') {
      const minY = getGridAwareTarget(graph, Math.min(...cells.map((c) => c.getGeometry()!.y)), [0])
      for (const cell of cells) {
        const geo = cell.getGeometry()!.clone() as Geometry
        geo.y = minY
        model.setGeometry(cell, geo)
      }
    } else if (alignment === 'bottom') {
      const maxBottom = getGridAwareTarget(graph, Math.max(...cells.map((c) => c.getGeometry()!.y + c.getGeometry()!.height)), cells.map((c) => c.getGeometry()!.height))
      for (const cell of cells) {
        const geo = cell.getGeometry()!.clone() as Geometry
        geo.y = maxBottom - geo.height
        model.setGeometry(cell, geo)
      }
    } else {
      // middle
      const minY = Math.min(...cells.map((c) => c.getGeometry()!.y))
      const maxBottom = Math.max(...cells.map((c) => c.getGeometry()!.y + c.getGeometry()!.height))
      const centerY = getGridAwareTarget(graph, (minY + maxBottom) / 2, cells.map((c) => c.getGeometry()!.height / 2))
      for (const cell of cells) {
        const geo = cell.getGeometry()!.clone() as Geometry
        geo.y = centerY - geo.height / 2
        model.setGeometry(cell, geo)
      }
    }
  })

  graph.refresh()
  graph.view.validate()
}
