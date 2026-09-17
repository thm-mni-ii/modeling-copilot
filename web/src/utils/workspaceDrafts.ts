import type { JsonObject } from '@/services/api/types/common'
import type { ModelPatch, TaskEditDocument } from '@/services/api/types/model'

export interface StoredWorkspaceDraft {
  key: string
  modelId: string | null
  baseVersionId: string | null
  baseReleaseId: string | null
  savedAt: string
  patches: ModelPatch[]
  languages: JsonObject[]
  data: JsonObject
  taskEdit?: TaskEditDocument | null
}

const STORAGE_PREFIX = 'model-workspace-journal:'
const storageKey = (key: string) => `${STORAGE_PREFIX}${key}`

export const readDraft = async (key: string): Promise<StoredWorkspaceDraft | null> => {
  if (typeof localStorage === 'undefined') return null
  const value = localStorage.getItem(storageKey(key))
  if (!value) return null
  try {
    return JSON.parse(value) as StoredWorkspaceDraft
  } catch {
    localStorage.removeItem(storageKey(key))
    return null
  }
}

export const writeDraft = async (draft: StoredWorkspaceDraft) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(storageKey(draft.key), JSON.stringify(draft))
}

export const removeDraft = async (key: string) => {
  if (typeof localStorage !== 'undefined') localStorage.removeItem(storageKey(key))
}
