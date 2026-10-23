import http from '@/services/api/httpClient'
import type { TaskVersionReference, ApiPage } from '@/services/api/types/common'
import type { ChallengeConfig, ChallengeAttempt } from '@/services/challenges'
export interface Condition {
  type: 'completed' | 'score' | 'at' | 'after'
  stepId: string | null
  value: number | null
  at: string | null
  timezone: string
  seconds: number | null
}
export interface PathStep {
  id: string
  title: string
  taskVersion: TaskVersionReference
  unlock: { mode: 'all' | 'any'; conditions: Condition[] }
  challenge?: ChallengeConfig | null
}
export interface PathTemplate {
  id: string
  name: string
  description: string
  published: boolean
  archived: boolean
  updatedAt: string | null
  steps: PathStep[]
}
export interface StepRun extends PathStep {
  status: 'locked' | 'available' | 'in_progress' | 'completed'
  modelId: string | null
  reasons: string[]
  availableAt: string | null
}
export interface PathRun {
  id: string
  templateId: string
  name: string
  description: string
  steps: StepRun[]
  completed: number
  total: number
  progress: number
}
export interface StepRunContext {
  id: string
  runId: string
  stepId: string
  modelId: string
  title: string
  taskVersion: TaskVersionReference
  startedAt: string
  completedAt: string | null
  unlockedAt: string | null
  challenge: ChallengeAttempt | null
}
export default {
  stepRunForModel: (modelId: string) => http.get<StepRunContext | null>(`/v1/learning-path-step-runs/by-model/${modelId}`),
  stopChallenge: (runId: string, stepId: string) => http.post<StepRunContext>(`/v1/learning-path-runs/${runId}/steps/${stepId}/challenge/stop`),
  templates: (skip = 0) => http.get<ApiPage<PathTemplate>>('/v1/learning-path-templates', { params: { skip, limit: 100 } }),
  template: (id: string) => http.get<PathTemplate>(`/v1/learning-path-templates/${id}`),
  save: (template: PathTemplate) => {
    const { name, description, published, archived, updatedAt, steps } = template
    const body = { name, description, published, archived, updatedAt, steps }
    return template.id ? http.put<PathTemplate>(`/v1/learning-path-templates/${template.id}`, body) : http.post<PathTemplate>('/v1/learning-path-templates', body)
  },
  start: (id: string) => http.post<PathRun>(`/v1/learning-path-templates/${id}/runs`),
  runs: (skip = 0) => http.get<ApiPage<PathRun>>('/v1/learning-path-runs', { params: { skip, limit: 100 } }),
  run: (id: string) => http.get<PathRun>(`/v1/learning-path-runs/${id}`),
  startStep: (runId: string, stepId: string, acknowledgedChallenge: ChallengeConfig | null = null) => http.post<{ modelId: string }>(`/v1/learning-path-runs/${runId}/steps/${stepId}/start`, { acknowledgedChallenge }),
  complete: (runId: string, stepId: string) => http.post<PathRun>(`/v1/learning-path-runs/${runId}/steps/${stepId}/complete`)
}
