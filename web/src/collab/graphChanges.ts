import { InternalEvent, RootChange, type EventObject, type Graph } from '@maxgraph/core'

/** Vertices and edges of the model, without its root and layers. */
export const countCells = (graph: Graph) => {
  const root = graph.getDataModel().getRoot()
  return root ? root.filterDescendants((cell) => cell.isVertex() || cell.isEdge()).length : 0
}

/**
 * Calls onChange after every completed model change, telling whether the whole model was swapped,
 * as when a model is loaded; returns the function that stops it.
 */
export const watchGraphChanges = (graph: Graph, onChange: (cellCount: number, replaced: boolean) => void) => {
  const model = graph.getDataModel()
  const listener = (_sender: unknown, event: EventObject) => {
    const changes: unknown[] = event.getProperty('changes') ?? []
    onChange(
      countCells(graph),
      changes.some((change) => change instanceof RootChange)
    )
  }
  model.addListener(InternalEvent.CHANGE, listener)
  return () => model.removeListener(listener)
}
