import type { ModelPatch, ModelVersionInfo, WorkspaceLanguageReference } from '@/services/api/types/model'
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
}

/** One change to write into the units and, after it, the checkpoint that names the state it leaves. */
export interface HistoryStep {
  change: UnitChange<ModelUnit>
  /** Set on the last step of a version. A label makes it a release in collab-kit, as the adapter reads it. */
  checkpoint?: { label?: string; reason?: string }
}

/** Whether a change writes or removes anything; a version equal to the one before has none. */
export const hasChange = (change: UnitChange<ModelUnit>) => Object.keys(change.set ?? {}).length > 0 || (change.delete?.length ?? 0) > 0

/** The checkpoint of a version: a release carries its name (the number if it has none, as collab-kit knows a release by its label), the description is the reason. */
const checkpointOf = ({ kind, releaseName, versionNumber, description }: ModelVersionInfo): HistoryStep['checkpoint'] => ({
  ...(kind === 'release' ? { label: releaseName || versionNumber } : {}),
  ...(description ? { reason: description } : {})
})

/**
 * The states a checkpoint passes through on its way from the version before: after every patch but
 * the last, whose state is the stored one. Empty if a patch does not apply, then the version is one step.
 */
const middleStates = (before: string, patches: readonly Pick<ModelPatch, 'xml'>[]) => {
  const states: string[] = []
  try {
    let xml = before
    for (const patch of patches.slice(0, -1)) {
      xml = applyModelPatches(xml, [patch])
      states.push(xml)
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
  for (const { info, xml } of mode === 'none' ? [] : versions) {
    if (mode === 'steps' && info.kind === 'checkpoint' && before !== null) {
      for (const state of middleStates(before, info.patches)) {
        const change = moveTo(state, info.workspaceLanguages)
        if (hasChange(change)) steps.push({ change })
      }
    }
    steps.push({ change: moveTo(xml, info.workspaceLanguages), checkpoint: checkpointOf(info) })
    before = xml
  }
  if (live) {
    const change = moveTo(live.xml, live.languages)
    if (hasChange(change)) steps.push({ change })
  }
  return steps
}
