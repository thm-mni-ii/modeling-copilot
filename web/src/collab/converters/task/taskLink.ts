import type { Workpiece } from '@/collab/kit/collabKitV1'

/** The format in the contract of the task workpiece, as the backend creates it. */
export const TASK_FORMAT = 'copilot-task'
/** The map of the task workpiece holding one mark per edit ID, as the backend names it. */
export const MARKS_MAP = 'marks'
/** The shared text of the task workpiece holding the notes below the task. */
export const NOTES_TEXT = 'notes'

/** Where the model workpiece finds its task: the workpiece of marks and notes, and the fixed text as a CK task. */
export interface TaskLink {
  workpieceId: string
  taskId: string
}

/** The task shared along with the model, if the host shared one; the contract never changes. */
export const taskLinkOf = (workpiece: Workpiece): TaskLink | null => {
  const link = workpiece.contract.task as Partial<TaskLink> | undefined
  return typeof link?.workpieceId === 'string' && typeof link.taskId === 'string' ? { workpieceId: link.workpieceId, taskId: link.taskId } : null
}
