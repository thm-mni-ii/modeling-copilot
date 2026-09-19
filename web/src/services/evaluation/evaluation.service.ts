import type { AxiosResponse } from 'axios'
import httpClient from '@/services/api/httpClient'
import type { ApiId } from '@/services/api/types/common'
import type { Evaluation, EvaluationDetail, EvaluationPage, EvaluationWorkflow } from '@/services/api/types/evaluation'

class EvaluationService {
  listWorkflows(): Promise<AxiosResponse<EvaluationWorkflow[]>> { return httpClient.get('/v1/evaluation-workflows') }
  start(modelId: ApiId): Promise<AxiosResponse<Evaluation>> { return httpClient.post(`/v1/models/${modelId}/evaluations`, {}) }
  list(modelId: ApiId): Promise<AxiosResponse<EvaluationPage>> { return httpClient.get(`/v1/models/${modelId}/evaluations`) }
  get(evaluationId: ApiId): Promise<AxiosResponse<EvaluationDetail>> { return httpClient.get(`/v1/evaluations/${evaluationId}`) }
}
export default new EvaluationService()
