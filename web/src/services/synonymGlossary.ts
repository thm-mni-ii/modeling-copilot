import http from '@/services/api/httpClient'

export type EntryStatus = 'accepted' | 'rejected' | 'ignored'
export type RecalculateScope = 'missing' | 'all'

export interface EvaluableRelease { id: string; versionNumber: number; sampleSolutions: { modelId: string; versionId: string }[] }
export interface EvaluableTask { id: string; name: string; releases: EvaluableRelease[] }
export interface GlossaryElement { id: string; label: string; targetKind: 'element' | 'connection'; type: string | null; comparisonGroup: string | null }
export interface GlossaryEntry { id: string; referenceElementId: string; term: string; termKey: string; status: EntryStatus; origin: 'manual' | 'suggestion'; updatedAt: string; matchingSource: boolean }
export interface Suggestion {
  referenceElementId: string
  term: string
  termKey: string
  variants: { text: string; count: number }[]
  persons: number
  submissions: number
  evidence: { contextUnique: number; contextBest: number; textOnly: number; recognized: number; hintAccepted?: number }
  comparisons: TermComparison[]
  alsoSuggestedFor: { referenceElementId: string; label: string; persons: number }[]
}
export interface SignalJob { id: string; scope: RecalculateScope; state: 'running' | 'completed'; total: number; done: number; failed: number }
export interface SignalStatus { evaluated: number; collected: number; missing: number; unavailable: boolean; job: SignalJob | null }
export interface OutcomeCounts { counted: number; partial?: number; notCounted: number; countedElsewhere: number; countedAtSameName?: number; unknown: number; usedForLearnerResult: number }
export interface OutcomeOccurrence { evaluationId: string; modelVersionId: string; submissionElementId: string | null; state: 'counted' | 'partial' | 'not_counted' | 'counted_elsewhere' | 'unknown'; usedForLearnerResult: boolean; evidenceNote: string | null; reason?: string | null }
export interface TermComparison { referenceText: string; submissionText: string; method: string; minimum: number; maximum: number; acceptance?: number | null; floor?: number | null; referenceForm?: string | null; submissionForm?: string | null }
export interface OutcomeGroup { key: string; conditions: Record<string, string>; cases: number; comparisons: TermComparison[]; counts: OutcomeCounts; reasons: Record<string, number> }
export interface TermOutcome { referenceElementId: string; term: string; termKey: string; counts: OutcomeCounts; reasons?: Record<string, number>; occurrences: OutcomeOccurrence[]; comparisons: TermComparison[]; groups?: OutcomeGroup[] }
export interface OutcomeExplanation {
  submissionElementId: string | null
  submissionLabel: string
  referenceLabel: string
  state: OutcomeOccurrence['state']
  summary: string
  candidateReason: string
  resultReason: string
  evidenceScope: 'pair' | 'submission' | 'suggestion'
  checks: { method: string; result: string; role: string; note: string }[]
  similarities: { method: string; score: number | null; thresholds: Record<string, number>; confirmationFloors: Record<string, number>; referenceText: string | null }[]
  alternatives: { referenceElementId: string; referenceLabel: string; submissionElementId: string; submissionLabel: string; counted: boolean }[]
  limitations: string[]
}
export interface TextEvidence { spelling: number; meaning: number; meaningFloor: number }
export interface ReplayItem { evaluationId: string; modelVersionId: string; runId: string; status: 'pending' | 'running' | 'done' | 'failed'; beforePercent: number | null; afterPercent: number | null; error: string | null }
export interface ReplayBatch { id: string; state: 'running' | 'completed'; createdAt: string; expiresAt: string; workflowName: string; workflowVersion: string | null; textEvidence: TextEvidence | null; items: ReplayItem[]; outcomes: TermOutcome[]; unavailable: boolean }
export interface MatchingWorkload { basis: 'text_pairs' | 'reference_texts'; baseline: number; additional: number; total: number; percent: number | null; covered: number; evaluated: number }
export interface GlossaryView { revision: number; elements: GlossaryElement[]; entries: GlossaryEntry[]; suggestions: Suggestion[]; signals: SignalStatus; outcomes: TermOutcome[]; outcomesUnavailable: number; matchingWorkload: MatchingWorkload }
export interface GlossaryChange { referenceElementId: string; term: string; status: EntryStatus | null }
export interface SolutionRef { taskId: string; versionId: string; modelId: string; modelVersionId: string }

const solutionPath = (ref: SolutionRef) => `/v1/synonym-glossary/tasks/${ref.taskId}/versions/${ref.versionId}/solutions/${ref.modelId}/${ref.modelVersionId}`
const signalPath = (taskId: string, versionId: string) => `/v1/synonym-glossary/tasks/${taskId}/versions/${versionId}/signals`

export const synonymGlossary = {
  tasks: () => http.get<EvaluableTask[]>('/v1/synonym-glossary/tasks'),
  solution: (ref: SolutionRef, excludeOwn = false, excludeStaff = true) => http.get<GlossaryView>(solutionPath(ref), { params: { exclude_own: excludeOwn, exclude_staff: excludeStaff } }),
  save: (ref: SolutionRef, baseRevision: number, changes: GlossaryChange[]) => http.post<GlossaryView>(`${solutionPath(ref)}/entries`, { baseRevision, changes }),
  setMatchingSource: (ref: SolutionRef, entryId: string, baseRevision: number, enabled: boolean) =>
    http.post<GlossaryView>(`${solutionPath(ref)}/entries/${entryId}/matching-source`, { baseRevision, enabled }),
  importEntries: (ref: SolutionRef, fromReferenceVersionId: string, baseRevision: number) =>
    http.post<{ imported: number; skipped: string[]; glossary: GlossaryView }>(`${solutionPath(ref)}/entries/import`, { fromReferenceVersionId, baseRevision }),
  recalculate: (taskId: string, versionId: string, scope: RecalculateScope) => http.post<SignalStatus>(`${signalPath(taskId, versionId)}/recalculate`, { scope }),
  status: (taskId: string, versionId: string) => http.get<SignalStatus>(`${signalPath(taskId, versionId)}/status`),
  explainOutcome: (ref: SolutionRef, outcome: TermOutcome, occurrence: OutcomeOccurrence, replayId: string | null) =>
    http.post<OutcomeExplanation[]>(`${solutionPath(ref)}/outcomes/explain`, { evaluationId: occurrence.evaluationId, referenceElementId: outcome.referenceElementId, termKey: outcome.termKey, submissionElementId: occurrence.submissionElementId, replayId }),
  replays: (ref: SolutionRef) => http.get<ReplayBatch[]>(`${solutionPath(ref)}/replays`),
  startReplay: (ref: SolutionRef, textEvidence: TextEvidence | null) => http.post<ReplayBatch>(`${solutionPath(ref)}/replays`, { textEvidence }),
  replay: (ref: SolutionRef, id: string) => http.get<ReplayBatch>(`${solutionPath(ref)}/replays/${id}`),
  deleteReplay: (ref: SolutionRef, id: string) => http.delete(`${solutionPath(ref)}/replays/${id}`)
}
