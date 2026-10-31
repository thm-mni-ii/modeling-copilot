import { Graph, Point, Cell, FitPlugin } from '@maxgraph/core'
import type { CellStyle } from '@maxgraph/core'
import type { DiagramConnection } from '@/model/Connection'
import { applyConnectionAdditionalLabels, applyConnectionLabelOffset } from './connectionLabelHelpers'
import { createConnectionStyle } from './elementFactory'

export type ConnectionPreviewMode = 'simple' | 'scenario' | 'routing'

type EdgeStyle = CellStyle & Record<string, any>

const cloneStyle = (style: EdgeStyle): EdgeStyle => ({ ...style })

/** Leitet den Style einer Vorschau-Kante aus dem Style der Verbindung ab. */
type PreviewStyle = (base: EdgeStyle) => EdgeStyle

type PreviewCell = Cell & {
  previewStyle?: PreviewStyle
  // Trägt Label, Label-Versatz und Zusatzlabels der Verbindung
  previewLabel?: boolean
  previewSummary?: boolean
}

/** Kante der Verbindungsvorschau im Editor (dort darf man sie frei verformen). */
export const isPreviewEdge = (cell: Cell): boolean => Boolean((cell as PreviewCell).previewStyle)

const markPreviewEdge = (edge: Cell, connection: DiagramConnection, previewStyle: PreviewStyle = cloneStyle, previewLabel = false): void => {
  ;(edge as any).connectionId = connection.type
  ;(edge as PreviewCell).previewStyle = previewStyle
  ;(edge as PreviewCell).previewLabel = previewLabel
}

const dashedStyle: PreviewStyle = (base) => ({ ...base, dashed: true, dashPattern: base.dashPattern ?? '6 4' })

const applyPoints = (edge: any, points?: { x: number; y: number }[]) => {
  if (!points || points.length === 0) return
  const geometry = edge.getGeometry()
  if (!geometry) return
  geometry.points = points.map((pt) => new Point(pt.x, pt.y))
}

export const clearConnectionPreview = (graph: Graph): void => {
  graph.removeCells(graph.getChildCells())
}

/**
 * Übernimmt geänderte Einstellungen in die vorhandene Vorschau, ohne sie neu aufzubauen.
 * So bleiben verschobene Elemente und Knickpunkte erhalten.
 * @returns false, wenn es noch keine Vorschau gibt und sie neu aufgebaut werden muss
 */
export const updateConnectionPreview = (graph: Graph, connection: DiagramConnection): boolean => {
  const cells = graph.getChildCells() as PreviewCell[]
  const edges = cells.filter((cell) => cell.previewStyle)
  if (edges.length === 0) return false

  const model = graph.getDataModel()
  model.beginUpdate()
  try {
    for (const edge of edges) {
      model.setStyle(edge, edge.previewStyle!(createConnectionStyle(connection)))
      if (!edge.previewLabel) continue

      model.setValue(edge, connection.defaultLabel ?? '')
      applyConnectionLabelOffset(edge, connection.labelOffset)
      applyConnectionAdditionalLabels(graph, edge, connection)
    }

    cells.filter((cell) => cell.previewSummary).forEach((note) => model.setValue(note, describeScenario(createConnectionStyle(connection))))
  } finally {
    model.endUpdate()
  }

  return true
}

export const renderSimpleConnectionPreview = (graph: Graph, connection: DiagramConnection): Cell | null => {
  clearConnectionPreview(graph)
  const parent = graph.getDefaultParent()
  let createdEdge: Cell | null = null

  graph.getDataModel().beginUpdate()
  try {
    const style = createConnectionStyle(connection)

    const source = graph.insertVertex({
      parent,
      value: '',
      x: 80,
      y: 120,
      width: 1,
      height: 1,
      style: { opacity: 0 }
    })

    const target = graph.insertVertex({
      parent,
      value: '',
      x: 320,
      y: 120,
      width: 1,
      height: 1,
      style: { opacity: 0 }
    })

    const edge = graph.insertEdge({
      parent,
      source,
      target,
      value: connection.defaultLabel ?? '',
      style
    })
    createdEdge = edge ?? null
    markPreviewEdge(edge, connection, cloneStyle, true)

    applyConnectionLabelOffset(edge, connection.labelOffset)
    applyPoints(edge, connection.points)
    applyConnectionAdditionalLabels(graph, edge, connection)

    graph.clearSelection()
  } finally {
    graph.getDataModel().endUpdate()
  }

  return createdEdge
}

