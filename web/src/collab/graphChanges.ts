import { InternalEvent, type Graph } from '@maxgraph/core'

/** Vertices and edges of the model, without its root and layers. */
export const countCells = (graph: Graph) => {
  const root = graph.getDataModel().getRoot()
  return root ? root.filterDescendants((cell) => cell.isVertex() || cell.isEdge()).length : 0
}

/** Calls onChange after every completed model change; returns the function that stops it. */
export const watchGraphChanges = (graph: Graph, onChange: (cellCount: number) => void) => {
  const model = graph.getDataModel()
  const listener = () => onChange(countCells(graph))
  model.addListener(InternalEvent.CHANGE, listener)
  return () => model.removeListener(listener)
}
