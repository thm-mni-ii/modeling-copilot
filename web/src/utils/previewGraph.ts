import { EdgeStyle, Graph, InternalEvent, Point } from '@maxgraph/core'
import { enableLabelPadding, protectHtmlLabels } from './htmlLabels'
import { installFeedbackOverlayRenderer } from './feedbackOverlays'

const resizeObservers = new WeakMap<Graph, ResizeObserver>()

export const createPreviewGraph = (container: HTMLDivElement): Graph => {
  container.innerHTML = ''

  const graph = new Graph(container)
  installFeedbackOverlayRenderer(graph)
  // Same default edge routing as in the canvas (DrawingCanvas.vue)
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
  enableLabelPadding(graph)
  graph.getView().updateStyle = false
  InternalEvent.disableContextMenu(container)

  const observer = new ResizeObserver(() => fitPreviewGraph(graph))
  observer.observe(container)
  resizeObservers.set(graph, observer)

  return graph
}

export const fitPreviewGraph = (graph: Graph, padding = 8): void => {
  const container = graph.container
  // Hidden tabs have no usable dimensions. Fit when the observer sees them become visible.
  if (container.clientWidth === 0 || container.clientHeight === 0) return

  const view = graph.getView()
  // Measure without an existing transform so repeated fits do not accumulate scaling or rounding.
  view.scale = 1
  view.translate = new Point(0, 0)
  graph.refresh()
  const bounds = graph.getGraphBounds()

  const availableWidth = Math.max(container.clientWidth - padding * 2, 1)
  const availableHeight = Math.max(container.clientHeight - padding * 2, 1)
  const width = Math.max(bounds.width, 1)
  const height = Math.max(bounds.height, 1)

  const scale = Math.min(availableWidth / width, availableHeight / height, 1)

  view.scale = scale

  const dx = padding / scale - bounds.x + (availableWidth / scale - width) / 2
  const dy = padding / scale - bounds.y + (availableHeight / scale - height) / 2

  view.translate = new Point(dx, dy)
  graph.refresh()
}

export const destroyPreviewGraph = (graph: Graph | null): null => {
  if (graph) {
    resizeObservers.get(graph)?.disconnect()
    resizeObservers.delete(graph)
    graph.destroy()
  }
  return null
}
