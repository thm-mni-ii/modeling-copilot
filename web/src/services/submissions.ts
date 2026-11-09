import http from './api/httpClient'
import type { ApiPage } from './api/types/common'
import type { Assignment, AssignmentData, DirectoryUser, GlobalFeedbackSettings, PublicationRequest, ReviewEntry, RunData, SubmissionAccess, SubmissionCourses, SubmissionCourseDetail, SubmissionDetail, SubmissionRow, SubmissionRun, SubmissionView } from './api/types/submission'
import type { ModelPackage } from '@/utils/modelPackage'

export const submissions = {
  access: () => http.get<SubmissionAccess>('/v1/submission-access'),
  courses: () => http.get<SubmissionCourses>('/v1/submission-courses'),
  course: (id: string) => http.get<SubmissionCourseDetail>(`/v1/submission-courses/${id}`),
  enroll: (id: string) => http.post<{ enrolled: boolean }>(`/v1/submission-runs/${id}/enrollment`),
  list: (skip = 0, archived = false) => http.get<ApiPage<Assignment> & { canCreate: boolean }>('/v1/submission-assignments', { params: { skip, limit: 20, archived } }),
  assignment: (id: string) => http.get<Assignment>(`/v1/submission-assignments/${id}`),
  saveAssignment: (id: string | null, data: AssignmentData & { baseRevision: number; archived: boolean }) => (id ? http.put<Assignment>(`/v1/submission-assignments/${id}`, data) : http.post<Assignment>('/v1/submission-assignments', data)),
  startRun: (id: string, data: RunData & { assignmentRevision: number }) => http.post<SubmissionRun>(`/v1/submission-assignments/${id}/runs`, data),
  run: (id: string, view?: SubmissionView) => http.get<SubmissionRun>(`/v1/submission-runs/${id}`, { params: { view } }),
  saveRun: (id: string, data: RunData & { baseRevision: number }) => http.put<SubmissionRun>(`/v1/submission-runs/${id}`, data),
  listSubmissions: (id: string, skip = 0, history = false, view?: SubmissionView) => http.get<ApiPage<SubmissionRow>>(`/v1/submission-runs/${id}/submissions`, { params: { skip, limit: 100, history, view } }),
  exportCsv: (id: string) => http.get<Blob>(`/v1/submission-runs/${id}/submissions.csv`, { responseType: 'blob' }),
  submit: (id: string, data: { package?: ModelPackage; modelId?: string; versionId?: string; modelName?: string; baseSubmissionId: string | null }) => http.post<SubmissionDetail>(`/v1/submission-runs/${id}/submissions`, data),
  submission: (id: string, view?: SubmissionView) => http.get<SubmissionDetail>(`/v1/submissions/${id}`, { params: { view } }),
  saveReview: (id: string, kind: string, data: { entries: ReviewEntry[]; score: number | null; baseRevision: number; action: 'save' | 'complete' | 'reopen' }, view?: SubmissionView) => http.put<SubmissionDetail>(`/v1/submissions/${id}/reviews/${kind}`, data, { params: { view } }),
  publish: (id: string, reviews: PublicationRequest[]) => http.post<{ items: Array<{ reviewId: string; published: boolean; message: string }> }>(`/v1/submission-runs/${id}/publish`, { reviews }),
  resolve: (id: string, data: { reviewId: string; publication: number; entryId: string; resolved: boolean }) => http.put(`/v1/submissions/${id}/resolved`, data),
  users: (q = '', runId?: string) => http.get<ApiPage<DirectoryUser>>('/v1/submission-users', { params: { q, runId } }),
  settings: (revision?: number) => http.get<GlobalFeedbackSettings>('/v1/global-feedback-settings', { params: { revision } }),
  saveSettings: (settings: GlobalFeedbackSettings) => http.put<GlobalFeedbackSettings>('/v1/global-feedback-settings', { baseRevision: settings.revision, overlays: settings.overlays })
}

export const submissionError = (error: unknown) => {
  const response = error as { response?: { data?: { message?: string } }; message?: string }
  return response.response?.data?.message ?? response.message ?? 'The action could not be completed.'
}
