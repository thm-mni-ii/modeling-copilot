import type { AutonomyMode } from '@/model/Autonomy'
import type { ApiId, ApiIdentity, ApiVersionInfo, ModelVersionReference, TaskVersionReference } from './common'
import type { WorkspaceLanguageReference } from './model'

export type TaskVersionKind = 'checkpoint' | 'release'
export type TaskVisibility = 'private' | 'published'

export interface Task extends ApiIdentity {
  name: string
  parent: TaskVersionReference | null
  latestVersionId: ApiId | null
  latestReleaseId: ApiId | null
  latestReleaseCreatedBy: string | null
  visibility: TaskVisibility
  archivedAt: string | null
}

export interface CreateTask {
  name: string
  parent?: TaskVersionReference | null
}

export interface UpdateTask {
  name?: string
  archived?: boolean
  visibility?: TaskVisibility
}

export interface TaskData {
  contentHtml: string
  autonomyMode: AutonomyMode
  sampleSolutions: ModelVersionReference[]
  evaluationWorkflows: string[]
}

export interface TaskVersionInfo extends ApiVersionInfo {
  taskId: ApiId
  kind: TaskVersionKind
  releaseName: string | null
  description: string | null
  workspaceLanguages: WorkspaceLanguageReference[]
}

export interface TaskVersion extends TaskVersionInfo {
  data: TaskData
}

export interface CreateTaskVersion {
  baseVersionId: ApiId | null
  kind: TaskVersionKind
  releaseName?: string | null
  description?: string | null
  workspaceLanguages: WorkspaceLanguageReference[]
  data: TaskData
}
