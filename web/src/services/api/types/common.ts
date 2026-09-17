export type ApiId = string
export type JsonObject = Record<string, unknown>

export interface ApiPage<T> {
  items: T[]
  total: number
}

export interface ApiIdentity {
  id: ApiId
  ownerId: string
  createdAt: string
}

export interface ApiVersionInfo {
  id: ApiId
  versionNumber: string
  createdAt: string
  createdBy: string
}

export interface LanguageVersionReference {
  languageId: ApiId
  versionId: ApiId
}

export interface TaskVersionReference {
  taskId: ApiId
  versionId: ApiId
}

export interface ModelVersionReference {
  modelId: ApiId
  versionId: ApiId
}
