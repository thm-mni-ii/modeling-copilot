import { InternalEvent, type Graph } from '@maxgraph/core'

/** Calls onChange after every completed model change; returns the function that stops it. */
export const watchGraphChanges = (graph: Graph, onChange: (cellCount: number) => void) => {
  const model = graph.getDataModel()
  const listener = () => {
    const root = model.getRoot()
    onChange(root ? root.filterDescendants((cell) => cell.isVertex() || cell.isEdge()).length : 0)
  }
  model.addListener(InternalEvent.CHANGE, listener)
  return () => model.removeListener(listener)
}