const createActorVertex = (graph: Graph, parent: any, { x, y, label, fill }: { x: number; y: number; label: string; fill: string }) => {
  return graph.insertVertex({
    parent,
    value: label,
    x,
    y,
    width: 150,
    height: 70,
    style: {
      shape: 'rounded',
      fillColor: fill,
      strokeColor: '#37474f',
      fontColor: '#263238',
      fontSize: 14,
      align: 'center',
      verticalAlign: 'middle',
      whiteSpace: 'wrap'
    }
  })
}

const describeScenario = (style: EdgeStyle): string => `Sample Scenario\n\n• Entry: Client sends a request\n• Gateway forwards and responds\n• Service publishes an event\n\nProperties:\n• ${describeStyleSummary(style)}`

const describeStyleSummary = (style: EdgeStyle): string => {
  const fragments: string[] = []

  if (style.dashed) fragments.push('Dashed line')
  if (style.rounded) fragments.push('Abgerundete Knicke')
  if (style.curved) fragments.push('Kurvierter Verlauf')
  if (style.startArrow && style.startArrow !== 'none') fragments.push(`Start arrow: ${style.startArrow}`)
  if (style.endArrow && style.endArrow !== 'none') fragments.push(`End arrow: ${style.endArrow}`)
  if (style.strokeWidth) fragments.push(`Line width: ${style.strokeWidth}px`)
  if (style.strokeColor) fragments.push(`Line color: ${style.strokeColor}`)
  if (style.portConstraint) fragments.push(`Port-Constraint: ${style.portConstraint}`)

  if (fragments.length === 0) {
    return 'Default appearance without special options.'
  }

  return fragments.join('\n• ')
}

const feedbackStyle: PreviewStyle = (base) => ({ ...base, curved: true, startArrow: base.startArrow ?? 'open', endArrow: base.endArrow ?? 'classic' })

export const renderScenarioConnectionPreview = (graph: Graph, connection: DiagramConnection): void => {
  clearConnectionPreview(graph)
  const parent = graph.getDefaultParent()

  graph.getDataModel().beginUpdate()
  try {
    const baseStyle = createConnectionStyle(connection)

    const client = createActorVertex(graph, parent, {
      x: 40,
      y: 100,
      label: 'Client UI\n(Business Unit)',
      fill: '#e3f2fd'
    })

    const gateway = createActorVertex(graph, parent, {
      x: 250,
      y: 60,
      label: 'API Gateway\n(Integration)',
      fill: '#e8f5e9'
    })

    const service = createActorVertex(graph, parent, {
      x: 250,
      y: 210,
      label: 'Order Service\n(Domain)',
      fill: '#fff8e1'
    })

    const eventBus = createActorVertex(graph, parent, {
      x: 460,
      y: 140,
      label: 'Event Bus\n(Distribution)',
      fill: '#f3e5f5'
    })

    const note = graph.insertVertex({
      parent,
      value: describeScenario(baseStyle),
      x: 40,
      y: 220,
      width: 200,
      height: 160,
      style: {
        shape: 'note',
        fillColor: '#fffde7',
        strokeColor: '#fbc02d',
        fontColor: '#5d4037',
        fontSize: 12,
        whiteSpace: 'wrap'
      }
    })

    ;(note as PreviewCell).previewSummary = true

    const requestEdge = graph.insertEdge({
      parent,
      source: client,
      target: gateway,
      value: connection.defaultLabel ?? '',
      style: cloneStyle(baseStyle)
    })

    markPreviewEdge(requestEdge, connection, cloneStyle, true)
    applyConnectionLabelOffset(requestEdge, connection.labelOffset)
    applyPoints(requestEdge, connection.points)
    applyConnectionAdditionalLabels(graph, requestEdge, connection)

    const forwardEdge = graph.insertEdge({
      parent,
      source: gateway,
      target: service,
      value: 'Forward to domain',
      style: cloneStyle(baseStyle)
    })

    markPreviewEdge(forwardEdge, connection)
    const forwardGeometry = forwardEdge.getGeometry()
    if (forwardGeometry) {
      forwardGeometry.points = [new Point(gateway.geometry!.x + gateway.geometry!.width + 30, gateway.geometry!.y + gateway.geometry!.height + 10)]
    }

    const eventEdge = graph.insertEdge({
      parent,
      source: service,
      target: eventBus,
      value: 'Domain Event',
      style: dashedStyle(baseStyle)
    })
    markPreviewEdge(eventEdge, connection, dashedStyle)

    const feedbackEdge = graph.insertEdge({
      parent,
      source: eventBus,
      target: client,
      value: 'Notification',
      style: feedbackStyle(baseStyle)
    })
    markPreviewEdge(feedbackEdge, connection, feedbackStyle)

    const feedbackGeometry = feedbackEdge.getGeometry()
    if (feedbackGeometry) {
      feedbackGeometry.points = [new Point(eventBus.geometry!.x + 60, eventBus.geometry!.y - 80), new Point(client.geometry!.x - 40, client.geometry!.y + 20)]
    }

    applyConnectionLabelOffset(feedbackEdge, connection.labelOffset)

    graph.clearSelection()
  } finally {
    graph.getDataModel().endUpdate()
  }

  // Fit the entire scenario to the visible area
  graph.getPlugin<FitPlugin>(FitPlugin.pluginId)?.fit({ border: 10 })
  graph.view.validate()
  graph.refresh()
}

