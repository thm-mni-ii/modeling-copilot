import type { JsonObject } from '@/services/api/types/common'
import type { UnitChange } from '@/collab/kit/collabKitV1'
import { marksOf, type SharedMark, type SharedMarks } from './marks'

/** A state of the private task: its revision, when it came about, and the document. */
export interface PrivateTaskState {
  revision: number
  createdAt: string
  document: JsonObject
}

/** One change to write into the marks, with what is needed to bring it in order with the steps of the model. */
export interface TaskHistoryStep {
  change: UnitChange<SharedMark>
  revision: number
  createdAt: string
}

/** The marks that change from one state to the next, as a change of the units. */
const changeOf = (before: SharedMarks, after: SharedMarks) => {
  const set: SharedMarks = {}
  for (const [id, mark] of Object.entries(after)) if (JSON.stringify(mark) !== JSON.stringify(before[id])) set[id] = mark
  return { set, delete: Object.keys(before).filter((id) => !(id in after)) }
}

/** The private states of the task as steps for a new workpiece, oldest first; a state equal to the one before is no step. */
export const taskStepsOf = (states: readonly PrivateTaskState[]): TaskHistoryStep[] => {
  let previous: SharedMarks = {}
  return states.flatMap(({ revision, createdAt, document }) => {
    const marks = marksOf(document)
    const change = changeOf(previous, marks)
    previous = marks
    return Object.keys(change.set).length || change.delete.length ? [{ change, revision, createdAt }] : []
  })
}
