import { Editor as CoreEditor } from '@tiptap/core'
import modelService from '@/services/model/model.service'
import taskService from '@/services/task/task.service'
import type { JsonObject } from '@/services/api/types/common'
import type { TaskEditDocument } from '@/services/api/types/model'
import { createTaskEditExtensions } from '@/components/tasks/taskEditMarks'
import { createJsonPatch } from '@/utils/jsonPatches'
import { stripTaskEdits } from '@/utils/taskEdits'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, Workpiece } from '@/collab/kit/collabKitV1'
import { marksOf, withMarks, type SharedMark, type SharedMarks } from '@/collab/converters/task/marks'
import { MARKS_MAP, taskLinkOf } from '@/collab/converters/task/taskLink'

const WAIT_MS = 10000
const POLL_MS = 200
const pause = () => new Promise((resolve) => setTimeout(resolve, POLL_MS))

/** The text as the editor reads it, with the same marks, so offsets count the same way everywhere. */
export const baseOf = (html: string): JsonObject => {
  const parser = new CoreEditor({ content: html, editable: false, extensions: createTaskEditExtensions() })
  const parsed = parser.getJSON() as JsonObject
  parser.destroy()
  return parsed
}

const textOf = (node: JsonObject): string => (typeof node.text === 'string' ? node.text : ((node.content as JsonObject[] | undefined) ?? []).map(textOf).join(''))

/** Waits until collab-kit holds the marks the session has. */
const waitUntilHeld = async (ck: CollabKitApi, workpieceId: string, own: [string, SharedMark][]) => {
  const until = Date.now() + WAIT_MS
  for (;;) {
    const stored = (await ck.workpieces.unitsAt<SharedMark>(workpieceId, { map: MARKS_MAP })).units
    if (stored.size === own.length && own.every(([key, mark]) => JSON.stringify(stored.get(key)) === JSON.stringify(mark))) return
    if (Date.now() > until) throw new Error('collab-kit did not take the task marks in time.')
    await pause()
  }
}

/**
 * The private edits of the task go into the marks of the room: marks and insertions by edit ID, while
 * the CK task keeps the plain text. Only for a new share, the workpiece of a share that goes on holds the live state.
 */
export const writeTaskMarks = async (ck: CollabKitApi, workpiece: Workpiece, edit: JsonObject, contentHtml: string) => {
  const link = taskLinkOf(workpiece)
  const marks = marksOf(edit)
  if (!link || !Object.keys(marks).length) return
  // The offsets only fit if the private text is the text of the CK task.
  if (textOf(stripTaskEdits(edit)) !== textOf(baseOf(contentHtml))) throw new Error('The text of the task differs from the shared one.')
  const session = ck.open<SharedMark>(link.workpieceId, { map: MARKS_MAP })
  try {
    await session.synced
    // Out of undo, so the host cannot take the edits back.
    session.units.update({ set: marks }, { undoable: false })
    await waitUntilHeld(ck, link.workpieceId, Object.entries(marks))
  } finally {
    session.close()
  }
}

/** The marks of the task of the room as everyone made them; null if no task is shared. */
export const readTaskMarks = async (modelWorkpieceId: string): Promise<SharedMarks | null> => {
  const ck = await loadCollabKit()
  const link = taskLinkOf(await ck.workpieces.get(modelWorkpieceId))
  if (!link) return null
  const session = ck.open<SharedMark>(link.workpieceId, { map: MARKS_MAP })
  try {
    await session.synced
    return Object.fromEntries(session.units.entries())
  } finally {
    session.close()
  }
}

/** Lays the marks over the plain text of the task of the model and saves the difference as its task edit. */
export const saveTaskMarks = async (modelId: string, marks: SharedMarks): Promise<TaskEditDocument | null> => {
  const model = (await modelService.get(modelId)).data
  const reference = model.taskVersion
  if (!reference) return model.taskEdit
  const current = (await modelService.getTaskEdit(modelId)).data
  const before = current?.document ?? (await taskService.getVersion(reference.taskId, reference.versionId)).data.data.contentDocument
  if (!before) throw new Error('The task document has not finished loading.')
  const after = withMarks(stripTaskEdits(before), marks)
  const operations = createJsonPatch(before, after)
  if (!operations.length) return current
  const patch = { id: crypto.randomUUID(), createdAt: new Date().toISOString(), document: after, operations }
  return (await modelService.updateTaskEdit(modelId, { baseRevision: current?.revision ?? 0, patches: [patch] })).data
}
