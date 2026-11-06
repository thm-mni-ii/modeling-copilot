import type { ModelPatch, ModelVersionInfo, TaskEditDocument, WorkspaceLanguageReference } from '@/services/api/types/model'
import type { UnitChange } from '@/collab/kit/collabKitV1'
import { applyModelPatches } from '@/utils/modelPatches'
import { splitModel, type SharedCell } from './modelCells'
import { LANGUAGES_KEY, type ModelUnit } from './modelUnits'

/** How much of the private history goes into the workpiece: none, one step per version, or every patch. */
export type HistoryMode = 'none' | 'versions' | 'steps'

/** A version of the private model with its whole state; a checkpoint holds only patches, so the XML is read per version. */
export interface PrivateVersion {
  info: ModelVersionInfo
  xml: string
  /** The task state this version points to; null if it points to none. */
  task: TaskEditDocument | null
}

/** One change to write into the units and, after it, the checkpoint that names the state it leaves. */
export interface HistoryStep {
  change: UnitChange<ModelUnit>
  /** Set on the last step of a version. A label makes it a release in collab-kit, as the adapter reads it. */
  checkpoint?: { label?: string; reason?: string }
  /** When it happened privately, to bring it in order with the steps of the task. */
  createdAt: string
  /** The task revision of its version: the task steps up to it come before its checkpoint. */
  taskRevision: number
}

/** Whether a change writes or removes anything; a version equal to the one before has none. */
export const hasChange = <Value>(change: UnitChange<Value>) => Object.keys(change.set ?? {}).length > 0 || (change.delete?.length ?? 0) > 0

/** The checkpoint of a version: a release carries its name (the number if it has none, as collab-kit knows a release by its label), the description is the reason. */
const checkpointOf = ({ kind, releaseName, versionNumber, description }: ModelVersionInfo): HistoryStep['checkpoint'] => ({
  ...(kind === 'release' ? { label: releaseName || versionNumber } : {}),
  ...(description ? { reason: description } : {})
})

/**
 * The states a checkpoint passes through on its way from the version before: after every patch but
 * the last, whose state is the stored one. Empty if a patch does not apply, then the version is one step.
 */
const middleStates = (before: string, patches: readonly ModelPatch[]) => {
  const states: { xml: string; createdAt: string }[] = []
  try {
    let xml = before
    for (const patch of patches.slice(0, -1)) {
      xml = applyModelPatches(xml, [patch])
      states.push({ xml, createdAt: patch.createdAt })
    }
  } catch {
    return []
  }
  return states
}

/**
 * The private history as steps for a new workpiece, oldest first, so that collab-kit holds the
 * versions a visitor sees before joining. `versions` writes the state of every version and names it;
 * `steps` also writes each patch of a checkpoint as a step of its own. Releases hold no patches, so
 * they stay one step. A version always ends on its stored state, whatever the patches lead to.
 * `live` is the state the host shares now; it comes last, with no checkpoint, and is left out if
 * the last version already holds it. Without a history it is the only step.
 */
export const stepsOf = (versions: readonly PrivateVersion[], mode: HistoryMode, live?: { xml: string; languages: WorkspaceLanguageReference[] }): HistoryStep[] => {
  // What the units hold after the steps so far, to write only what differs.
  let cells: ReadonlyMap<string, SharedCell> = new Map()
  let languages = ''
  const moveTo = (xml: string, workspaceLanguages: WorkspaceLanguageReference[]): UnitChange<ModelUnit> => {
    const next = splitModel(xml, cells)
    const set: Record<string, ModelUnit> = {}
    for (const [id, cell] of next) {
      const before = cells.get(id)
      if (!before || before.xml !== cell.xml || before.index !== cell.index) set[id] = cell
    }
    const removed = Array.from(cells.keys()).filter((id) => !next.has(id))
    // The languages go in with the first step and again only when they change.
    const written = JSON.stringify(workspaceLanguages)
    if (written !== languages) set[LANGUAGES_KEY] = workspaceLanguages
    cells = next
    languages = written
    return { set, delete: removed }
  }

  const steps: HistoryStep[] = []
  let before: string | null = null
  for (const { info, xml, task } of mode === 'none' ? [] : versions) {
    const taskRevision = task?.revision ?? 0
    if (mode === 'steps' && info.kind === 'checkpoint' && before !== null) {
      for (const state of middleStates(before, info.patches)) {
        const change = moveTo(state.xml, info.workspaceLanguages)
        if (hasChange(change)) steps.push({ change, createdAt: state.createdAt, taskRevision })
      }
    }
    const lastPatch = info.kind === 'checkpoint' ? info.patches[info.patches.length - 1] : undefined
    steps.push({ change: moveTo(xml, info.workspaceLanguages), checkpoint: checkpointOf(info), createdAt: lastPatch?.createdAt ?? info.createdAt, taskRevision })
    before = xml
  }
  if (live) {
    const change = moveTo(live.xml, live.languages)
    const now = { createdAt: new Date().toISOString(), taskRevision: Number.POSITIVE_INFINITY }
    // Without a history the state is the one version visitors see, so it is a release of its own and not the empty start.
    if (hasChange(change)) steps.push(mode === 'none' ? { change, checkpoint: { label: 'State at sharing' }, ...now } : { change, ...now })
  }
  return steps
}
