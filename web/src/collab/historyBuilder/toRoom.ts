import { notifyWarning } from '@/composables/useNotifications'
import type { ModelSnapshot } from '@/model/ModelSnapshot'
import modelService from '@/services/model/model.service'
import type { JsonObject } from '@/services/api/types/common'
import type { Model, WorkspaceLanguageReference } from '@/services/api/types/model'
import { stripTaskEdits } from '@/utils/taskEdits'
import { loadTaskEditHistory } from '@/utils/taskEditTimeline'
import type { CollabKitApi, Session, UnitChange, Workpiece } from '@/collab/kit/collabKitV1'
import { hasChange, stepsOf, type HistoryMode, type HistoryStep, type PrivateVersion } from '@/collab/converters/model/modelHistory'
import { sameUnits, type ModelUnit } from '@/collab/converters/model/modelUnits'
import type { SharedMark } from '@/collab/converters/task/marks'
import { taskStepsOf, type PrivateTaskState, type TaskHistoryStep } from '@/collab/converters/task/taskHistory'
import { MARKS_MAP, taskLinkOf } from '@/collab/converters/task/taskLink'
import { baseOf } from '@/collab/sharing/shareTask'
import { CELLS_MAP, type HostLink } from '@/collab/storage/workpiece'

/** What the host shares: the private model, how much of its history, and the state as it is now. */
export interface ShareSource {
  model: Model
  mode: HistoryMode
  xml: string
  languages: WorkspaceLanguageReference[]
  /** The task as the host has it now, if it comes along and was marked. */
  task: { document: JsonObject; contentHtml: string } | null
}

/** One thing to write, in the order of the private history. */
type PlanItem = { target: 'model'; change: UnitChange<ModelUnit> } | { target: 'task'; change: UnitChange<SharedMark> } | { target: 'checkpoint'; checkpoint: NonNullable<HistoryStep['checkpoint']> }

/** The versions read at once from the API, and per page. */
const BATCH = 6
const PAGE = 100

/** How often collab-kit is asked whether it holds what was written, and for how long. */
const POLL_MS = 50
const WAIT_MS = 10000

const pause = () => new Promise((resolve) => setTimeout(resolve, POLL_MS))

/** The versions of the private model with their whole state and task state, oldest first. */
const readPrivateVersions = async (model: Model): Promise<PrivateVersion[]> => {
  const ids: string[] = []
  for (let total = 1; ids.length < total; ) {
    const { items, total: all } = (await modelService.listVersions(model, ids.length, PAGE)).data
    if (items.length === 0) break
    ids.push(...items.map((item) => item.id))
    total = all
  }
  // The API lists the newest first; a version builds on the one before it.
  ids.reverse()
  const versions: PrivateVersion[] = []
  for (let start = 0; start < ids.length; start += BATCH) {
    const batch = await Promise.all(ids.slice(start, start + BATCH).map((id) => modelService.getVersion(model, id)))
    for (const { data } of batch) versions.push({ info: data, xml: (data.data as ModelSnapshot).xml, task: data.taskEditSnapshot })
  }
  return versions
}

const textOf = (node: JsonObject): string => (typeof node.text === 'string' ? node.text : ((node.content as JsonObject[] | undefined) ?? []).map(textOf).join(''))

/**
 * The states of the task the mode asks for: only the one now, one per version, or every step. The state
 * now comes last. Marks and insertions go in by edit ID, while the CK task keeps the plain text, so their
 * offsets only fit if both texts are the same. If this fails the model is shared without the edits.
 */
const readTaskStates = async (model: Model, mode: HistoryMode, versions: readonly PrivateVersion[], { document, contentHtml }: NonNullable<ShareSource['task']>): Promise<PrivateTaskState[]> => {
  try {
    if (textOf(stripTaskEdits(document)) !== textOf(baseOf(contentHtml))) throw new Error('The text of the task differs from the shared one.')
    const now: PrivateTaskState = { revision: Number.POSITIVE_INFINITY, createdAt: new Date().toISOString(), document }
    if (mode === 'none') return [now]
    if (mode === 'versions') return [...versions.flatMap(({ task }) => (task ? [{ revision: task.revision, createdAt: task.updatedAt, document: task.document }] : [])), now]
    const history = await loadTaskEditHistory(model.id)
    const states: PrivateTaskState[] = []
    for (let start = 0; start < history.length; start += BATCH) {
      const batch = history.slice(start, start + BATCH)
      const read = await Promise.all(batch.map((step) => modelService.getTaskEditVersion(model.id, step.id)))
      batch.forEach(({ revision, createdAt }, index) => states.push({ revision, createdAt, document: read[index].data.document }))
    }
    return [...states, now]
  } catch (error) {
    notifyWarning(`The task edits could not be shared: ${(error as Error).message}`)
    return []
  }
}

