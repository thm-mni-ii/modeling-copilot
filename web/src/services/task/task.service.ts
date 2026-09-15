import type { AxiosResponse } from 'axios'
import httpClient from '@/services/api/httpClient'
import type { ApiId, ApiPage } from '@/services/api/types/common'
import type { ModelVersion } from '@/services/api/types/model'
import type { CreateTask, CreateTaskVersion, Task, TaskVersion, TaskVersionInfo, UpdateTask } from '@/services/api/types/task'

class TaskService {
  list(skip = 0, limit = 20, options: { q?: string; archived?: boolean } = {}): Promise<AxiosResponse<ApiPage<Task>>> {
    return httpClient.get('/v1/tasks', { params: { skip, limit, ...options } })
  }

  get(taskId: ApiId): Promise<AxiosResponse<Task>> {
    return httpClient.get(`/v1/tasks/${taskId}`)
  }

  create(task: CreateTask): Promise<AxiosResponse<Task>> {
    return httpClient.post('/v1/tasks', task)
  }

  update(taskId: ApiId, task: UpdateTask): Promise<AxiosResponse<Task>> {
    return httpClient.patch(`/v1/tasks/${taskId}`, task)
  }

  listVersions(taskId: ApiId, skip = 0, limit = 20): Promise<AxiosResponse<ApiPage<TaskVersionInfo>>> {
    return httpClient.get(`/v1/tasks/${taskId}/versions`, { params: { skip, limit } })
  }

  getVersion(taskId: ApiId, versionId: ApiId): Promise<AxiosResponse<TaskVersion>> {
    return httpClient.get(`/v1/tasks/${taskId}/versions/${versionId}`)
  }

  createVersion(taskId: ApiId, version: CreateTaskVersion): Promise<AxiosResponse<TaskVersion>> {
    return httpClient.post(`/v1/tasks/${taskId}/versions`, version)
  }

  getSampleSolution(taskId: ApiId, versionId: ApiId, modelId: ApiId, modelVersionId: ApiId): Promise<AxiosResponse<ModelVersion>> {
    return httpClient.get(`/v1/tasks/${taskId}/versions/${versionId}/sample-solutions/${modelId}/${modelVersionId}`)
  }
}

export default new TaskService()
