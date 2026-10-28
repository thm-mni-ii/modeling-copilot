import { Point } from '@maxgraph/core'
import type { AbstractGraph, Cell } from '@maxgraph/core'
import type { ConnectionLabelCell, DiagramConnection } from '@/model/Connection'

const DEFAULT_LABEL_STYLE = {
  shape: 'label',
  strokeColor: 'transparent',
  fillColor: 'transparent',
  align: 'center',
  verticalAlign: 'middle',
  fontColor: '#000000',
  fontSize: 12
} as const

const sanitizeGeometryValue = (value: number | undefined, fallback = 0): number => {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

const ensureLabelCellId = (definition: ConnectionLabelCell): string => {
  const trimmed = typeof definition.type === 'string' ? definition.type.trim() : ''
  if (!trimmed) {
    const fallback = `Label ${Math.floor(Math.random() * 100000)}`
    definition.type = fallback
    return fallback
  }
  if (trimmed !== definition.type) {
    definition.type = trimmed
  }
  return trimmed
}

/**
 * Entfernt zuvor hinzugef��gte zusätzliche Label-Zellen von der Edge.
 * Es werden nur Zellen entfernt, die das Marker-Flag `connectionLabelId` tragen.
 */
const removeExistingAdditionalLabels = (graph: AbstractGraph, edge: Cell): void => {
  const childCount = edge.getChildCount()
  if (childCount === 0) return

  const toRemove: Cell[] = []
  for (let i = 0; i < childCount; i += 1) {
    const child = edge.getChildAt(i) as Cell
    if ((child as any).connectionLabelId) {
      toRemove.push(child)
    }
  }

  if (toRemove.length > 0) {
    graph.removeCells(toRemove)
  }
}

const applyGeometrySettings = (cell: Cell, definition: ConnectionLabelCell): void => {
  const geometry = cell.getGeometry()
  if (!geometry) return

  const relative = definition.geometry?.relative ?? true
  geometry.relative = relative

  if (definition.geometry) {
    if (definition.geometry.x !== undefined) geometry.x = definition.geometry.x
    if (definition.geometry.y !== undefined) geometry.y = definition.geometry.y
    if (definition.geometry.width !== undefined) geometry.width = definition.geometry.width
    if (definition.geometry.height !== undefined) geometry.height = definition.geometry.height

    if (definition.geometry.offsetX !== undefined || definition.geometry.offsetY !== undefined) {
      const offsetX = sanitizeGeometryValue(definition.geometry.offsetX)
      const offsetY = sanitizeGeometryValue(definition.geometry.offsetY)
      geometry.offset = new Point(offsetX, offsetY)
    }
  }

  cell.setGeometry(geometry)
}

/**
 * Positioniert das Haupt-Label einer Edge.
 * x: relativ entlang der Kante (-1 = Start, 0 = Mitte, 1 = Ende),
 * y: Pixel senkrecht auf dem Bildschirm, positiv nach oben (wie der Label-Versatz bei Elementen).
 * Diese Funktion wird sowohl in der Vorschau als auch beim tatsächlichen Insert verwendet.
 */
export const applyConnectionLabelOffset = (edge: Cell, offset: DiagramConnection['labelOffset']): void => {
  if (!offset) return
  const geometry = edge.getGeometry()
  if (!geometry) return

  const clone = geometry.clone()
  if (offset.x !== undefined) clone.x = offset.x
  if (offset.y !== undefined) clone.offset = new Point(clone.offset?.x ?? 0, -offset.y)
  edge.setGeometry(clone)
}

/**
 * Fügt einer Edge zusätzliche Text-Zellen als Kinder hinzu.
 * Diese Funktion wird sowohl in der Vorschau als auch beim tatsächlichen Insert verwendet.
 */
export const applyConnectionAdditionalLabels = (graph: AbstractGraph, edge: Cell, connection: DiagramConnection): void => {
  const definitions = connection.additionalLabels ?? []
  if (definitions.length === 0) {
    removeExistingAdditionalLabels(graph, edge)
    return
  }

  removeExistingAdditionalLabels(graph, edge)
  definitions.forEach((definition) => {
    const labelId = ensureLabelCellId(definition)
    // Der Label-Typ wiederholt sich auf jeder Kante, die Zell-ID muss im ganzen Modell eindeutig sein
    const cellId = `${edge.getId()}-${labelId}`
    const style = {
      ...DEFAULT_LABEL_STYLE,
      fontColor: connection.style.fontColor ?? DEFAULT_LABEL_STYLE.fontColor,
      fontSize: connection.style.fontSize ?? DEFAULT_LABEL_STYLE.fontSize,
      ...definition.style
    }
    style.editable = definition.allowLabelEdit !== false

    const width = sanitizeGeometryValue(definition.geometry?.width, 0)
    const height = sanitizeGeometryValue(definition.geometry?.height, 0)
    const x = sanitizeGeometryValue(definition.geometry?.x, 0)
    const y = sanitizeGeometryValue(definition.geometry?.y, 0)

    const child = graph.insertVertex({
      id: cellId,
      parent: edge,
      value: definition.text ?? '',
      x,
      y,
      width,
      height,
      style
    })

    child.setConnectable(definition.connectable ?? false)
    ;(child as any).allowLabelEdit = definition.allowLabelEdit !== false
    ;(child as any).connectionLabelId = labelId
    if (child.getId() !== cellId) {
      child.setId(cellId)
    }

    applyGeometrySettings(child, definition)
  })
}
