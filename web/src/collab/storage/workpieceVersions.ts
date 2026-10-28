import type { ApiId, ApiPage } from '@/services/api/types/common'
import type { CreateModelVersion, Model, ModelVersion, ModelVersionInfo, WorkspaceLanguageReference } from '@/services/api/types/model'
import { createEmptyModelSnapshot, EMPTY_MODEL_XML } from '@/model/ModelSnapshot'
import { createModelPatch } from '@/utils/modelPatches'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabEvent, CollabKitApi, Workpiece } from '@/collab/kit/collabKitV1'
import { liveSession } from '@/collab/kit/liveSession'
import { languagesIn, xmlOf, type ModelUnit } from './modelUnits'
import { CELLS_MAP, languagesOf, linkOf } from './workpiece'

/** The version methods of model.service for a model shared through a workpiece, in the shapes of the API. */
export interface ModelVersions {
  listVersions(skip: number, limit: number): Promise<{ data: ApiPage<ModelVersionInfo> }>
  /** Left out, the latest version with the newest state of collab-kit. */
  getVersion(versionId?: ApiId | null): Promise<{ data: ModelVersion }>
  createVersion(version: CreateModelVersion): Promise<{ data: ModelVersion }>
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
interface Entry {
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

/** The versions oldest first: the initial release, then one per checkpoint with the changes since the one before. */
const entriesOf = (model: Model, history: History, checkpoints: readonly CollabEvent[]) => {
  const entries: Entry[] = [{ info: initialOf(model, history.workpiece) }]
  let done = 0
  for (const checkpoint of checkpoints) {
    const before = entries[entries.length - 1].info
    const release = Boolean(checkpoint.label)
    const end = checkpoint.at ? history.steps.findIndex((step) => step.id === checkpoint.at) + 1 : 0
    const steps = history.steps.slice(done, end)
    done = Math.max(done, end)
    entries.push({
      at: checkpoint.at,
      info: {
        id: checkpoint._id,
        versionNumber: nextNumber(before.versionNumber, release),
        createdAt: checkpoint.createdAt,
        createdBy: checkpoint.createdBy,
        modelId: model.id,
        baseReleaseId: release ? null : before.kind === 'release' ? before.id : before.baseReleaseId,
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
  return entries
}

/** The version with a state of the workpiece and its languages; without one, the empty model. */
const withState = (model: Model, workpiece: Workpiece, info: ModelVersionInfo, units?: ReadonlyMap<string, ModelUnit>): ModelVersion => ({
  ...info,
  data: { ...createEmptyModelSnapshot(model.name), xml: (units && xmlOf(units)) ?? EMPTY_MODEL_XML },
  workspaceLanguages: units ? languagesIn(units, workpiece) : info.workspaceLanguages,
  taskEditSnapshot: null
})

/** Whether collab-kit holds every unit as the session has it, so nothing of the own is on its way. */
const sameUnits = (stored: ReadonlyMap<string, ModelUnit>, own: [string, ModelUnit][]) => stored.size === own.length && own.every(([key, unit]) => JSON.stringify(stored.get(key)) === JSON.stringify(unit))

const pause = () => new Promise((resolve) => setTimeout(resolve, PAUSE_MS))

/** The adapter of a model shared through a workpiece; null for a model the API keeps. */
export const versionsOf = (model: Model): ModelVersions | null => {
  const link = linkOf(model.preferences)
  if (!link) return null
  const { workpieceId } = link

  const stateAt = async (at?: string) => (await (await loadCollabKit()).workpieces.unitsAt<ModelUnit>(workpieceId, { at, map: CELLS_MAP })).units

  // Checkpoints first, so the history read after reaches every change they stand at. Only the list
  // needs the patches; a single version reads just its own state, so opening a model stays quick.
  const read = async (withPatches: boolean) => {
    const ck = await loadCollabKit()
    const checkpoints = (await ck.events.list({ anchorKind: 'workpiece', anchorId: workpieceId, kind: 'checkpoint' })).reverse()
    const history = withPatches ? await historyOf(ck, workpieceId) : { workpiece: histories.get(workpieceId)?.workpiece ?? (await ck.workpieces.get(workpieceId)), steps: [], xml: EMPTY_MODEL_XML }
    return { workpiece: history.workpiece, entries: entriesOf(model, history, checkpoints) }
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
      const items = (await read(true)).entries.map(({ info }) => info).reverse()
      return { data: { items: items.slice(skip, skip + limit), total: items.length } }
    },
    getVersion: async (versionId) => {
      const { workpiece, entries } = await read(false)
      // Without an ID the newest state under the latest version: the binding shows it anyway.
      if (!versionId) return { data: withState(model, workpiece, entries[entries.length - 1].info, await stateAt()) }
      const entry = entries.find(({ info }) => info.id === versionId)
      if (!entry) throw new Error('This version is not in the workpiece.')
      return { data: await versionAt(workpiece, entry) }
    },
    createVersion: async (version) => {
      // The first save of an own model: the workpiece has its history already, nothing is stored.
      if (!version.baseVersionId) {
        const { workpiece, entries } = await read(false)
        return { data: withState(model, workpiece, entries[0].info) }
      }
      const checkpoint = await mark(version)
      const { workpiece, entries } = await read(false)
      const entry = entries.find(({ info }) => info.id === checkpoint._id)
      if (!entry) throw new Error('The checkpoint is not in the workpiece.')
      return { data: await versionAt(workpiece, entry) }
    }
  }
}
