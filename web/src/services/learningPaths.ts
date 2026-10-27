import type { SurveyVersion, SurveyResponse } from '@/services/surveys'
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
  type?: 'task' | 'survey'
  taskVersion: TaskVersionReference | null
  surveyId?: string | null
  beforeSurveyId?: string | null
  afterSurveyId?: string | null
  required?: boolean
  unlock: { mode: 'sequence' | 'all' | 'any'; conditions: Condition[] }
  challenge?: ChallengeConfig | null
}
export interface PulseSurveyConfig {
  enabled: boolean
  surveyIds: string[]
  minGapSeconds: number
  maxGapSeconds: number | null
  maxPerSession: number
  maxPerTask: number | null
  minActiveSeconds: number
  excludeStepIds: string[]
}
export const defaultPulseSurveyConfig = (): PulseSurveyConfig => ({ enabled: false, surveyIds: [], minGapSeconds: 600, maxGapSeconds: 1800, maxPerSession: 3, maxPerTask: null, minActiveSeconds: 120, excludeStepIds: [] })
export interface PulseOffer { id: string; surveyId: string }
export type PulseState = 'idle' | 'offered' | 'open' | 'thanks' | 'expired'
export type SurveyPhase = 'before' | 'after' | `pulse:${string}`
export interface PathTemplate {
  id: string
  name: string
  description: string
  published: boolean
  archived: boolean
  revision: number
  updatedAt: string | null
  steps: PathStep[]
  pulseSurveys?: PulseSurveyConfig
}
export interface StepRun extends PathStep {
  status: 'locked' | 'available' | 'in_progress' | 'completed' | 'skipped'
  modelId: string | null
  reasons: string[]
  availableAt: string | null
}
export interface PathRun {
  templateRevision: number
  id: string
  templateId: string
  name: string
  description: string
  steps: StepRun[]
  completed: number
  coins?: number
  total: number
  progress: number
  skipped?: number
  finished?: boolean
}
export interface PathModelContext {
  id: string
  runId: string
  stepId: string
  modelId: string
  coins: number
  title: string
  taskVersion: TaskVersionReference
  startedAt: string
  completedAt: string | null
  removed: boolean
  templateRevision: number
  completionRequested: boolean
  beforeSurvey: { surveyId: string; completed: boolean } | null
  afterSurvey: { surveyId: string; completed: boolean } | null
  challenge: ChallengeAttempt | null
}
export default {
  pollPulse: (runId: string, stepId: string, sessionKey: string, activeSecondsDelta: number) => http.post<{ offer: PulseOffer | null; nextPollSeconds: number }>(`/v1/learning-path-runs/${runId}/steps/${stepId}/pulse/poll`, { sessionKey, activeSecondsDelta }),
  openPulse: (runId: string, offerId: string) => http.post<{ version: SurveyVersion; answers: Record<string, unknown>; revision: number; sessionId: string; releaseChanged: boolean; status: string }>(`/v1/learning-path-runs/${runId}/pulse/${offerId}/open`),
  dismissPulse: (runId: string, offerId: string) => http.post(`/v1/learning-path-runs/${runId}/pulse/${offerId}/dismiss`),
  expirePulse: (runId: string, offerId: string) => http.post<{ event: 'expired' | 'dismissed' | 'answered' | 'opened' }>(`/v1/learning-path-runs/${runId}/pulse/${offerId}/expire`),
  openSurvey: (runId: string, stepId: string, phase?: SurveyPhase) => http.post<{ version: SurveyVersion; answers: Record<string, unknown>; revision: number; sessionId: string; releaseChanged: boolean; status: string }>(`/v1/learning-path-runs/${runId}/steps/${stepId}/survey/open`, null, { params: { phase } }),
  saveSurveyDraft: (runId: string, stepId: string, answers: Record<string, unknown>, revision: number, sessionId: string, phase?: SurveyPhase) => http.put<{ revision: number }>(`/v1/learning-path-runs/${runId}/steps/${stepId}/survey/draft`, { answers, revision, sessionId }, { params: { phase } }),
  submitSurvey: (runId: string, stepId: string, answers: Record<string, unknown>, revision: number, sessionId: string, phase?: SurveyPhase) => http.post<SurveyResponse>(`/v1/learning-path-runs/${runId}/steps/${stepId}/survey/submit`, { answers, revision, sessionId }, { params: { phase } }),
  skipSurvey: (runId: string, stepId: string, revision: number, sessionId: string) => http.post(`/v1/learning-path-runs/${runId}/steps/${stepId}/survey/skip`, { revision, sessionId }),
  modelContext: (modelId: string) => http.get<PathModelContext | null>(`/v1/learning-path-runs/by-model/${modelId}/context`),
  resumeStep: (runId: string, stepId: string) => http.post<PathModelContext>(`/v1/learning-path-runs/${runId}/steps/${stepId}/resume`),
  stopChallenge: (runId: string, stepId: string) => http.post<PathModelContext>(`/v1/learning-path-runs/${runId}/steps/${stepId}/challenge/stop`),
  templates: (skip = 0) => http.get<ApiPage<PathTemplate>>('/v1/learning-path-templates', { params: { skip, limit: 100 } }),
  template: (id: string) => http.get<PathTemplate>(`/v1/learning-path-templates/${id}`),
  save: (template: PathTemplate) => {
    const { name, description, published, archived, revision, steps, pulseSurveys } = template
    const body = { name, description, published, archived, revision, steps, pulseSurveys }
    return template.id ? http.put<PathTemplate>(`/v1/learning-path-templates/${template.id}`, body) : http.post<PathTemplate>('/v1/learning-path-templates', body)
  },
  start: (id: string) => http.post<PathRun>(`/v1/learning-path-templates/${id}/runs`),
  runs: (skip = 0) => http.get<ApiPage<PathRun>>('/v1/learning-path-runs', { params: { skip, limit: 100 } }),
  run: (id: string) => http.get<PathRun>(`/v1/learning-path-runs/${id}`),
  startStep: (runId: string, stepId: string, acknowledgedChallenge: ChallengeConfig | null = null) => http.post<{ modelId: string }>(`/v1/learning-path-runs/${runId}/steps/${stepId}/start`, { acknowledgedChallenge }),
  complete: (runId: string, stepId: string) => http.post<PathRun>(`/v1/learning-path-runs/${runId}/steps/${stepId}/complete`)
}
