import { Cell, Geometry, ConnectionConstraint, Point, Rectangle } from '@maxgraph/core'
import type { Graph } from '@maxgraph/core'
import type { DiagramElement } from '@/model/Element'

/**
 * Erstellt eine MaxGraph Cell aus einer DiagramElement-Definition
 *
 * Diese Methode wird sowohl von der Toolbar als auch von der Vorschau verwendet,
 * um sicherzustellen, dass Elemente identisch erstellt werden.
 *
 * @param element - Die DiagramElement-Definition
 * @param x - X-Position
 * @param y - Y-Position
 * @returns Die erstellte Cell
 */
export function createCellFromElement(element: DiagramElement, x: number, y: number): Cell {
  const width = element.width ?? 120
  const height = element.height ?? 80
  const style = element.style ?? {}

  // 1. Basis-Style aufbauen
  const baseStyle: Record<string, any> = {
    shape: element.renderMode === 'swimlane' ? 'swimlane' : element.predefinedShape ?? 'rectangle',
    ...style, // Alle Style-Eigenschaften aus Definition übernehmen
    // Defaults für fehlende Werte
    strokeColor: style.strokeColor ?? 'black',
    fillColor: style.fillColor ?? '#f5f5f5',
    strokeWidth: style.strokeWidth ?? 1,
    fontSize: style.fontSize ?? 11,
    fontColor: style.fontColor ?? 'black',
    fontFamily: style.fontFamily ?? 'Arial',
    align: style.align ?? 'center',
    verticalAlign: style.verticalAlign ?? 'middle'
  }

  // Swimlane-spezifische Eigenschaften
  if (element.renderMode === 'swimlane') {
    if (baseStyle.startSize === undefined) baseStyle.startSize = 22
    if (baseStyle.horizontal === undefined) baseStyle.horizontal = false
    if (baseStyle.swimlaneLine === undefined) baseStyle.swimlaneLine = true
    if (baseStyle.layoutPreset === undefined) baseStyle.layoutPreset = 'list'
    if (baseStyle.labelBackgroundColor === undefined) baseStyle.labelBackgroundColor = 'transparent'
    if (baseStyle.containerLayout === undefined) baseStyle.containerLayout = 'list'
    if (baseStyle.listDirection === undefined) baseStyle.listDirection = 'vertical'
    if (baseStyle.listItemSpacing === undefined) baseStyle.listItemSpacing = 10
    if (baseStyle.listCrossPadding === undefined) baseStyle.listCrossPadding = 10
    if (baseStyle.listStretchCrossAxis === undefined) baseStyle.listStretchCrossAxis = true
    if (baseStyle.resizeMainAxis === undefined) baseStyle.resizeMainAxis = true
    if (baseStyle.resizeCrossAxis === undefined) baseStyle.resizeCrossAxis = false
  }

  // Collapse/Folding aktivieren
  if (element.collapsible) {
    baseStyle.foldable = true
  }

  // Canvas2D: Shape-Type verwenden
  if (element.renderMode === 'canvas2d') {
    baseStyle.shape = element.type
  }

  // 2. Geometry erstellen
  const geometry = new Geometry(x, y, width, height)

  // 3. Anchor Points als Connection Constraints hinzufügen
  if (element.anchorPoints && element.anchorPoints.length > 0) {
    const constraints = element.anchorPoints.map((point: { x: number; y: number }) => new ConnectionConstraint(new Point(point.x, point.y), false))
    ;(geometry as any).constraints = constraints
  }

  // 3a. Collapse-Konfiguration auswerten (Größe + Darstellung)
  const collapsedConfig = element.collapsible ? element.collapsed : undefined
  if (element.collapsible && collapsedConfig && (collapsedConfig.width || collapsedConfig.height)) {
    const collapsedWidth = collapsedConfig.width ?? width
    const collapsedHeight = collapsedConfig.height ?? height
    geometry.alternateBounds = new Rectangle(0, 0, collapsedWidth, collapsedHeight)
  }

  // 4. Cell erstellen
  const normalStyle = { ...baseStyle }
  const cell = new Cell(element.defaultLabel, geometry, normalStyle)
  cell.setVertex(true)
  cell.setConnectable(element.connectable ?? true)
  ;(cell as any).allowLabelEdit = element.allowLabelEdit !== false
  ;(cell as any).diagramElementType = element.type
  ;(cell as any).diagramAttributes = {
    type: element.type,
    label: element.defaultLabel
  }

  const collapseMetadata: Record<string, any> = {}
  const collapsedStyle = collapsedConfig?.style ? { ...normalStyle, ...collapsedConfig.style } : undefined

  if (collapsedConfig?.label) {
    collapseMetadata.label = collapsedConfig.label
  }
  if (collapsedStyle) {
    collapseMetadata.style = collapsedStyle
  }
  if (Object.keys(collapseMetadata).length > 0) {
    ;(cell as any).collapsedConfig = collapseMetadata
  }

  // 4a. getStyle-Funktion setzen (wichtig für Collapse-Funktionalität)
  // Diese Funktion wird von MaxGraph aufgerufen um den aktuellen Style zu erhalten
  if (element.collapsible) {
    cell.getStyle = function (this: Cell) {
      if (this.isCollapsed() && collapseMetadata.style) {
        return collapseMetadata.style
      }
      return normalStyle
    }
  }

  return cell
}

