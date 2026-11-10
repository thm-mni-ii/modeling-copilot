import type { FeedbackState } from '@/model/Feedback'
import type { ReviewEntry } from '@/services/api/types/submission'

/** Selecting an existing marking never removes it; correctness changes retain the comment and ID. */
export const selectFeedbackMark = (entries: ReviewEntry[], cellId: string, state: FeedbackState, createId: () => string): { entries: ReviewEntry[]; selectedId: string; changed: boolean } => {
  const existing = entries.find((entry) => entry.cellId === cellId && entry.state === state)
  if (existing) return { entries, selectedId: existing.id, changed: false }
  const previous = state === 'hint' ? undefined : entries.find((entry) => entry.cellId === cellId && entry.state !== 'hint')
  const entry: ReviewEntry = previous ? { ...previous, state } : { id: createId(), cellId, state, comment: '' }
  return { entries: previous ? entries.map((item) => (item.id === previous.id ? entry : item)) : [...entries, entry], selectedId: entry.id, changed: true }
}

export const reviewStatusLabel = (status: string) => ({ draft: 'Draft - private to reviewers', complete: 'Ready to publish', published: 'Feedback published' })[status] ?? status
