import type { AxiosResponse } from 'axios'
import httpClient from '@/services/api/httpClient'
import type { ApiId, ApiPage } from '@/services/api/types/common'
import type { CreateModel, CreateModelVersion, Model, ModelListOptions, ModelVersion, ModelVersionInfo, TaskEditDocument, UpdateModel, UpdateTaskEdit } from '@/services/api/types/model'
import { versionsOf } from '@/collab/storage/workpieceVersions'

class ModelService {
  list(skip = 0, limit = 20, options: ModelListOptions = {}): Promise<AxiosResponse<ApiPage<Model>>> {
    return httpClient.get('/v1/models', { params: { skip, limit, ...options } })
  }

  get(modelId: ApiId): Promise<AxiosResponse<Model>> {
    return httpClient.get(`/v1/models/${modelId}`)
  }

  update(modelId: ApiId, model: UpdateModel): Promise<AxiosResponse<Model>> {
    return httpClient.patch(`/v1/models/${modelId}`, model)
  }

  create(model: CreateModel): Promise<AxiosResponse<Model>> {
    return httpClient.post('/v1/models', model)
  }

  // A model shared through a workpiece keeps its versions in collab-kit; the adapter answers in the same shapes.
  listVersions(model: Model, skip = 0, limit = 20): Promise<{ data: ApiPage<ModelVersionInfo> }> {
    return versionsOf(model)?.listVersions(skip, limit) ?? httpClient.get(`/v1/models/${model.id}/versions`, { params: { skip, limit } })
  }

  getVersion(model: Model, versionId?: ApiId | null): Promise<{ data: ModelVersion }> {
    const shared = versionsOf(model)
    if (shared) return shared.getVersion(versionId)
    if (!versionId) return Promise.reject(new Error('This model has no saved version yet.'))
    return httpClient.get(`/v1/models/${model.id}/versions/${versionId}`)
  }

  createVersion(model: Model, version: CreateModelVersion): Promise<{ data: ModelVersion }> {
    return versionsOf(model)?.createVersion(version) ?? httpClient.post(`/v1/models/${model.id}/versions`, version)
  }

  getTaskEdit(modelId: ApiId): Promise<AxiosResponse<TaskEditDocument | null>> {
    return httpClient.get(`/v1/models/${modelId}/task-edit`)
  }

  updateTaskEdit(modelId: ApiId, taskEdit: UpdateTaskEdit): Promise<AxiosResponse<TaskEditDocument>> {
    return httpClient.put(`/v1/models/${modelId}/task-edit`, taskEdit)
  }
}

export default new ModelService()
