import type { ApiId, ApiPage } from '@/services/api/types/common'
import type { CreateModelVersion, Model, ModelPatch, ModelVersion, ModelVersionInfo, WorkspaceLanguageReference } from '@/services/api/types/model'
import httpClient from '@/services/api/httpClient'
import { createEmptyModelSnapshot, EMPTY_MODEL_XML } from '@/model/ModelSnapshot'
import { createModelPatch } from '@/utils/modelPatches'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabEvent, CollabKitApi, Workpiece } from '@/collab/kit/collabKitV1'
import { liveSession } from '@/collab/kit/liveSession'
import { languagesIn, sameUnits, xmlOf, type ModelUnit } from '@/collab/converters/model/modelUnits'
import { sharedTaskHistory } from '@/collab/worksheet/sharedTask'
import { CELLS_MAP, languagesOf, linkOf } from './workpiece'

/** The version methods of model.service for a model shared through a workpiece, in the shapes of the API. */
export interface ModelVersions {
  listVersions(skip: number, limit: number): Promise<{ data: ApiPage<ModelVersionInfo> }>
  /** Left out, the latest version with the newest state of collab-kit. */
  getVersion(versionId?: ApiId | null): Promise<{ data: ModelVersion }>
  createVersion(version: CreateModelVersion): Promise<{ data: ModelVersion }>
  /** What the room holds for the way back: its versions with the change each stands at, and the changes after the last of them. */
  roomHistory(): Promise<{ versions: Entry[]; rest: ModelPatch[] }>
}

/** The release every shared model starts from; never stored, so all own models of the workpiece share it. */
const INITIAL = 'initial'
/** States read at once while catching up on the stored changes. */
const BATCH = 6
/** How often and how long a checkpoint waits for collab-kit to hold the own changes. */
const ATTEMPTS = 10
const PAUSE_MS = 200

/** One stored change: when, what it did to the cells, and the languages after it. */
interface Step {
  id: string
  createdAt: string
  patch: string | null
  languages: WorkspaceLanguageReference[]
}

/** What is read of one workpiece; stored changes never change, so it only grows. */
interface History {
  workpiece: Workpiece
  steps: Step[]
  /** The model XML after the last step, the base of the next patch. */
  xml: string
}

/** A version and the change it stands at; none for the initial release. */
export interface Entry {
  info: ModelVersionInfo
  at?: string
}

const histories = new Map<string, History>()
const reads = new Map<string, Promise<History>>()

/** Reads the changes stored since the last read, a batch of states at a time; one read per workpiece after the other. */
const historyOf = (ck: CollabKitApi, workpieceId: string) => {
  const read = (reads.get(workpieceId) ?? Promise.resolve())
    .catch(() => undefined)
    .then(async () => {
      const history = histories.get(workpieceId) ?? { workpiece: await ck.workpieces.get(workpieceId), steps: [], xml: EMPTY_MODEL_XML }
      histories.set(workpieceId, history)
      const since = history.steps[history.steps.length - 1]?.id
      const updates = await ck.workpieces.updates(workpieceId, since ? { since } : {})
      for (let start = 0; start < updates.length; start += BATCH) {
        const batch = updates.slice(start, start + BATCH)
        const states = await Promise.all(batch.map((update) => ck.workpieces.unitsAt<ModelUnit>(workpieceId, { at: update._id, map: CELLS_MAP })))
        batch.forEach((update, index) => {
          const { units } = states[index]
          const xml = xmlOf(units) ?? EMPTY_MODEL_XML
          history.steps.push({ id: update._id, createdAt: update.createdAt, patch: createModelPatch(history.xml, xml), languages: languagesIn(units, history.workpiece) })
          history.xml = xml
        })
      }
      return history
    })
  reads.set(workpieceId, read)
  return read
}

/** The number after the one before, as the API counts: a checkpoint counts on, a release begins the next. */
const nextNumber = (previous: string, release: boolean) => {
  const [major = 0, minor = 0] = previous.split('.').map(Number)
  return release ? `${major + 1}.0` : `${Math.max(major, 1)}.${minor + 1}`
}

const initialOf = (model: Model, workpiece: Workpiece): ModelVersionInfo => ({
  id: INITIAL,
  versionNumber: '1.0',
  createdAt: workpiece.createdAt,
  createdBy: workpiece.createdBy,
  modelId: model.id,
  baseReleaseId: null,
  patches: [],
  workspaceLanguages: languagesOf(workpiece),
  taskVersion: null,
  kind: 'release',
  releaseName: 'Initial release',
  description: null
})

