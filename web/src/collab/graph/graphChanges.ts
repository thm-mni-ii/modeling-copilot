import { InternalEvent, RootChange, type EventObject, type Graph, type UndoableEdit } from '@maxgraph/core'

/**
 * Calls onChange after every completed model change, telling whether the whole model was swapped,
 * as when a model is loaded, and with the edit, which tells an undo or redo; returns the function
 * that stops it.
 */
export const watchGraphChanges = (graph: Graph, onChange: (replaced: boolean, edit: UndoableEdit | undefined) => void) => {
  const model = graph.getDataModel()
  const listener = (_sender: unknown, event: EventObject) => {
    const changes: unknown[] = event.getProperty('changes') ?? []
    onChange(
      changes.some((change) => change instanceof RootChange),
      event.getProperty('edit')
    )
  }
  model.addListener(InternalEvent.CHANGE, listener)
  return () => model.removeListener(listener)
}