/**
 * Fügt eine Cell mit ihren Child-Elementen zum Graph hinzu
 *
 * @param graph - Die Graph-Instanz
 * @param cell - Die hinzuzufügende Cell
 * @param element - Die DiagramElement-Definition (für Child-Elemente)
 * @param parent - Das Parent-Element im Graph
 */
export function addCellToGraph(graph: Graph, cell: Cell, element: DiagramElement, parent: any): void {
  const addChildRecursive = (parentCell: Cell, child: any): void => {
    const childGeometry = new Geometry(child.position.x, child.position.y, child.position.width, child.position.height)
    childGeometry.relative = child.position.relative

    if (Array.isArray(child.anchorPoints) && child.anchorPoints.length > 0) {
      const constraints = child.anchorPoints.map((point: { x: number; y: number }) => new ConnectionConstraint(new Point(point.x, point.y), false))
      ;(childGeometry as any).constraints = constraints
    }

    const childStyle: any = {
      ...child.style,
      shape: child.renderMode === 'swimlane' ? 'swimlane' : child.predefinedShape || 'label'
    }

    const childCell = new Cell(child.defaultLabel, childGeometry, childStyle)
    childCell.setVertex(true)
    childCell.setConnectable(child.connectable ?? false)
    ;(childCell as any).allowLabelEdit = child.allowLabelEdit !== false
    ;(childCell as any).diagramElementType = child.type

    graph.addCell(childCell, parentCell)

    if (Array.isArray(child.children) && child.children.length > 0) {
      child.children.forEach((nestedChild: any) => addChildRecursive(childCell, nestedChild))
    }
  }

  // Füge Haupt-Element hinzu
  graph.addCell(cell, parent)

  // Child-Elemente rekursiv hinzufügen
  if (Array.isArray(element.children) && element.children.length > 0) {
    element.children.forEach((child: any) => addChildRecursive(cell, child))
  }
}

/**
 * Erstellt das Style-Objekt für eine Verbindung aus einer DiagramConnection-Definition
 *
 * Diese Methode wird vom CustomConnectionHandler und von der Vorschau verwendet,
 * um sicherzustellen, dass Verbindungen identisch erstellt werden.
 *
 * @param connection - Die DiagramConnection-Definition
 * @returns Das Style-Objekt für MaxGraph
 */
/**
 * Rendert eine Verbindungs-Vorschau im Graph (nur die Edge, mit Dummy-Knoten)
 *
 * Diese Methode wird verwendet, um eine einzelne Verbindung im Preview-Modus anzuzeigen
 *
 * @param graph - Die Graph-Instanz
 * @param connection - Die DiagramConnection-Definition
 */
