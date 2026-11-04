import modelService from '@/services/model/model.service'
import type { TaskEditPatch, TaskEditVersionInfo } from '@/services/api/types/model'
import type { JsonObject } from '@/services/api/types/common'
import { collectTaskEdits } from '@/utils/taskEdits'

export interface TaskEditTimelineStep {
  id: string
  createdAt: string
  saved: boolean
  label: string
  patch?: TaskEditPatch
}

export const loadTaskEditHistory = async (modelId: string): Promise<TaskEditVersionInfo[]> => {
  const entries: TaskEditVersionInfo[] = []
  let total = 0
  do {
    const page = (await modelService.listTaskEditHistory(modelId, entries.length)).data
    if (!page.items.length) break
    entries.push(...page.items)
    total = page.total
  } while (entries.length < total)
  return entries
}

export const buildTaskEditTimeline = (history: TaskEditVersionInfo[], patches: TaskEditPatch[], base?: JsonObject | null): TaskEditTimelineStep[] => {
  let previous = collectTaskEdits(base)
  const local = patches.map((patch): TaskEditTimelineStep => {
    const current = collectTaskEdits(patch.document)
    const before = new Map(previous.map((entry) => [entry.id, entry]))
    const after = new Map(current.map((entry) => [entry.id, entry]))
    const labels = [...new Set([...before.keys(), ...after.keys()])].flatMap((id) => {
      if (JSON.stringify(before.get(id)) === JSON.stringify(after.get(id))) return []
      const entry = after.get(id) ?? before.get(id)!
      return [`${!before.has(id) ? 'Created' : !after.has(id) ? 'Removed' : 'Changed'} ${entry.type}`]
    })
    previous = current
    return { id: patch.id, createdAt: patch.createdAt, saved: false, label: labels.join(', ') || 'Task state restored', patch }
  })
  return [
  ...history.map((entry) => ({
    id: entry.id, createdAt: entry.createdAt, saved: true,
    label: entry.changes.map((change) => `${({ create: 'Created', remove: 'Removed', update: 'Changed' })[change.kind]} ${change.editType}`).join(', ') || 'Task state restored'
  })),
  ...local
  ]
}