/** The versions oldest first: the initial release, then one per checkpoint with the changes since the one before. A workpiece given the private history starts with its first checkpoint, as release 1.0, and has no empty initial release. `done` tells how many stored changes they take up. */
const entriesOf = (model: Model, history: History, checkpoints: readonly CollabEvent[], host?: { base: ModelVersionInfo | null; since: string | null }) => {
  // A workpiece made with a history mode starts with its first checkpoint; without one, with the empty initial release.
  const given = history.workpiece.contract.history !== undefined && checkpoints.length > 0
  const entries: Entry[] = host || given ? [] : [{ info: initialOf(model, history.workpiece) }]
  let done = 0
  // The host's own model: what came before sharing is in the private model, so only the checkpoints after it are the room's.
  const sinceIndex = host?.since ? checkpoints.findIndex((checkpoint) => checkpoint._id === host.since) : -1
  if (sinceIndex >= 0) {
    const at = checkpoints[sinceIndex].at
    done = at ? history.steps.findIndex((step) => step.id === at) + 1 : 0
  }
  for (const checkpoint of checkpoints.slice(sinceIndex + 1)) {
    const before = entries[entries.length - 1]?.info ?? host?.base ?? undefined
    const release = Boolean(checkpoint.label)
    const end = checkpoint.at ? history.steps.findIndex((step) => step.id === checkpoint.at) + 1 : 0
    const steps = history.steps.slice(done, end)
    done = Math.max(done, end)
    entries.push({
      at: checkpoint.at,
      info: {
        id: checkpoint._id,
        versionNumber: nextNumber(before?.versionNumber ?? '0.0', release),
        createdAt: checkpoint.createdAt,
        createdBy: checkpoint.createdBy,
        modelId: model.id,
        baseReleaseId: release || !before ? null : before.kind === 'release' ? before.id : before.baseReleaseId,
        // A release holds its whole state; what others changed since the last checkpoint is in it, not shown as steps.
        patches: release ? [] : steps.flatMap((step) => (step.patch ? [{ createdAt: step.createdAt, xml: step.patch }] : [])),
        workspaceLanguages: end > 0 ? history.steps[end - 1].languages : languagesOf(history.workpiece),
        taskVersion: null,
        kind: release ? 'release' : 'checkpoint',
        releaseName: checkpoint.label ?? null,
        description: checkpoint.reason ?? null
      }
    })
  }
  return { entries, done }
}

/** The task state of a room when a version was made, so the timeline shows it as it does for a private version; null if none is shown or it has none. */
const taskStateAt = async (createdAt: string) => {
  const source = sharedTaskHistory.value
  if (!source) return null
  try {
    const time = Date.parse(createdAt)
    const before = (await source.list()).filter((step) => Date.parse(step.createdAt) <= time)
    return before.length ? await source.document(before[before.length - 1].id) : null
  } catch {
    return null
  }
}

/** The version with a state of the workpiece and its languages; without one, the empty model. */
const withState = (model: Model, workpiece: Workpiece, info: ModelVersionInfo, units?: ReadonlyMap<string, ModelUnit>): ModelVersion => ({
  ...info,
  data: { ...createEmptyModelSnapshot(model.name), xml: (units && xmlOf(units)) ?? EMPTY_MODEL_XML },
  workspaceLanguages: units ? languagesIn(units, workpiece) : info.workspaceLanguages,
  // The room shows its task as a CK task; the newest private version must not make the store load the private one.
  taskVersion: null,
  taskEditSnapshot: null
})

const pause = () => new Promise((resolve) => setTimeout(resolve, PAUSE_MS))