/**
 * Model and task steps in one order, so that the times collab-kit gives them keep the order they had
 * privately. Within a version they go by time, as the timeline sorts them; before a checkpoint come
 * all task steps up to the revision of its version, so the state it marks is the one the version had.
 */
const planOf = (modelSteps: readonly HistoryStep[], taskSteps: readonly TaskHistoryStep[]) => {
  const plan: PlanItem[] = []
  let next = 0
  const takeTaskSteps = (due: (step: TaskHistoryStep) => boolean) => {
    while (next < taskSteps.length && due(taskSteps[next])) {
      plan.push({ target: 'task', change: taskSteps[next].change })
      next += 1
    }
  }
  for (const step of modelSteps) {
    takeTaskSteps((task) => task.revision <= step.taskRevision && Date.parse(task.createdAt) <= Date.parse(step.createdAt))
    if (hasChange(step.change)) plan.push({ target: 'model', change: step.change })
    if (step.checkpoint) {
      takeTaskSteps((task) => task.revision <= step.taskRevision)
      plan.push({ target: 'checkpoint', checkpoint: step.checkpoint })
    }
  }
  takeTaskSteps(() => true)
  return plan
}

/** Waits until collab-kit holds every unit the session has, so a checkpoint marks exactly that state. */
const waitUntilHeld = async <Value>(ck: CollabKitApi, session: Session<Value>, map: string) => {
  const until = Date.now() + WAIT_MS
  while (!sameUnits((await ck.workpieces.unitsAt<Value>(session.workpieceId, { map })).units, session.units.entries())) {
    if (Date.now() > until) throw new Error('collab-kit did not take the history in time.')
    await pause()
  }
}

/**
 * Writes the plan into the new workpieces before anyone joins, out of undo, so the host cannot take the
 * history back. On changing workpiece it waits until collab-kit holds the last one, or the order of the
 * times could turn around.
 */
const writePlan = async (ck: CollabKitApi, workpieceId: string, taskWorkpieceId: string | null, plan: readonly PlanItem[], onProgress?: (done: number, total: number) => void) => {
  const model = ck.open<ModelUnit>(workpieceId, { map: CELLS_MAP })
  const task = taskWorkpieceId ? ck.open<SharedMark>(taskWorkpieceId, { map: MARKS_MAP }) : null
  const modelHeld = () => waitUntilHeld(ck, model, CELLS_MAP)
  const taskHeld = () => (task ? waitUntilHeld(ck, task, MARKS_MAP) : Promise.resolve())
  try {
    await Promise.all([model.synced, task?.synced])
    onProgress?.(0, plan.length)
    let last: 'model' | 'task' | null = null
    for (const [index, item] of plan.entries()) {
      if (item.target === 'task') {
        if (last === 'model') await modelHeld()
        task?.units.update(item.change, { undoable: false })
        last = 'task'
      } else {
        if (last === 'task') await taskHeld()
        last = 'model'
        if (item.target === 'model') model.units.update(item.change, { undoable: false })
        else {
          await modelHeld()
          await ck.workpieces.checkpoint(workpieceId, item.checkpoint)
        }
      }
      onProgress?.(index + 1, plan.length)
    }
    // The sessions may close only once collab-kit holds the last of it.
    await Promise.all([modelHeld(), taskHeld()])
  } finally {
    model.close()
    task?.close()
  }
}

/**
 * Builds the private history in the new workpieces, as much of it as the mode asks for. Only for a new
 * share: the workpiece of a share that goes on holds the live state.
 */
export const buildRoomHistory = async (ck: CollabKitApi, workpiece: Workpiece, { model, mode, xml, languages, task }: ShareSource, onProgress?: (done: number, total: number) => void) => {
  const versions = mode === 'none' ? [] : await readPrivateVersions(model)
  const link = taskLinkOf(workpiece)
  const taskStates = link && task ? await readTaskStates(model, mode, versions, task) : []
  await writePlan(ck, workpiece._id, link?.workpieceId ?? null, planOf(stepsOf(versions, mode, { xml, languages }), taskStepsOf(taskStates)), onProgress)
}

/** Where the history of the room starts, so the host's own model shows the private history before it and the room's after it. */
export const roomHistoryStart = async (ck: CollabKitApi, workpiece: Workpiece): Promise<Pick<HostLink, 'checkpoint' | 'taskUpdate'>> => {
  const checkpoints = await ck.events.list({ anchorKind: 'workpiece', anchorId: workpiece._id, kind: 'checkpoint' })
  const link = taskLinkOf(workpiece)
  const taskUpdates = link ? await ck.workpieces.updates(link.workpieceId) : []
  return { checkpoint: checkpoints[0]?._id ?? null, taskUpdate: taskUpdates[taskUpdates.length - 1]?._id ?? null }
}
