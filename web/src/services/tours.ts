import http from '@/services/api/httpClient'

export type TourEventName = 'opened' | 'started' | 'step' | 'completed' | 'skipped'
export interface TourProgress {
  completed: boolean
  skipped: boolean
}

export default {
  progress: (tourId: string) => http.get<TourProgress>(`/v1/tours/${tourId}/progress`),
  recordEvent: (tourId: string, event: TourEventName, stepId?: string) => http.post<TourProgress>(`/v1/tours/${tourId}/events`, { event, ...(stepId ? { stepId } : {}) })
}
