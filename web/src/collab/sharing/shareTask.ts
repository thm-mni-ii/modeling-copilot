import { Editor as CoreEditor } from '@tiptap/core'
import modelService from '@/services/model/model.service'
import type { JsonObject } from '@/services/api/types/common'
import type { TaskEditChange, TaskEditVersionInfo } from '@/services/api/types/model'
import { createTaskEditExtensions } from '@/components/tasks/taskEditMarks'
import { collectTaskEdits, TASK_EDIT_MARKS } from '@/utils/taskEdits'
import { loadTaskEditHistory } from '@/utils/taskEditTimeline'
import type { CollabKitApi } from '@/collab/kit/collabKitV1'
import { withMarks, type SharedMark, type SharedMarks } from '@/collab/converters/task/marks'
import { MARKS_MAP } from '@/collab/converters/task/taskLink'
import type { TaskHistorySource } from '@/collab/worksheet/sharedTask'

/** States read at once while catching up on the task history. */
const BATCH = 6

/** The text as the editor reads it, with the same marks, so offsets count the same way everywhere. */
export const baseOf = (html: string): JsonObject => {
  const parser = new CoreEditor({ content: html, editable: false, extensions: createTaskEditExtensions() })
  const parsed = parser.getJSON() as JsonObject
  parser.destroy()
  return parsed
}

/** The step of a task of a room as the dialogs of the private history read it. */
interface Step {
  info: TaskEditVersionInfo
  document: JsonObject
}

const textOfEdit = (document: JsonObject, id: string) => collectTaskEdits(document).find((entry) => entry.id === id)?.fragments[0]?.text ?? ''

const changesBetween = (before: SharedMarks, after: SharedMarks, previous: JsonObject, document: JsonObject): TaskEditChange[] =>
  [...new Set([...Object.keys(before), ...Object.keys(after)])].flatMap((id): TaskEditChange[] => {
    if (JSON.stringify(before[id]) === JSON.stringify(after[id])) return []
    const entry = after[id] ?? before[id]
    const editType = entry.mark === 'insertion' ? 'insertion' : TASK_EDIT_MARKS[entry.mark as keyof typeof TASK_EDIT_MARKS]
    return [{ kind: !before[id] ? 'create' : !after[id] ? 'remove' : 'update', editId: id, editType, text: textOfEdit(after[id] ? document : previous, id) }]
  })

/**
 * The history of the task of a room, read from the changes of its marks the way the model history is
 * read from the changes of its cells. Notes change the same workpiece, so a change that leaves the
 * marks as they were is no step. `restore` takes a state as the current one. For the host, `host` gives
 * the private model whose history comes first and the change after which the history of the room begins;
 * asked anew each time, as the way back into the private model moves it.
 */
export const taskHistoryOf = (ck: CollabKitApi, workpieceId: string, base: JsonObject, contentHtml: string, restore: (document: JsonObject) => void, host?: () => { modelId: string; after: string | null } | undefined): TaskHistorySource => {
  const steps: Step[] = []
  let marks: SharedMarks = {}
  let document: JsonObject = base
  let since: string | undefined
  // One read after the other, as two dialogs may ask at once.
  let reading: Promise<void> = Promise.resolve()
  const read = () => {
    reading = reading
      .catch(() => undefined)
      .then(async () => {
        const updates = await ck.workpieces.updates(workpieceId, since ? { since } : {})
        for (let start = 0; start < updates.length; start += BATCH) {
          const batch = updates.slice(start, start + BATCH)
          const states = await Promise.all(batch.map((update) => ck.workpieces.unitsAt<SharedMark>(workpieceId, { at: update._id, map: MARKS_MAP })))
          batch.forEach((update, index) => {
            since = update._id
            const next: SharedMarks = Object.fromEntries(states[index].units)
            const nextDocument = withMarks(base, next)
            const changes = changesBetween(marks, next, document, nextDocument)
            if (changes.length) steps.push({ info: { id: update._id, revision: steps.length + 1, createdAt: update.createdAt, savedAt: update.createdAt, changes }, document: nextDocument })
            marks = next
            document = nextDocument
          })
        }
      })
    return reading
  }
  return {
    contentHtml,
    contentDocument: base,
    list: async () => {
      await read()
      const own = host?.()
      const before = own ? await loadTaskEditHistory(own.modelId) : []
      const offset = before[before.length - 1]?.revision ?? 0
      // What came before the boundary is in the private history, not a step of the room; update IDs grow with time.
      const after = own?.after
      const room = after ? steps.filter((step) => step.info.id > after) : steps
      return [...before, ...room.map((step, index) => ({ ...step.info, revision: offset + index + 1 }))]
    },
    document: async (id) => {
      // A step read before needs no new look at the changes.
      let step = steps.find((item) => item.info.id === id)
      if (!step) {
        await read()
        step = steps.find((item) => item.info.id === id)
      }
      if (step) return { schemaVersion: 1, revision: step.info.revision, updatedAt: step.info.createdAt, document: step.document }
      const own = host?.()
      if (own) return (await modelService.getTaskEditVersion(own.modelId, id)).data
      throw new Error('This task state could not be found.')
    },
    restore
  }
}
