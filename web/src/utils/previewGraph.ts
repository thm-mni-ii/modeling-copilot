import { EdgeStyle, Graph, InternalEvent, Point } from '@maxgraph/core'
import { protectHtmlLabels } from './htmlLabels'

export const createPreviewGraph = (container: HTMLDivElement): Graph => {
  container.innerHTML = ''

  const graph = new Graph(container)
  // Gleiche Standard-Linienführung wie im Canvas (DrawingCanvas.vue)
  graph.getStylesheet().getDefaultEdgeStyle().edgeStyle = EdgeStyle.OrthConnector
  graph.setEnabled(false)
  graph.setPanning(false)
  graph.setConnectable(false)
  graph.setCellsResizable(false)
  graph.setDropEnabled(false)
  graph.setCellsEditable(false)
  graph.setCellsMovable(false)
  graph.setCellsCloneable(false)
  graph.setAllowDanglingEdges(false)
  graph.setHtmlLabels(true)
  protectHtmlLabels(graph)
  graph.getView().updateStyle = false
  InternalEvent.disableContextMenu(container)

  return graph
}

export const fitPreviewGraph = (graph: Graph, padding = 8): void => {
  const container = graph.container
  const bounds = graph.getGraphBounds()

  const availableWidth = Math.max(container.clientWidth - padding * 2, 1)
  const availableHeight = Math.max(container.clientHeight - padding * 2, 1)
  const width = Math.max(bounds.width, 1)
  const height = Math.max(bounds.height, 1)

  const scale = Math.min(availableWidth / width, availableHeight / height, 1)

  const view = graph.getView()
  view.scale = scale

  const dx = padding / scale - bounds.x + (availableWidth / scale - width) / 2
  const dy = padding / scale - bounds.y + (availableHeight / scale - height) / 2

  view.translate = new Point(dx, dy)
  graph.refresh()
}

export const destroyPreviewGraph = (graph: Graph | null): null => {
  if (graph) {
    graph.destroy()
  }
  return null
}
