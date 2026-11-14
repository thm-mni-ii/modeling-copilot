import type { AxiosResponse } from 'axios'
import httpClient from '@/services/api/httpClient'
import type { ApiId } from '@/services/api/types/common'
import type { Evaluation, EvaluationDetail, EvaluationPage, EvaluationWorkflow } from '@/services/api/types/evaluation'
import { analysisFromEvaluation } from '@/utils/analysisFeedback'

class EvaluationService {
  listWorkflows(): Promise<AxiosResponse<EvaluationWorkflow[]>> { return httpClient.get('/v1/evaluation-workflows') }
  start(modelId: ApiId): Promise<AxiosResponse<Evaluation>> { return httpClient.post(`/v1/models/${modelId}/evaluations`, {}) }
  list(modelId: ApiId): Promise<AxiosResponse<EvaluationPage>> { return httpClient.get(`/v1/models/${modelId}/evaluations`) }
  get(evaluationId: ApiId): Promise<AxiosResponse<EvaluationDetail>> { return httpClient.get(`/v1/evaluations/${evaluationId}`) }
  async getAnalysis(evaluationId: ApiId, referenceKey: string) { return analysisFromEvaluation((await this.get(evaluationId)).data, referenceKey) }
  downloadArchive(evaluationId: ApiId): Promise<AxiosResponse<Blob>> { return httpClient.get(`/v1/evaluations/${evaluationId}/archive.zip`, { responseType: 'blob' }) }
}
export default new EvaluationService()
