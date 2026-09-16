import type { ApiId, ApiIdentity, ApiVersionInfo, JsonObject, LanguageVersionReference, TaskVersionReference } from './common'

export type ModelVersionKind = 'checkpoint' | 'release'
export type ModelSortField = 'updatedAt' | 'createdAt' | 'name'
export type SortOrder = 'asc' | 'desc'

export interface ModelListOptions {
  q?: string
  archived?: boolean
  taskBound?: boolean
  sort?: ModelSortField
  order?: SortOrder
}

export interface WorkspaceLanguageReference extends LanguageVersionReference {
  source: 'required' | 'additional'
}

export interface TaskEditDocument {
  schemaVersion: 1
  revision: number
  updatedAt: string
  document: JsonObject
}

export interface UpdateTaskEdit {
  baseRevision: number
  document: JsonObject
}

export interface Model extends ApiIdentity {
  name: string
  latestVersionId: ApiId | null
  taskVersion: TaskVersionReference | null
  taskEdit: TaskEditDocument | null
  preferences: JsonObject
  updatedAt: string
  archivedAt: string | null
}

export interface CreateModel {
  name: string
  taskVersion?: TaskVersionReference | null
}

export interface UpdateModel {
  name?: string
  archived?: boolean
  preferences?: JsonObject
}

export interface ModelVersionInfo extends ApiVersionInfo {
  modelId: ApiId
  baseReleaseId: ApiId | null
  patches: ModelPatch[]
  workspaceLanguages: WorkspaceLanguageReference[]
  taskVersion: TaskVersionReference | null
  kind: ModelVersionKind
  releaseName: string | null
  description: string | null
}

export interface ModelPatch {
  createdAt: string
  xml: string
}

export interface ModelVersion extends ModelVersionInfo {
  data: JsonObject
  taskEditSnapshot: TaskEditDocument | null
  annotations: JsonObject | null
}

export interface CreateModelVersion {
  baseVersionId: ApiId | null
  baseReleaseId?: ApiId | null
  workspaceLanguages?: WorkspaceLanguageReference[]
  taskVersion?: TaskVersionReference | null
  data: JsonObject
  patches?: ModelPatch[]
  kind?: ModelVersionKind
  releaseName?: string | null
  description?: string | null
}
