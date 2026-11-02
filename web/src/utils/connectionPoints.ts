import type { Cell, CellStyle, ConnectionConstraint } from '@maxgraph/core'
import type { AnchorPoint, DiagramElement } from '@/model/Element'
import type { EndpointSelector } from '@/model/Syntax'

/** Deterministic identity for existing points; new points receive UUIDs in the editor. */
export const pointId = (point: AnchorPoint): string => point.id ?? `point-${point.x}-${point.y}`
export const pointLabel = (point: AnchorPoint): string => point.name?.trim() || `(${point.x}, ${point.y})`
export const ensurePointIds = (points: AnchorPoint[]) => {
  for (const point of points) point.id ??= pointId(point)
}

export const elementTypeOf = (cell: Cell | null): string | null => {
  if (!cell) return null
  return (cell as any).diagramElementType ?? (cell as any).diagramAttributes?.type ?? null
}

export const pointsOf = (cell: Cell | null): AnchorPoint[] => {
  const json = (cell as any)?.connectionPointsJson
  if (typeof json !== 'string') return []
  try { const points = JSON.parse(json); return Array.isArray(points) ? points : [] }
  catch { return [] }
}

export const endpointId = (edge: Cell, source: boolean, terminal: Cell | null): string | null => {
  const style = edge.getStyle() as Record<string, unknown>
  const id = style[source ? 'exitPointId' : 'entryPointId']
  if (typeof id === 'string' && id) return id
  const x = style[source ? 'exitX' : 'entryX']
  const y = style[source ? 'exitY' : 'entryY']
  if (x == null || y == null) return null
  const point = pointsOf(terminal).find((p) => Math.abs(p.x - Number(x)) < 0.000001 && Math.abs(p.y - Number(y)) < 0.000001)
  return point ? pointId(point) : null
}

export const matchesEndpoint = (selector: EndpointSelector | undefined, id: string | null, points: AnchorPoint[]): boolean => {
  if (!selector?.pointIds?.length && !selector?.groups?.length) return true
  if (!id) return false
  const point = points.find((p) => pointId(p) === id)
  return Boolean(selector.pointIds?.includes(id) || point?.groups?.some((g) => selector.groups?.includes(g)))
}

export const endpointStyle = (point: AnchorPoint | null, source: boolean): Record<string, string | number | boolean> => point ? {
  [source ? 'exitPointId' : 'entryPointId']: pointId(point),
  [source ? 'exitX' : 'entryX']: point.x,
  [source ? 'exitY' : 'entryY']: point.y,
  [source ? 'exitPerimeter' : 'entryPerimeter']: false
} : {}

export const constraintStyle = (constraint: ConnectionConstraint | null | undefined, source: boolean) => constraint?.point ? {
  [source ? 'exitPointId' : 'entryPointId']: constraint.name ?? '',
  [source ? 'exitX' : 'entryX']: constraint.point.x,
  [source ? 'exitY' : 'entryY']: constraint.point.y,
  [source ? 'exitPerimeter' : 'entryPerimeter']: constraint.perimeter
} as CellStyle : {}

export const availablePoints = (element: DiagramElement): (AnchorPoint | null)[] => {
  const points = element.anchorPoints ?? []
  return element.docking === 'outline' || points.length === 0 ? [...points, null] : points
}