/** The adapter of a model shared through a workpiece; null for a model the API keeps. */
export const versionsOf = (model: Model): ModelVersions | null => {
  const link = linkOf(model.preferences)
  if (!link) return null
  const { workpieceId, host } = link

  // The host's own model shows the whole history: the versions of the private model it comes from, then what the room added.
  const privatePage = async (skip: number, limit: number) => (await httpClient.get<ApiPage<ModelVersionInfo>>(`/v1/models/${host!.modelId}/versions`, { params: { skip, limit } })).data
  const privateAll = async () => {
    const items: ModelVersionInfo[] = []
    for (let total = 1; items.length < total; ) {
      const page = await privatePage(items.length, 100)
      if (page.items.length === 0) break
      items.push(...page.items)
      total = page.total
    }
    return items
  }
  const privateNewest = async () => (host ? (await privatePage(0, 1)).items[0] ?? null : null)
  // The newest version: the last of the room, or the private model's if the room made none.
  const latestOf = async (entries: readonly Entry[]) => entries[entries.length - 1]?.info ?? (await privateNewest())

  const stateAt = async (at?: string) => (await (await loadCollabKit()).workpieces.unitsAt<ModelUnit>(workpieceId, { at, map: CELLS_MAP })).units

  // Checkpoints first, so the history read after reaches every change they stand at. Only the list
  // needs the patches; a single version reads just its own state, so opening a model stays quick.
  const read = async (withPatches: boolean) => {
    const ck = await loadCollabKit()
    const checkpoints = (await ck.events.list({ anchorKind: 'workpiece', anchorId: workpieceId, kind: 'checkpoint' })).reverse()
    const history = withPatches ? await historyOf(ck, workpieceId) : { workpiece: histories.get(workpieceId)?.workpiece ?? (await ck.workpieces.get(workpieceId)), steps: [], xml: EMPTY_MODEL_XML }
    const { entries, done } = entriesOf(model, history, checkpoints, host ? { base: await privateNewest(), since: host.checkpoint } : undefined)
    return { workpiece: history.workpiece, entries, rest: history.steps.slice(done) }
  }

  const versionAt = async (workpiece: Workpiece, { info, at }: Entry) => withState(model, workpiece, info, at ? await stateAt(at) : undefined)

  // Every change is stored as it is made; a checkpoint only marks where collab-kit stands, once it holds the own ones.
  const mark = async (version: CreateModelVersion) => {
    const session = liveSession<ModelUnit>(workpieceId)
    if (!session || session.status !== 'connected') throw new Error('Not connected to collab-kit.')
    for (let attempt = 0; attempt < ATTEMPTS; attempt += 1) {
      if (sameUnits(await stateAt(), session.units.entries())) break
      await pause()
    }
    const ck = await loadCollabKit()
    return ck.workpieces.checkpoint(workpieceId, version.kind === 'release' ? { label: version.releaseName ?? undefined, reason: version.description ?? undefined } : {})
  }

  return {
    listVersions: async (skip, limit) => {
      const room = (await read(true)).entries.map(({ info }) => info).reverse()
      const items = host ? [...room, ...(await privateAll())] : room
      return { data: { items: items.slice(skip, skip + limit), total: items.length } }
    },
    getVersion: async (versionId) => {
      const { workpiece, entries } = await read(false)
      // Without an ID the newest state under the latest version: the binding shows it anyway.
      if (!versionId) {
        const latest = await latestOf(entries)
        if (!latest) throw new Error('This model has no version yet.')
        return { data: withState(model, workpiece, latest, await stateAt()) }
      }
      const entry = entries.find(({ info }) => info.id === versionId)
      // A version from before sharing is the private model's.
      if (!entry && host) return { data: (await httpClient.get<ModelVersion>(`/v1/models/${host.modelId}/versions/${versionId}`)).data }
      if (!entry) throw new Error('This version is not in the workpiece.')
      return { data: { ...(await versionAt(workpiece, entry)), taskEditSnapshot: await taskStateAt(entry.info.createdAt) } }
    },
    createVersion: async (version) => {
      // The first save of an own model: the workpiece has its history already, nothing is stored.
      if (!version.baseVersionId) {
        const { workpiece, entries } = await read(false)
        const first = host ? await latestOf(entries) : entries[0].info
        if (!first) throw new Error('This model has no version yet.')
        return { data: withState(model, workpiece, first) }
      }
      const checkpoint = await mark(version)
      const { workpiece, entries } = await read(false)
      const entry = entries.find(({ info }) => info.id === checkpoint._id)
      if (!entry) throw new Error('The checkpoint is not in the workpiece.')
      return { data: await versionAt(workpiece, entry) }
    },
    roomHistory: async () => {
      const { entries, rest } = await read(true)
      return { versions: entries, rest: rest.flatMap((step) => (step.patch ? [{ createdAt: step.createdAt, xml: step.patch }] : [])) }
    }
  }
}
