import type { AxiosError } from 'axios'
import { createEmptyModelSnapshot, EMPTY_MODEL_XML, type ModelSnapshot } from '@/model/ModelSnapshot'
import httpClient from '@/services/api/httpClient'
import type { JsonObject, LanguageVersionReference, TaskVersionReference } from '@/services/api/types/common'
import type { CreateModelVersion, Model, ModelPatch, ModelVersion, ModelVersionInfo, TaskEditDocument, WorkspaceLanguageReference } from '@/services/api/types/model'
import modelService from '@/services/model/model.service'
import taskService from '@/services/task/task.service'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { createJsonPatch } from '@/utils/jsonPatches'
import { applyModelPatches, createModelPatch } from '@/utils/modelPatches'
import { stripTaskEdits } from '@/utils/taskEdits'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, Workpiece } from '@/collab/kit/collabKitV1'
import { xmlOf, type ModelUnit } from '@/collab/converters/model/modelUnits'
import { marksOf, withMarks, type SharedMark, type SharedMarks } from '@/collab/converters/task/marks'
import { MARKS_MAP, taskLinkOf } from '@/collab/converters/task/taskLink'
import { CELLS_MAP, historyModeOf, linkOf } from '@/collab/storage/workpiece'
import { versionsOf } from '@/collab/storage/workpieceVersions'
import { sharedTaskEdit, sharedTaskReference } from '@/collab/worksheet/sharedTask'

/** The state of the room as this browser holds it now. */
export interface RoomState {
  xml: string
  languages: WorkspaceLanguageReference[]
}

/** One change of the marks of a room that changed them; notes change the same workpiece. */
interface RoomTaskStep {
  id: string
  createdAt: string
  marks: SharedMarks
}

/** What is read of the task of a room: its steps, and where the next read goes on. */
interface TaskRead {
  steps: RoomTaskStep[]
  marks: SharedMarks
  seen: string | null
}

/** What is read of a room for the way back: its versions, the changes after the last of them, and the task. */
interface RoomRead {
  versions: { info: ModelVersionInfo; xml: string }[]
  rest: ModelPatch[]
  task: TaskRead
}

const NOTHING: RoomRead = { versions: [], rest: [], task: { steps: [], marks: {}, seen: null } }

/** States read at once from collab-kit. */
const BATCH = 6
/** How often a visitor reads what the room added, as nothing can be read any more once the room is closed. */
const FOLLOW_MS = 30000

const xmlAt = async (ck: CollabKitApi, workpieceId: string, at?: string) => (at ? xmlOf((await ck.workpieces.unitsAt<ModelUnit>(workpieceId, { at, map: CELLS_MAP })).units) : null) ?? EMPTY_MODEL_XML

/** Reads the changes of the marks since the last read. */
const readTaskSteps = async (ck: CollabKitApi, workpieceId: string, read: TaskRead): Promise<TaskRead> => {
  const updates = await ck.workpieces.updates(workpieceId, read.seen ? { since: read.seen } : {})
  const steps = [...read.steps]
  let { marks, seen } = read
  for (let start = 0; start < updates.length; start += BATCH) {
    const batch = updates.slice(start, start + BATCH)
    const states = await Promise.all(batch.map((update) => ck.workpieces.unitsAt<SharedMark>(workpieceId, { at: update._id, map: MARKS_MAP })))
    batch.forEach((update, index) => {
      const next: SharedMarks = Object.fromEntries(states[index].units)
      if (JSON.stringify(next) !== JSON.stringify(marks)) steps.push({ id: update._id, createdAt: update.createdAt, marks: next })
      marks = next
      seen = update._id
    })
  }
  return { steps, marks, seen }
}

