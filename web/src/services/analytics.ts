import http from '@/services/api/httpClient'
import type { PathVisibility } from '@/services/learningPaths'
import type { TourEventName } from '@/services/tours'
import type { ApiPage } from '@/services/api/types/common'
import type { EvaluationFeedback } from '@/services/api/types/evaluation'

export interface PathAnalytics {
  id: string
  name: string
  visibility: PathVisibility
  revision: number
  participants: number
  notStarted: number
  inProgress: number
  completed: number
  stalled: number
  avgProgress: number
  completionRate: number
  medianSecondsToFinish: number | null
  lastActivityAt: string | null
}
export interface PathAnalyticsDetail extends PathAnalytics { description: string; hiddenStaffRuns: number }
export interface TourAnalytics {
  id: string
  title: string
  version: number
  openedUsers: number
  startedUsers: number
  completedUsers: number
  skippedUsers: number
  completionRate: number
  lastActivityAt: string | null
}
export interface TourSummary {
  tours: number
  openedUsers: number
  startedUsers: number
  completedUsers: number
  skippedUsers: number
  completionRate: number
  knownUsers: number
  coverage: number
}
export interface TourWeek { weekStart: string; starts: number; completions: number }
export interface TourOverview { summary: TourSummary; weekly: TourWeek[]; tours: TourAnalytics[] }
export interface TourFunnelStep { id: string; title: string; reached: number; leftHere: number; biggestDropOff: boolean }
export type TourParticipantStatus = 'opened' | 'in_progress' | 'completed' | 'skipped'
export interface TourParticipant {
  userId: string
  userName: string
  status: TourParticipantStatus
  furthestStepId: string | null
  opens: number
  starts: number
  firstEventAt: string
  lastEventAt: string
}
export interface TourAnalyticsDetail extends TourAnalytics { steps: TourFunnelStep[]; participants: TourParticipant[] }
export interface TourTimelineEvent { event: TourEventName; stepId: string | null; stepTitle: string | null; at: string }

export type PlatformPeriod = '7d' | '30d' | 'semester' | 'all'
export interface CountItem { key: string; count: number }
export interface WeekPoint { weekStart: string; count: number }
export interface PlatformKpis {
  knownUsers: number
  newUsers: number
  activeUsersWeek: number
  activeUsersMonth: number
  usersWithModels: number
  models: number
  modelsArchived: number
  avgModelsPerUser: number | null
  medianModelsPerUser: number | null
  checkpoints: number
  releases: number
}
export interface PlatformOverview {
  period: PlatformPeriod
  since: string | null
  kpis: PlatformKpis
  weeklyActiveUsers: WeekPoint[]
  weeklyNewModels: WeekPoint[]
  modelsPerUser: { label: string; users: number }[]
}
export interface PlatformTaskKpis {
  tasksPublished: number
  tasksHidden: number
  tasksArchived: number
  evaluations: number
  evaluationsLastWeek: number
  evaluationsByState: CountItem[]
}
export interface PlatformTask { taskId: string; taskName: string; persons: number; models: number; evaluations: number; avgScore: number | null }
export interface PlatformTasks { period: PlatformPeriod; since: string | null; kpis: PlatformTaskKpis; tasks: PlatformTask[] }
export type PlatformPersonSort = 'name' | 'lastSeenAt' | 'models' | 'tasks' | 'evaluations' | 'helpRequests' | 'sessionSeconds'
export interface PlatformPerson {
  userId: string
  userName: string
  lastSeenAt: string | null
  models: number
  tasks: number
  evaluations: number
  helpRequests: number
  sessionSeconds: number
}

export interface HistogramBin { label: string; users: number }
export interface HelpFunnel { requests: number; topicDone: number; reflectionDone: number; completed: number; cancelled: number; open: number; abortRate: number | null }
export interface StepFeedback {
  stepId: string
  title: string
  persons: number
  attemptPersons: number
  attempts: number
  avgAttempts: number | null
  attemptDistribution: HistogramBin[]
  minimumScorePercent: number | null
  passedPersons: number | null
  passedShare: number | null
  scoredPersons: number
  avgFirstScore: number | null
  avgBestScore: number | null
  scoreBands: HistogramBin[]
  scoreCurve: { attempt: number; avgScore: number | null; scored: number }[]
  support: { kind: string; persons: number; requests: number }[]
  limits: { kind: string; limit: number | null; exhausted: number | null; share: number | null }[]
  help: HelpFunnel
}
export interface PulseStats {
  offers: number
  opened: number
  answered: number
  dismissed: number
  expired: number
  pending: number
  openRate: number | null
  answerRate: number | null
  dismissRate: number | null
  expiredRate: number | null
  sessions: number
  offersPerSession: number | null
  surveys: { surveyId: string; name: string; offered: number; answered: number; answerRate: number | null }[]
}
export interface PathFeedback {
  steps: StepFeedback[]
  help: HelpFunnel
  pulse: PulseStats
  helpAnswers: { name: string; title: string; responses: number; options: CountItem[] }[]
}
export interface AttemptEvent {
  at: string
  type: 'evaluation' | 'help_request'
  evaluationId: string | null
  state: string | null
  scorePercent: number | null
  passed: boolean | null
  supportKind: string | null
  helpStage: string | null
}
export interface AttemptModel {
  evaluationId: string
  stepId: string
  stepTitle: string
  startedAt: string
  modelVersionId: string | null
  xml: string
  feedback: EvaluationFeedback | null
}
export interface StepAttempts { stepId: string; title: string; events: AttemptEvent[] }
export interface ActivityStats {
  persons: number
  sessions: number
  openSessions: number
  avgSessionsPerPerson: number | null
  sessionDistribution: HistogramBin[]
  avgGrossSeconds: number | null
  medianGrossSeconds: number | null
  avgActiveSeconds: number | null
  medianActiveSeconds: number | null
  avgSessionSeconds: number | null
  tabHiddenPerPerson: number | null
  focusLostPerPerson: number | null
  tabHiddenPerSession: number | null
  focusLostPerSession: number | null
  outsideShare: number | null
}
export interface StepActivity extends ActivityStats { stepId: string; title: string }
export interface ActivityTotals { sessions: number; grossSeconds: number; activeSeconds: number; tabHidden: number; focusLost: number }
export interface RunActivity extends ActivityTotals { runId: string; steps: (ActivityTotals & { stepId: string })[] }
export interface PathActivity { path: ActivityStats; steps: StepActivity[]; runs: RunActivity[] }

