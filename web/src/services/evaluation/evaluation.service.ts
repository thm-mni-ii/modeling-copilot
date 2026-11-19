import type { AxiosResponse } from 'axios'
import httpClient from '@/services/api/httpClient'
import type { ApiId } from '@/services/api/types/common'
import type { Evaluation, EvaluationDetail, EvaluationFeedback, EvaluationPage, EvaluationParameters, EvaluationWorkflow } from '@/services/api/types/evaluation'
import { analysisFromEvaluation } from '@/utils/analysisFeedback'

class EvaluationService {
  listWorkflows(): Promise<AxiosResponse<EvaluationWorkflow[]>> { return httpClient.get('/v1/evaluation-workflows') }
  start(modelId: ApiId, parameters: Partial<EvaluationParameters> = {}): Promise<AxiosResponse<Evaluation>> { return httpClient.post(`/v1/models/${modelId}/evaluations`, parameters) }
  list(modelId: ApiId, skip = 0, limit = 100): Promise<AxiosResponse<EvaluationPage>> { return httpClient.get(`/v1/models/${modelId}/evaluations`, { params: { skip, limit } }) }
  async listAll(modelId: ApiId): Promise<Evaluation[]> {
    const entries: Evaluation[] = []
    let total = 0
    do {
      const page = (await this.list(modelId, entries.length)).data
      if (!page.items.length) break
      entries.push(...page.items)
      total = page.total
    } while (entries.length < total)
    return entries
  }
  get(evaluationId: ApiId): Promise<AxiosResponse<EvaluationDetail>> { return httpClient.get(`/v1/evaluations/${evaluationId}`) }
  getFeedback(evaluationId: ApiId): Promise<AxiosResponse<EvaluationFeedback>> { return httpClient.get(`/v1/evaluations/${evaluationId}/feedback`) }
  async getAnalysis(evaluationId: ApiId, referenceKey: string) { return analysisFromEvaluation((await this.get(evaluationId)).data, referenceKey) }
  downloadArchive(evaluationId: ApiId): Promise<AxiosResponse<Blob>> { return httpClient.get(`/v1/evaluations/${evaluationId}/archive.zip`, { responseType: 'blob' }) }
}
export default new EvaluationService()