export const renderRoutingConnectionPreview = (graph: Graph, connection: DiagramConnection): void => {
  clearConnectionPreview(graph)
  const parent = graph.getDefaultParent()

  graph.getDataModel().beginUpdate()
  try {
    const baseStyle = createConnectionStyle(connection)

    // Create a complex layout with obstacles to demonstrate routing algorithms
    // This layout will show different paths depending on the routing algorithm chosen

    // Central hub
    const hub = graph.insertVertex({
      parent,
      value: 'Central\nHub',
      x: 320,
      y: 200,
      width: 120,
      height: 90,
      style: {
        shape: 'rounded',
        fillColor: '#1976d2',
        strokeColor: '#0d47a1',
        fontColor: '#ffffff',
        fontSize: 14,
        fontStyle: 1
      }
    })

    // Top node
    const topNode = graph.insertVertex({
      parent,
      value: 'Service A',
      x: 310,
      y: 20,
      width: 140,
      height: 70,
      style: {
        shape: 'rounded',
        fillColor: '#43a047',
        strokeColor: '#2e7d32',
        fontColor: '#ffffff',
        fontSize: 13
      }
    })

    // Left node
    const leftNode = graph.insertVertex({
      parent,
      value: 'Service B',
      x: 30,
      y: 180,
      width: 140,
      height: 70,
      style: {
        shape: 'rounded',
        fillColor: '#fb8c00',
        strokeColor: '#e65100',
        fontColor: '#ffffff',
        fontSize: 13
      }
    })

    // Right node
    const rightNode = graph.insertVertex({
      parent,
      value: 'Service C',
      x: 590,
      y: 180,
      width: 140,
      height: 70,
      style: {
        shape: 'rounded',
        fillColor: '#8e24aa',
        strokeColor: '#6a1b9a',
        fontColor: '#ffffff',
        fontSize: 13
      }
    })

    // Bottom left
    const bottomLeft = graph.insertVertex({
      parent,
      value: 'Database',
      x: 80,
      y: 380,
      width: 120,
      height: 80,
      style: {
        shape: 'cylinder',
        fillColor: '#039be5',
        strokeColor: '#01579b',
        fontColor: '#ffffff',
        fontSize: 13
      }
    })

    // Bottom right
    const bottomRight = graph.insertVertex({
      parent,
      value: 'Cache',
      x: 560,
      y: 380,
      width: 120,
      height: 80,
      style: {
        shape: 'hexagon',
        fillColor: '#e53935',
        strokeColor: '#c62828',
        fontColor: '#ffffff',
        fontSize: 13
      }
    })

    // Top-left diagonal element
    const topLeftDiagonal = graph.insertVertex({
      parent,
      value: 'Analytics',
      x: 30,
      y: 30,
      width: 130,
      height: 65,
      style: {
        shape: 'rounded',
        fillColor: '#00897b',
        strokeColor: '#00695c',
        fontColor: '#ffffff',
        fontSize: 13
      }
    })

    // Bottom-right diagonal element
    const bottomRightDiagonal = graph.insertVertex({
      parent,
      value: 'Monitor',
      x: 600,
      y: 490,
      width: 130,
      height: 65,
      style: {
        shape: 'rounded',
        fillColor: '#6d4c41',
        strokeColor: '#4e342e',
        fontColor: '#ffffff',
        fontSize: 13
      }
    })

    // Obstacle in the middle (to force routing around it)
    const obstacle = graph.insertVertex({
      parent,
      value: 'Firewall',
      x: 310,
      y: 330,
      width: 140,
      height: 60,
      style: {
        shape: 'rectangle',
        fillColor: '#757575',
        strokeColor: '#424242',
        fontColor: '#ffffff',
        fontSize: 12,
        opacity: 60
      }
    })

    void obstacle

    // Create edges that will show different routing behavior
    // Edge 1: Top to Hub (straight vs curved)
    const edge1 = graph.insertEdge({
      parent,
      source: topNode,
      target: hub,
      value: connection.defaultLabel ?? '',
      style: cloneStyle(baseStyle)
    })

    markPreviewEdge(edge1, connection, cloneStyle, true)
    applyConnectionLabelOffset(edge1, connection.labelOffset)
    applyConnectionAdditionalLabels(graph, edge1, connection)

    // Edge 2: Left to Hub (will show orthogonal vs elbow differences)
    const edge2 = graph.insertEdge({
      parent,
      source: leftNode,
      target: hub,
      value: '',
      style: cloneStyle(baseStyle)
    })

    // Edge 3: Right to Hub
    const edge3 = graph.insertEdge({
      parent,
      source: rightNode,
      target: hub,
      value: '',
      style: cloneStyle(baseStyle)
    })

    // Edge 4: Hub to Bottom Left (needs to route around obstacle)
    const edge4 = graph.insertEdge({
      parent,
      source: hub,
      target: bottomLeft,
      value: '',
      style: cloneStyle(baseStyle)
    })

    // Edge 5: Hub to Bottom Right (needs to route around obstacle)
    const edge5 = graph.insertEdge({
      parent,
      source: hub,
      target: bottomRight,
      value: '',
      style: cloneStyle(baseStyle)
    })

    // Edge 6: Lateral connection (Left to Right, passing above/below hub)
    const edge6 = graph.insertEdge({
      parent,
      source: leftNode,
      target: rightNode,
      value: '',
      style: dashedStyle(baseStyle)
    })

    // Edge 7: Diagonal connection (Top-Left to Bottom-Right) - shows routing difference clearly
    const edge7 = graph.insertEdge({
      parent,
      source: topLeftDiagonal,
      target: bottomRightDiagonal,
      value: '',
      style: cloneStyle(baseStyle)
    })

    // Edge 8: Analytics to Hub
    const edge8 = graph.insertEdge({
      parent,
      source: topLeftDiagonal,
      target: hub,
      value: '',
      style: cloneStyle(baseStyle)
    })

    // Edge 9: Cache to Monitor
    const edge9 = graph.insertEdge({
      parent,
      source: bottomRight,
      target: bottomRightDiagonal,
      value: '',
      style: cloneStyle(baseStyle)
    })

    // Info note explaining what to observe
    graph.insertVertex({
      parent,
      value: `Routing Demo\n\nChange the routing settings and observe:\n\n• How Connections route around the obstacle (firewall)\n• Differences between orthogonal and diagonal Connections\n• Diagonal Connection (Analytics ↔ Monitor)\n• Effects of the 'rounded' and 'curved' options\n• Behavior with different edge styles`,
      x: 30,
      y: 570,
      width: 700,
      height: 110,
      style: {
        shape: 'note',
        fillColor: '#fff3e0',
        strokeColor: '#ff9800',
        fontColor: '#bf360c',
        fontSize: 11,
        whiteSpace: 'wrap',
        align: 'left',
        verticalAlign: 'top',
        spacingLeft: 10,
        spacingTop: 8
      }
    })

    // Select the first edge to highlight the current style
    graph.clearSelection()

    markPreviewEdge(edge6, connection, dashedStyle)
    ;[edge2, edge3, edge4, edge5, edge7, edge8, edge9].forEach((edge) => markPreviewEdge(edge, connection))
  } finally {
    graph.getDataModel().endUpdate()
  }

  // Fit the entire layout to the visible area
  graph.getPlugin<FitPlugin>(FitPlugin.pluginId)?.fit({ border: 10 })
  graph.view.validate()
  graph.refresh()
}
