import type { SurveyVersion, SurveyResponse } from '@/services/surveys'
import http from '@/services/api/httpClient'
import type { TaskVersionReference, ApiPage } from '@/services/api/types/common'
import type { ChallengeConfig, ChallengeAttempt } from '@/services/challenges'
export type ScoreScope = 'overall' | 'eachCategory'
/** Minimum for one recognition category, matched by its displayed label (e.g. "Attribute"). */
export interface CategoryMinimum { label: string; minimumPercent: number }
export interface CompletionGate { minimumScorePercent?: number | null; scoreScope?: ScoreScope; categoryMinimums?: CategoryMinimum[] }
export interface Condition {
  type: 'completed' | 'score' | 'at' | 'after'
  stepId: string | null
  value: number | null
  at: string | null
  timezone: string
  seconds: number | null
}
export interface PathStep extends CompletionGate {
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
  helpFeedback?: TaskHelpFeedbackConfig | null
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
export interface HelpChoice { id: string; text: string }
export interface HelpQuestionEdit { title: string; choices: HelpChoice[] }
export type HelpEditableQuestion = 'stuck_duration' | 'support_need' | 'next_action'
export interface HelpBlueprint { topic: import('@/services/surveys').SurveyDefinition; questions: Record<HelpEditableQuestion, HelpQuestionEdit> }
export interface TaskHelpFeedbackConfig {
  checkLimit: number | null
  clarifyLimit: number | null
  nextStepLimit: number | null
  exampleLimit: number | null
  solutionLimit: number | null
}
export const defaultTaskHelpFeedbackConfig = (): TaskHelpFeedbackConfig => ({ checkLimit: null, clarifyLimit: null, nextStepLimit: null, exampleLimit: 2, solutionLimit: 1 })
export interface HelpRequestConfig {
  enabled: boolean
  topicSurveyId: string | null
  reflectionSurveyId: string | null
  actionSurveyId: string | null
  topicQuestion: string
  markingAnswer: string
  actionQuestion: string
  markingEnabled: boolean
  markingRequired: boolean
  questionEdits?: Partial<Record<HelpEditableQuestion, HelpQuestionEdit>>
}
export const defaultHelpRequestConfig = (): HelpRequestConfig => ({
  enabled: false, topicSurveyId: null, reflectionSurveyId: null, actionSurveyId: null,
  topicQuestion: 'problem_area', markingAnswer: 'Aufgabenstellung/Modell', actionQuestion: 'next_action',
  markingEnabled: true, markingRequired: false
})
export type PathVisibility = 'published' | 'unlisted' | 'hidden'
export const pathVisibilityOptions = [
  { title: 'Published', value: 'published', description: 'Visible in the catalog. Learners can start and continue this path.' },
  { title: 'Unlisted', value: 'unlisted', description: 'Hidden from the catalog. Learners who already started can still see and continue their path.' },
  { title: 'Hidden', value: 'hidden', description: 'Hidden from all learners, including existing runs. Only admins can access this path.' }
]
export const pathVisibilityLabel = (visibility: PathVisibility) => pathVisibilityOptions.find((option) => option.value === visibility)?.title ?? 'Hidden'
export interface PathTemplate {
  id: string
  name: string
  description: string
  visibility: PathVisibility
  published: boolean
  archived: boolean
  revision: number
  updatedAt: string | null
  steps: PathStep[]
  pulseSurveys?: PulseSurveyConfig
  helpRequests?: HelpRequestConfig
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
export interface PathModelContext extends CompletionGate {
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
  helpRequests: HelpRequestConfig & TaskHelpFeedbackConfig
  helpUsage: HelpUsage
}
export type HelpFeedbackType = 'help.clarify' | 'help.next_step' | 'help.example' | 'help.check' | 'help.solution'
export const helpFeedbackOptions: { type: HelpFeedbackType; limitKey: keyof TaskHelpFeedbackConfig; choice: string; title: string; short: string; icon: string; description: string }[] = [
  { type: 'help.check', limitKey: 'checkLimit', choice: 'support_need_4', title: 'Prüfung', short: 'Prüfung', icon: 'mdi-check-decagram-outline', description: 'Prüft den bisherigen Modellstand als Ganzes.' },
  { type: 'help.clarify', limitKey: 'clarifyLimit', choice: 'support_need_1', title: 'Erklärung', short: 'Erklär.', icon: 'mdi-lightbulb-on-outline', description: 'Erklärt den Stand an der markierten Problemstelle.' },
  { type: 'help.next_step', limitKey: 'nextStepLimit', choice: 'support_need_2', title: 'Nächster Schritt', short: 'Nächster', icon: 'mdi-arrow-right-circle-outline', description: 'Gibt einen Hinweis auf den nächsten Bearbeitungsschritt.' },
  { type: 'help.example', limitKey: 'exampleLimit', choice: 'support_need_3', title: 'Beispiel', short: 'Beispiel', icon: 'mdi-book-open-variant', description: 'Zeigt ein Strukturbeispiel zur markierten Problemstelle.' },
  { type: 'help.solution', limitKey: 'solutionLimit', choice: 'support_need_5', title: 'Lösung', short: 'Lösung', icon: 'mdi-lightning-bolt-outline', description: 'Zeigt das passende Element der Musterlösung.' }
]
export type HelpUsage = Record<HelpFeedbackType, { used: number; pending: number; limit: number | null }>
export interface HelpTourAnswer { question: 'support_need' | 'next_action'; selected: boolean }
export type FeatureTourItem = 'feedback-types' | 'help-request' | 'mark-object' | 'automatic-feedback' | 'help-feedback-walkthrough'
export interface FeatureTourProgress { completedItems: FeatureTourItem[]; skippedItems: FeatureTourItem[]; firstOpenedAt: string | null }
export interface FeatureTourParticipant {
  userId: string
  userName: string
  openedCount: number
  tourStarts: number
  completedItems: FeatureTourItem[]
  skippedItems: FeatureTourItem[]
  lastEventAt: string
}
export interface FeatureTourReport { openedUsers: number; openedEvents: number; tourStarts: number; participants: FeatureTourParticipant[] }
export interface PathProgressSummary {
  id: string
  templateId: string
  learnerId: string
  learnerName: string
  name: string
  status: 'not_started' | 'in_progress' | 'completed'
  completed: number
  skipped: number
  total: number
  completedTasks: number
  totalTasks: number
  progress: number
  createdAt: string
  lastActivityAt: string
  firstFinishedAt: string | null
  stepProgress?: PathProgressStage[]
}
export interface PathProgressStage {
  id: string
  title: string
  status: StepRun['status']
}
export interface PathProgressStep {
  id: string
  title: string
  type: 'task' | 'survey'
  status: StepRun['status']
  archived: boolean
  openedAt: string | null
  completedAt: string | null
  availableAt: string | null
  reasons: string[]
}
export interface PathProgressDetail extends PathProgressSummary {
  description: string
  templateRevision: number
  steps: PathProgressStep[]
}
export interface HelpRequest {
  id: string
  runId: string
  stepId: string
  modelId: string
  modelVersionId: string
  createdAt: string
  flowVersion?: 1 | 2
  stage: 'topic' | 'marking' | 'reflection' | 'action' | 'completed' | 'cancelled'
  surveyIds: Record<HelpSurveyPhase, string>
  markings: HelpMarkings | null
  nextAction: string | null
  nextActionId?: string | null
  surveySessionId?: string | null
  markingRequired: boolean
  markingPurpose?: 'problem' | 'feedback'
  supportKind?: string | null
  evaluationId?: string | null
}
export type HelpSurveyPhase = 'topic' | 'reflection' | 'action'
export interface HelpTextRange { start: number; end: number; text: string }
export interface HelpMarkings { cellIds: string[]; taskTextRanges: HelpTextRange[] }
export interface SurveySession { version: SurveyVersion; answers: Record<string, unknown>; revision: number; sessionId: string; releaseChanged: boolean; status: string }
const helpUrl = (runId: string, stepId: string, requestId: string) => `/v1/learning-path-runs/${runId}/steps/${stepId}/help-requests/${requestId}`
export default {
  featureTourProgress: () => http.get<FeatureTourProgress>('/v1/learning-path-feature-tour'),
  recordFeatureTourEvent: (event: 'opened' | 'started' | 'completed' | 'skipped', itemId?: FeatureTourItem) =>
    http.post<FeatureTourProgress>('/v1/learning-path-feature-tour/events', { event, ...(itemId ? { itemId } : {}) }),
  featureTourReport: () => http.get<FeatureTourReport>('/v1/learning-path-feature-tour/report'),
  exportProgressCsv: (runIds: string[]) => http.post<Blob>('/v1/learning-path-progress.csv', { runIds }, { responseType: 'blob' }),
  progressAccess: () => http.get<{ canView: boolean }>('/v1/learning-path-progress-access'),
  progress: (skip = 0) => http.get<ApiPage<PathProgressSummary>>('/v1/learning-path-progress', { params: { skip, limit: 100 } }),
  progressDetail: (id: string) => http.get<PathProgressDetail>(`/v1/learning-path-progress/${id}`),
  helpBlueprint: () => http.get<HelpBlueprint>('/v1/learning-path-help-blueprint'),
  helpDefaults: () => http.get<Record<HelpSurveyPhase, string>>('/v1/learning-path-help-defaults'),
  activeHelp: (runId: string, stepId: string) => http.get<HelpRequest | null>(`/v1/learning-path-runs/${runId}/steps/${stepId}/help-requests/active`),
  help: (runId: string, stepId: string, requestId: string) => http.get<HelpRequest>(helpUrl(runId, stepId, requestId)),
  cancelHelp: (runId: string, stepId: string, requestId: string) => http.post<HelpRequest>(`${helpUrl(runId, stepId, requestId)}/cancel`),
  saveHelpMarkings: (runId: string, stepId: string, requestId: string, markings: HelpMarkings) => http.put<HelpRequest>(`${helpUrl(runId, stepId, requestId)}/markings`, markings),
  reopenHelpMarkings: (runId: string, stepId: string, requestId: string) => http.post<HelpRequest>(`${helpUrl(runId, stepId, requestId)}/markings/reopen`),
  openHelpSurvey: (runId: string, stepId: string, requestId: string, phase: HelpSurveyPhase) => http.post<SurveySession>(`${helpUrl(runId, stepId, requestId)}/surveys/${phase}/open`),
  saveHelpSurveyDraft: (runId: string, stepId: string, requestId: string, phase: HelpSurveyPhase, answers: Record<string, unknown>, revision: number, sessionId: string) => http.put<{ revision: number }>(`${helpUrl(runId, stepId, requestId)}/surveys/${phase}/draft`, { answers, revision, sessionId }),
  submitHelpSurvey: (runId: string, stepId: string, requestId: string, phase: HelpSurveyPhase, answers: Record<string, unknown>, revision: number, sessionId: string) => http.post<SurveyResponse>(`${helpUrl(runId, stepId, requestId)}/surveys/${phase}/submit`, { answers, revision, sessionId }),
  requestHelp: (runId: string, stepId: string, requestId: string, modelVersionId: string) => http.post<HelpRequest>(`/v1/learning-path-runs/${runId}/steps/${stepId}/help-requests`, { requestId, modelVersionId }),
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
    const { name, description, visibility, revision, steps, pulseSurveys, helpRequests } = template
    const body = { name, description, visibility, revision, steps, pulseSurveys, helpRequests }
    return template.id ? http.put<PathTemplate>(`/v1/learning-path-templates/${template.id}`, body) : http.post<PathTemplate>('/v1/learning-path-templates', body)
  },
  start: (id: string) => http.post<PathRun>(`/v1/learning-path-templates/${id}/runs`),
  runs: (skip = 0) => http.get<ApiPage<PathRun>>('/v1/learning-path-runs', { params: { skip, limit: 100 } }),
  run: (id: string) => http.get<PathRun>(`/v1/learning-path-runs/${id}`),
  startStep: (runId: string, stepId: string, acknowledgedChallenge: ChallengeConfig | null = null) => http.post<{ modelId: string }>(`/v1/learning-path-runs/${runId}/steps/${stepId}/start`, { acknowledgedChallenge }),
  complete: (runId: string, stepId: string, evaluationId?: string) => http.post<PathRun>(`/v1/learning-path-runs/${runId}/steps/${stepId}/complete`, { evaluationId })
}
