import http from '@/services/api/httpClient'
import type { ApiPage } from '@/services/api/types/common'

export type SurveyMode = 'use' | 'preview' | 'test'
export interface SurveyQuestion {
  type: 'comment' | 'radiogroup' | 'checkbox' | 'rating' | 'matrix'
  name: string
  title: string
  description?: string
  page?: string
  isRequired: boolean
  visibleIf?: string
  visibleWhen?: 'help_requested' | 'pulse_answered'
  choices?: string[]
  exclusiveChoices?: string[]
  choiceLabels?: Record<string, string>
  rows?: string[]
  columns?: string[]
  isAllRowRequired?: boolean
  rateMin?: number
  rateMax?: number
  minRateDescription?: string
  maxRateDescription?: string
}
export interface SurveyPage {
  name: string
  title: string
  description?: string
}
export interface SurveyDefinition {
  elements: SurveyQuestion[]
  introduction?: string
  pages?: SurveyPage[]
  showQuestionNumbers?: 'on' | 'off'
}
export interface Survey {
  managedBy?: string | null
  templateId?: string | null
  id: string
  title: string
  definition: SurveyDefinition
  version: number
  latestVersionId: string
  latestKind: 'checkpoint' | 'release'
  activeReleaseId: string | null
  activeReleaseVersion: number | null
  revision: number
  createdAt: string
  updatedAt: string
  createdBy: string | null
  updatedBy: string | null
}
export interface SurveyVersionInfo {
  id: string
  surveyId: string
  version: number
  title: string
  kind: 'checkpoint' | 'release'
  createdAt: string
  createdBy: string | null
  releasedAt: string | null
  releasedBy: string | null
}
export interface SurveyVersion extends SurveyVersionInfo {
  definition: SurveyDefinition
}
export interface SurveyResponse {
  rewardCoins?: number
  coinBalance?: number
  id: string
  surveyId: string
  version: number
  versionId: string
  userId: string
  answers: Record<string, unknown>
  isTest: boolean
  createdAt: string
}
export const surveyError = (error: unknown) => {
  const response = (error as { response?: { status?: number; data?: { message?: string; code?: string } } }).response
  if (response?.data?.code === 'NO_ACTIVE_RELEASE') return 'Dieser Fragebogen hat noch keinen aktiven Release.'
  return response?.status === 409 ? 'Der Fragebogen wurde inzwischen geändert. Bitte neu laden.' : response?.data?.message ?? 'Die Anfrage konnte nicht verarbeitet werden.'
}
export default {
  list: (skip = 0) => http.get<ApiPage<Survey>>('/v1/surveys', { params: { skip, limit: 100 } }),
  get: (id: string) => http.get<Survey>(`/v1/surveys/${id}`),
  render: (id: string, mode: SurveyMode, versionId?: string) => http.get<SurveyVersion>(`/v1/surveys/${id}/render`, { params: { mode, versionId } }),
  versions: (id: string, skip = 0) => http.get<ApiPage<SurveyVersionInfo>>(`/v1/surveys/${id}/versions`, { params: { skip, limit: 100 } }),
  activate: (id: string, versionId: string, expectedRevision: number) => http.post<Survey>(`/v1/surveys/${id}/release`, { versionId, expectedRevision }),
  save: (id: string, title: string, definition: SurveyDefinition, baseVersionId: string | null, expectedRevision: number | null) => {
    const body = { title, definition, baseVersionId, expectedRevision }
    return id ? http.put<Survey>(`/v1/surveys/${id}`, body) : http.post<Survey>('/v1/surveys', body)
  },
  remove: (id: string) => http.delete(`/v1/surveys/${id}`),
  submit: (id: string, versionId: string, answers: Record<string, unknown>, mode: SurveyMode) => http.post<SurveyResponse>(`/v1/surveys/${id}/responses`, { versionId, answers, mode })
}
