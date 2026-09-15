import type { ModelPatch, ModelVersionInfo, WorkspaceLanguageReference } from '@/services/api/types/model'

export interface ReleaseTimelineStep {
  kind: 'release'
  releaseId: string
  versionNumber: string
  releaseName: string | null
  createdAt: string
  workspaceLanguages: WorkspaceLanguageReference[]
}

export interface PatchTimelineStep {
  kind: 'patch'
  saved: boolean
  releaseId: string
  checkpointId: string | null
  checkpointVersionNumber: string | null
  patch: ModelPatch
  patchNumber: number
  workspaceLanguages: WorkspaceLanguageReference[]
}

export type ModelTimelineStep = ReleaseTimelineStep | PatchTimelineStep

const chronological = (left: ModelVersionInfo, right: ModelVersionInfo) => {
  const byTime = new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime()
  return byTime || left.id.localeCompare(right.id)
}

/** Builds the complete timeline while preserving patch array order per checkpoint. */
export const buildModelTimeline = (versions: readonly ModelVersionInfo[]): ModelTimelineStep[] => {
  const releases = versions.filter((entry) => entry.kind === 'release').sort(chronological)
  const checkpoints = versions.filter((entry) => entry.kind === 'checkpoint').sort(chronological)
  const steps: ModelTimelineStep[] = []

  for (const release of releases) {
    steps.push({
      kind: 'release',
      releaseId: release.id,
      versionNumber: release.versionNumber,
      releaseName: release.releaseName,
      createdAt: release.createdAt,
      workspaceLanguages: release.workspaceLanguages
    })

    for (const checkpoint of checkpoints.filter((entry) => entry.baseReleaseId === release.id)) {
      checkpoint.patches.forEach((patch, patchIndex) => {
        steps.push({
          kind: 'patch',
          saved: true,
          releaseId: release.id,
          checkpointId: checkpoint.id,
          checkpointVersionNumber: checkpoint.versionNumber,
          patch,
          patchNumber: patchIndex + 1,
          workspaceLanguages: checkpoint.workspaceLanguages
        })
      })
    }
  }

  return steps
}

export const appendUnsavedTimelinePatches = (steps: readonly ModelTimelineStep[], releaseId: string | null, patches: readonly ModelPatch[], workspaceLanguages: readonly WorkspaceLanguageReference[] = []): ModelTimelineStep[] => {
  if (!releaseId || patches.length === 0) return [...steps]
  return [
    ...steps,
    ...patches.map(
      (patch, patchIndex): PatchTimelineStep => ({
        kind: 'patch',
        saved: false,
        releaseId,
        checkpointId: null,
        checkpointVersionNumber: null,
        patch,
        patchNumber: patchIndex + 1,
        workspaceLanguages: [...workspaceLanguages]
      })
    )
  ]
}

export const lastSavedTimelineIndex = (steps: readonly ModelTimelineStep[]) => {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const step = steps[index]
    if (step.kind === 'release' || step.saved) return index
  }
  return -1
}

export const releaseTimelineTicks = (steps: readonly ModelTimelineStep[], lastSavedIndex = lastSavedTimelineIndex(steps)) => {
  const ticks: Record<number, string> = Object.fromEntries(steps.flatMap((step, index) => (step.kind === 'release' ? [[index, `Release v${step.versionNumber}`]] : [])))
  if (lastSavedIndex >= 0) ticks[lastSavedIndex] = ticks[lastSavedIndex] ? `${ticks[lastSavedIndex]} · Last save` : 'Last save'
  return ticks
}

export const patchesForTimelineStep = (steps: readonly ModelTimelineStep[], selectedIndex: number) => {
  const selected = steps[selectedIndex]
  if (!selected) return []
  return steps
    .slice(0, selectedIndex + 1)
    .filter((step): step is PatchTimelineStep => step.kind === 'patch' && step.releaseId === selected.releaseId)
    .map((step) => step.patch)
}