export interface SurveyStatusCounts { responses: number; submitted: number; skipped: number; draft: number }
export interface SurveyAnalytics extends SurveyStatusCounts {
  id: string
  title: string
  kind: 'standard' | 'help'
  activeReleaseVersion: number | null
  submittedShare: number | null
  skippedShare: number | null
  draftShare: number | null
  lastResponseAt: string | null
}
export interface SurveyReleaseInfo { id: string; version: number; releasedAt: string | null; active: boolean; submitted: number }
export interface SurveyOption { key: string; label: string; count: number }
export interface SurveyTrendPoint { weekStart: string; responses: number; mean: number | null }
export interface SurveyQuestionStats {
  name: string
  title: string
  type: string
  kind: 'choice' | 'rating' | 'text' | 'other'
  responses: number
  mean: number | null
  median: number | null
  avgLength: number | null
  scaleMin: number | null
  scaleMax: number | null
  minLabel: string | null
  maxLabel: string | null
  options: SurveyOption[]
  trend: SurveyTrendPoint[]
}
export type SurveyContext = 'all' | 'path' | 'pulse' | 'help'
export interface SurveyAnalyticsDetail extends SurveyStatusCounts {
  submittedLastWeek: number
  completionShare: number | null
  lastResponseAt: string | null
  id: string
  title: string
  kind: 'standard' | 'help'
  release: SurveyReleaseInfo | null
  releases: SurveyReleaseInfo[]
  context: SurveyContext
  contextCounts: CountItem[]
  questions: SurveyQuestionStats[]
}

export interface PathSurveyRating { name: string; title: string; responses: number; responsesLastWeek: number; meanOverall: number | null; meanLastWeek: number | null }
export interface PathSurveyRelease {
  id: string
  version: number
  releasedAt: string | null
  active: boolean
  submitted: number
  ratings: PathSurveyRating[]
  questions: SurveyQuestionStats[]
}
export interface PathSurvey extends SurveyStatusCounts {
  submittedLastWeek: number
  submittedPreviousWeek: number
  completionShare: number | null
  lastResponseAt: string | null
  id: string
  title: string
  usages: string[]
  releases: PathSurveyRelease[]
}
export interface PathSurveys { surveys: PathSurvey[] }

export default {
  paths: () => http.get<PathAnalytics[]>('/v1/analytics/learning-paths'),
  path: (templateId: string, includeStaff: boolean) => http.get<PathAnalyticsDetail>(`/v1/analytics/learning-paths/${templateId}`, { params: { includeStaff } }),
  pathFeedback: (templateId: string, includeStaff: boolean) => http.get<PathFeedback>(`/v1/analytics/learning-paths/${templateId}/feedback`, { params: { includeStaff } }),
  pathActivity: (templateId: string, includeStaff: boolean) => http.get<PathActivity>(`/v1/analytics/learning-paths/${templateId}/activity`, { params: { includeStaff } }),
  pathSurveys: (templateId: string, includeStaff: boolean) => http.get<PathSurveys>(`/v1/analytics/learning-paths/${templateId}/surveys`, { params: { includeStaff } }),
  pathAttempts: (templateId: string, runId: string) =>
    http.get<StepAttempts[]>(`/v1/analytics/learning-paths/${templateId}/participants/${runId}/attempts`),
  attemptModel: (templateId: string, runId: string, evaluationId: string) =>
    http.get<AttemptModel>(`/v1/analytics/learning-paths/${templateId}/participants/${runId}/attempts/${evaluationId}/model`),
  platform: (period: PlatformPeriod, includeStaff: boolean) =>
    http.get<PlatformOverview>('/v1/analytics/platform', { params: { period, includeStaff } }),
  platformTasks: (period: PlatformPeriod, includeStaff: boolean) =>
    http.get<PlatformTasks>('/v1/analytics/platform/tasks', { params: { period, includeStaff } }),
  platformPersons: (period: PlatformPeriod, includeStaff: boolean, sortBy: PlatformPersonSort, sortDesc: boolean, skip: number, limit: number) =>
    http.get<ApiPage<PlatformPerson>>('/v1/analytics/platform/persons', { params: { period, includeStaff, sortBy, sortDesc, skip, limit } }),
  tours: (includeStaff: boolean) => http.get<TourOverview>('/v1/analytics/tours', { params: { includeStaff } }),
  tour: (tourId: string) => http.get<TourAnalyticsDetail>(`/v1/analytics/tours/${tourId}`),
  tourTimeline: (tourId: string, userId: string) =>
    http.get<TourTimelineEvent[]>(`/v1/analytics/tours/${tourId}/participants/${encodeURIComponent(userId)}/events`),
  surveys: () => http.get<SurveyAnalytics[]>('/v1/analytics/surveys'),
  survey: (surveyId: string, release: string | null, context: SurveyContext) =>
    http.get<SurveyAnalyticsDetail>(`/v1/analytics/surveys/${surveyId}`, { params: { release: release ?? undefined, context } })
}