/** Reads what the room holds beyond `before`; states of versions read before are not read again. */
const readRoom = async (ck: CollabKitApi, linked: Model, workpiece: Workpiece, before: RoomRead): Promise<RoomRead> => {
  const room = await versionsOf(linked)?.roomHistory()
  if (!room) return before
  const known = new Map(before.versions.map(({ info, xml }) => [info.id, xml]))
  const versions: RoomRead['versions'] = []
  for (let start = 0; start < room.versions.length; start += BATCH) {
    const batch = room.versions.slice(start, start + BATCH)
    const states = await Promise.all(batch.map(({ info, at }) => known.get(info.id) ?? xmlAt(ck, workpiece._id, at)))
    batch.forEach(({ info }, index) => versions.push({ info, xml: states[index] }))
  }
  const link = taskLinkOf(workpiece)
  return { versions, rest: room.rest, task: link ? await readTaskSteps(ck, link.workpieceId, before.task) : before.task }
}

/** Writes the states of the marks as task edits, each laid over the plain text; a state equal to the one before is no edit. */
const publishTaskSteps = async (modelId: string, steps: readonly Pick<RoomTaskStep, 'createdAt' | 'marks'>[]): Promise<TaskEditDocument | null> => {
  const model = (await modelService.get(modelId)).data
  const reference = model.taskVersion
  if (!reference) return model.taskEdit
  const current = (await modelService.getTaskEdit(modelId)).data
  let before = current?.document ?? (await taskService.getVersion(reference.taskId, reference.versionId)).data.data.contentDocument
  if (!before) throw new Error('The task document has not finished loading.')
  const patches = steps.flatMap(({ createdAt, marks }) => {
    const previous: JsonObject = before as JsonObject
    const document = withMarks(stripTaskEdits(previous), marks)
    const operations = createJsonPatch(previous, document)
    if (!operations.length) return []
    before = document
    return [{ id: crypto.randomUUID(), createdAt, document, operations }]
  })
  return patches.length ? (await modelService.updateTaskEdit(modelId, { baseRevision: current?.revision ?? 0, patches })).data : current
}

/** The patches from the private state to a state of the room: those of the room while they lead there, else the whole difference. */
const patchesTo = (xml: string, target: string, patches: readonly ModelPatch[]): ModelPatch[] => {
  try {
    if (createModelPatch(applyModelPatches(xml, patches), target) === null) return [...patches]
  } catch {
    // They start from a state that differs from the private one; the whole difference does it then.
  }
  const whole = createModelPatch(xml, target)
  return whole ? [{ createdAt: patches[patches.length - 1]?.createdAt ?? new Date().toISOString(), xml: whole }] : []
}

/** The next version of `target`; without any before, it is its first release. */
const nextVersion = (target: Model, base: ModelVersion | null, edit: TaskEditDocument | null, xml: string, languages: WorkspaceLanguageReference[], { kind, releaseName, description, patches }: Pick<ModelVersionInfo, 'kind' | 'releaseName' | 'description' | 'patches'>): CreateModelVersion => {
  const shared = { baseVersionId: base?.id ?? null, taskEditVersionId: edit?.versionId ?? null, workspaceLanguages: languages, taskVersion: target.taskVersion, description }
  const data = { ...createEmptyModelSnapshot(target.name), xml }
  if (!base || kind === 'release') return { ...shared, baseReleaseId: null, data, patches: [], kind: 'release', releaseName: releaseName ?? 'Initial release' }
  // A checkpoint holds the state only as patches, as in the store.
  const withoutXml: JsonObject = { ...data }
  delete withoutXml.xml
  return { ...shared, baseReleaseId: base.kind === 'release' ? base.id : base.baseReleaseId, data: withoutXml, patches: patchesTo((base.data as ModelSnapshot).xml, xml, patches), kind: 'checkpoint' }
}

/**
 * Writes what the room holds into `target`, version by version, oldest first: first the task steps up
 * to a version, so the version points to them, then the version. What is left after the last version
 * ends as a checkpoint of its own, if it changes anything. `onVersion` tells how far it came.
 */
