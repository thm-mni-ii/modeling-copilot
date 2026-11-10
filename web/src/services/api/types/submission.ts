import type { FeedbackState, FeedbackTargetOverlays } from '@/model/Feedback'
import type { ModelPackage } from '@/utils/modelPackage'
import type { TaskVersionReference } from './common'

export interface AssignmentData {
  name: string
  description: string
  taskVersion: TaskVersionReference | null
}
export interface Assignment {
  id: string
  name: string
  data: AssignmentData
  revision: number
  archived: boolean
  history?: Array<{ revision: number; data: AssignmentData }>
  canManage?: boolean
  runs?: SubmissionRun[]
  activeRunId?: string | null
}
export type SubmissionView = 'participant' | 'management'
export interface SubmissionAccess {
  canManage: boolean
  canCreate: boolean
}
export interface SubmissionCourse {
  id: string
  name: string
  description: string
  enrolled: boolean
  hasHistory: boolean
  activeRunId: string | null
  canEnroll: boolean
  deadline?: string | null
  submissionStatus?: string
}
export interface SubmissionCourseDetail {
  id: string
  name: string
  description: string
  activeRunId: string | null
  canModerate: boolean
  runs: Array<{ id: string; name: string; enrolled: boolean }>
}
export interface SubmissionCourses extends SubmissionAccess {
  items: SubmissionCourse[]
}
export interface RunGrant {
  userId: string
  manage: boolean
  review: boolean
  publish: boolean
}
export interface RunData {
  name: string
  deadline: string
  state: 'open' | 'closed' | 'archived'
  participation: 'all' | 'selected'
  participantIds?: string[]
  grants?: RunGrant[]
}
export interface SubmissionPermissions {
  manage: boolean
  review: boolean
  publish: boolean
}
export interface SubmissionRun {
  id: string
  assignmentId: string
  assignmentRevision: number
  revision: number
  data: RunData
  permissions: SubmissionPermissions
  canSubmit: boolean
  enrolled: boolean
  canEnroll: boolean
  canModerate: boolean
  managementView: boolean
  submissionBlockedReason?: 'archived' | 'closed' | 'deadline' | 'not_eligible' | 'not_enrolled' | 'review_started' | null
  assignment?: AssignmentData
  history?: Array<{ revision: number; data: RunData; at: string; by: string }>
}
export interface ReviewEntry {
  id: string
  cellId: string
  state: FeedbackState
  comment: string
  createdBy?: string
  updatedBy?: string
  updatedAt?: string | null
}
export interface ReviewPublication {
  id: string
  number: number
  entries: ReviewEntry[]
  score: number | null
  configRevision: number
  publishedBy: string
  createdAt: string
}
export interface SubmissionReview {
  id: string
  // Older published feedback keeps its producer type; peer assignment is no longer supported.
  kind: string
  revision: number
  status: 'draft' | 'complete' | 'published'
  reviewerId: string | null
  entries?: ReviewEntry[]
  score?: number | null
  published?: ReviewPublication
  configRevision: number
  publication: number
}
export interface SubmissionRow {
  id: string
  runId: string
  ownerId: string
  ownerName?: string
  modelName?: string
  createdAt: string
  current: boolean
  status: string
  reviews: SubmissionReview[]
  reviewStarted?: boolean
}
export interface SubmissionDetail extends SubmissionRow {
  package: ModelPackage
  permissions: SubmissionPermissions
  resolved: string[]
  isOwner: boolean
  reviewStarted: boolean
  runState: RunData['state']
  revision: number
  sourceModelId: string | null
  assignmentId: string
  managementView: boolean
  canModerate: boolean
  people?: Record<string, string>
}
export interface DirectoryUser {
  id: string
  name: string
}
export interface GlobalFeedbackSettings {
  revision: number
  overlays: FeedbackTargetOverlays
}
export interface PublicationRequest {
  submissionId: string
  reviewId: string
  revision: number
}
export const submissionStatus = (status: string) => ({ not_submitted: 'Not submitted yet', submitted: 'Submitted', in_review: 'Being reviewed', reviewed: 'Ready to publish', feedback_available: 'Feedback available' })[status] ?? status