const writeRoomBack = async (target: Model, room: RoomRead, { xml, languages, marks }: RoomState & { marks: SharedMarks | null }, onVersion?: (checkpoint: string, taskUpdate: string | null) => Promise<unknown>) => {
  let base = target.latestVersionId ? (await modelService.getVersion(target, target.latestVersionId)).data : null
  let edit = target.taskEdit
  let nextStep = 0
  let taskUpdate: string | null = null
  const publishUpTo = async (time: number) => {
    const due: RoomTaskStep[] = []
    while (nextStep < room.task.steps.length && Date.parse(room.task.steps[nextStep].createdAt) <= time) {
      due.push(room.task.steps[nextStep])
      nextStep += 1
    }
    if (!due.length) return
    edit = await publishTaskSteps(target.id, due)
    taskUpdate = due[due.length - 1].id
  }

  for (const { info, xml: state } of room.versions) {
    await publishUpTo(Date.parse(info.createdAt))
    base = (await modelService.createVersion(target, nextVersion(target, base, edit, state, info.workspaceLanguages, info))).data
    await onVersion?.(info.id, taskUpdate)
  }

  await publishUpTo(Number.POSITIVE_INFINITY)
  if (marks) edit = await publishTaskSteps(target.id, [{ createdAt: new Date().toISOString(), marks }])
  const closing = nextVersion(target, base, edit, xml, languages, { kind: 'checkpoint', releaseName: null, description: null, patches: room.rest })
  // Nothing left: no empty version, so another try after a failure adds none either.
  const unchanged = base && !closing.patches?.length && JSON.stringify(base.workspaceLanguages) === JSON.stringify(languages) && (base.taskEditSnapshot?.versionId ?? null) === (edit?.versionId ?? null)
  if (!unchanged) await modelService.createVersion(target, closing)
  return target
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

/** Moves the boundary of the host's model past what the private model holds now, so it counts once and another try goes on after it. */
const moveBoundary = async (checkpoint: string, taskUpdate: string | null) => {
  const workspace = useModelWorkspaceStore()
  const link = linkOf(workspace.preferences)
  if (!link?.host) return
  await workspace.updatePreferences({ ...workspace.preferences, collab: { ...link, host: { ...link.host, checkpoint, taskUpdate: taskUpdate ?? link.host.taskUpdate } } })
}

/** Writes what the room added since sharing began into the host's private model, version by version. */
export const writeRoomToPrivateModel = async (privateModelId: string, workpieceId: string, state: RoomState) => {
  const ck = await loadCollabKit()
  const linked = useModelWorkspaceStore().model
  const host = linked ? linkOf(linked.preferences)?.host : undefined
  const workpiece = await ck.workpieces.get(workpieceId)
  const link = taskLinkOf(workpiece)
  let room = NOTHING
  if (linked && host) {
    // Only what came after the boundary is a step of the room; it starts from the marks there.
    const marks: SharedMarks = link && host.taskUpdate ? Object.fromEntries((await ck.workpieces.unitsAt<SharedMark>(link.workpieceId, { at: host.taskUpdate, map: MARKS_MAP })).units) : {}
    room = await readRoom(ck, linked, workpiece, { ...NOTHING, task: { steps: [], marks, seen: host.taskUpdate } })
  }
  const target = (await modelService.get(privateModelId)).data
  return writeRoomBack(target, room, { ...state, marks: await readTaskMarks(workpieceId) }, moveBoundary)
}

/** Saves the state of the room as a new model, with one release; a model of the new kind keeps the task, so it stays among the tasks. */
export const saveRoomAsNewModel = async (privateModelId: string, workpieceId: string, name: string, state: RoomState) => {
  const marks = await readTaskMarks(workpieceId)
  const reference = marks ? (await modelService.get(privateModelId)).data.taskVersion : null
  const model = (await modelService.create({ name, taskVersion: reference })).data
  return writeRoomBack(model, NOTHING, { ...state, marks })
}

// What a visitor has read of the room so far; reading it ends with the access, so it is kept here.
let followed: { linked: Model; workpiece: Workpiece } | null = null
let mirror = NOTHING
let reading: Promise<void> = Promise.resolve()

const readMirror = async () => {
  const room = followed
  if (!room) return
  reading = reading
    .catch(() => undefined)
    .then(async () => {
      mirror = await readRoom(await loadCollabKit(), room.linked, room.workpiece, mirror)
    })
  await reading
}

/**
 * Keeps reading the history the host has given the visitors, so a visitor can take it along even when
 * the room closes all at once. Without a history there is nothing to read and the state alone goes along.
 */
export const followRoomHistory = (linked: Model, workpieceId: string) => {
  let timer: ReturnType<typeof setTimeout> | null = null
  let stopped = false
  const round = async () => {
    await readMirror().catch(() => undefined)
    if (!stopped) timer = setTimeout(() => void round(), FOLLOW_MS)
  }
  const start = async () => {
    const workpiece = await (await loadCollabKit()).workpieces.get(workpieceId)
    if (stopped || historyModeOf(workpiece) === 'none') return
    followed = { linked, workpiece }
    await round()
  }
  void start().catch(() => undefined)
  return () => {
    stopped = true
    if (timer) clearTimeout(timer)
  }
}

/** Forgets what was read, once the visitor has left. */
export const forgetRoomHistory = () => {
  followed = null
  mirror = NOTHING
}

/** The own model of a visitor, with the task if the API lets this visitor have it. */
const createOwnModel = async (name: string, reference: TaskVersionReference | null) => {
  if (!reference) return (await modelService.create({ name, taskVersion: null })).data
  try {
    return (await modelService.create({ name, taskVersion: reference })).data
  } catch (error) {
    if ((error as AxiosError).response?.status !== 404) throw error
    return (await modelService.create({ name, taskVersion: null })).data
  }
}

/**
 * Makes an own model of what a visitor holds: the history read so far and, on top of it, the state of
 * this browser. Half a model is of no use to anyone, so it goes again if writing it fails.
 */
export const keepRoomAsOwnModel = async (name: string, state: RoomState) => {
  // Still in the room this reads what came last; once it is closed, what was read before has to do.
  await readMirror().catch(() => undefined)
  const edit = sharedTaskEdit.value
  const model = await createOwnModel(name, sharedTaskReference.value)
  try {
    return await writeRoomBack(model, mirror, { ...state, marks: edit ? marksOf(edit.document) : null })
  } catch (error) {
    await httpClient.delete(`/v1/models/${model.id}`).catch(() => undefined)
    throw error
  }
}

/** What a branch from the timeline of a room model takes of the task; the notice tells why it took none. */
export interface RoomBranchTask {
  reference: TaskVersionReference | null
  languages: WorkspaceLanguageReference[]
  taskEdit: TaskEditDocument | null
  notice: string | null
}

/**
 * Die Task eines Raums für einen Branch: die Freigabe, sofern die API sie dieser Person gibt und die
 * Pflichtsprachen im Stand stehen, dazu die Markierungen über ihrem Text. Null außerhalb eines Raums.
 * Ohne Freigabe oder mit abweichenden Sprachen wird der Branch ein Modell ohne Task, der Stand bleibt.
 */
export const roomBranchTask = async (languages: WorkspaceLanguageReference[], atPosition: TaskEditDocument | null): Promise<RoomBranchTask | null> => {
  const reference = sharedTaskReference.value
  if (!reference || useModelWorkspaceStore().taskVersion) return null
  const without: RoomBranchTask = { reference: null, languages, taskEdit: null, notice: 'The task could not be taken along; the copy is a model without task.' }
  let version
  try {
    version = (await taskService.getVersion(reference.taskId, reference.versionId)).data
  } catch (error) {
    if ((error as AxiosError).response?.status !== 404) throw error
    return without
  }
  const required = version.workspaceLanguages.filter((language) => language.source === 'required')
  const isRequired = (language: LanguageVersionReference) => required.some((item) => item.languageId === language.languageId && item.versionId === language.versionId)
  if (!required.every((item) => languages.some((language) => language.languageId === item.languageId && language.versionId === item.versionId))) return without
  // Die Markierungen der Gruppe über dem Text der Freigabe, wie beim Behalten (publishTaskSteps).
  const edit = atPosition ?? sharedTaskEdit.value
  const base = version.data.contentDocument
  return {
    reference,
    languages: languages.map((language) => ({ ...language, source: isRequired(language) ? 'required' : 'additional' })),
    taskEdit: edit && base ? { ...edit, document: withMarks(stripTaskEdits(base), marksOf(edit.document)) } : null,
    notice: null
  }
}
