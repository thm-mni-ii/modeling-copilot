import type { ApiId, ApiPage, JsonObject, ModelVersionReference, TaskVersionReference } from './common'

export interface EvaluationStep { id: string; label: string; description: string | null; status: string; resultSummary: string | null; result: JsonObject | null }
export interface EvaluationWorkflow { name: string; description: string | null; labels: JsonObject; steps: EvaluationStep[] }
export interface Evaluation { id: ApiId; ownerId: string; task: TaskVersionReference; submission: ModelVersionReference; dagName: string; dagRunId: string; startedAt: string; state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'unknown'; workflow: EvaluationWorkflow; parameters?: EvaluationParameters; feedbackTypes?: string[]; feedback?: EvaluationFeedback | null }
export interface TextEvidenceThresholds { spelling: number; meaning: number; meaningFloor: number }
// Must match TEXT_EVIDENCE_DEFAULTS in dagu/workflow-services/workflow-data/src/main.py.
export const textEvidenceDefaults: TextEvidenceThresholds = { spelling: 0.85, meaning: 0.85, meaningFloor: 0.7 }
// Admin-only overrides of the tier thresholds; null or absent runs the workflow defaults.
export interface EvaluationParameters { textEvidence?: TextEvidenceThresholds | null; helpRequestId?: ApiId | null; allFeedbackTypes?: boolean }
export interface EvaluationDetail extends Evaluation { submissionSnapshot: JsonObject; steps: EvaluationStep[]; finalResult: JsonObject | null; scorePercent: number | null }
export type EvaluationPage = ApiPage<Evaluation>
/** Learner-facing result: state, score and recognition overview only. */
export interface EvaluationFeedback { id: ApiId; startedAt: string; workflowName: string; submission: ModelVersionReference; state: Evaluation['state']; scorePercent: number | null; recognitions: { referenceKey: string; recognition: JsonObject }[]; feedback?: HelpFeedbackEntry[]; hints?: LabelHint[] }
export type LabelHintSource = 'text_band' | 'neighbor_profile' | 'child_overlap'
export type LabelHintRelation = 'notation' | 'reordered' | 'head_form' | 'part_of_term' | 'abbreviation' | 'same_stem'
export type LabelHintAction = 'shown' | 'accepted' | 'dismissed' | 'retained' | 'reverted' | 'removed'
/** A likely but unproven counterpart; never counted. `suggestion` is the sample-solution text while the probe allows it. */
export interface LabelHint { id: string; submissionId: string; submissionLabel: string; suggestion: string | null; sources: LabelHintSource[]; relation: LabelHintRelation | null; note?: string | null; state: 'new' | 'shown' | 'accepted' | 'dismissed'; retention?: 'retained' | 'reverted' | 'removed' | null }
// Learner help feedback produced by feedback-generation (feedback-report/v4); the API passes an allowlisted copy.
export type HelpFeedbackType = 'help.clarify' | 'help.check' | 'help.next_step' | 'help.example' | 'help.solution'
export type HelpFeedbackStatus = 'matches' | 'differs' | 'unclear'
export interface HelpFeedbackCheck { area: string; status: HelpFeedbackStatus; certainty: 'proven' | 'conditional'; messageCode: string; text: string }
export interface HelpFeedbackObject { cellId: string; label: string; kind: string; identity: 'recognized' | 'provisional' | 'unassigned' | 'not_evaluated'; notEvaluated: number; verdict?: HelpFeedbackStatus | 'not_evaluated'; checks: HelpFeedbackCheck[]; score?: HelpFeedbackScore | null; example?: HelpFeedbackExample | null; pattern?: HelpFeedbackPattern | null }
/** help.example: the sample solution's structure pattern around the counterpart of `cellId` (maxGraph XML). */
export interface HelpFeedbackPattern { cellId: string; expected?: string }
/** help.example: the matching sample-solution element, rendered from its language definition. */
export interface HelpFeedbackExample { kind: string; label: string; typeName: string; definition: Record<string, unknown> | null; xml?: string | null }
/** help.check: present versus expected per countable part of one object. */
export interface HelpFeedbackScore { percent: number; parts: { label: string; present: number; expected: number; text?: string }[]; hint: string | null }
export interface HelpFeedbackNote { cellId: string; text: string }
export interface HelpFeedbackFocus { cellIds: string[]; area: string | null; issueKey: string | null; messageCode: string; text: string; repeated: boolean }
export interface HelpFeedbackEntry { type: HelpFeedbackType | string; referenceKey?: string; overview: { recognized: number; expected: number; percent: number | null; evaluationStatus: string }; notices: string[]; objects?: HelpFeedbackObject[]; /** help.check: observations on open elements (e.g. same-named copies), shown as info at the element. */ notes?: HelpFeedbackNote[]; focus?: HelpFeedbackFocus; recognition?: JsonObject; /** false: no marked object could be related to the sample solution, so the help quota is not used. */ referenced?: boolean }
/** What the modeling view needs to decide on task completion; served by both detail and feedback. */
export type EvaluationOutcome = Pick<EvaluationFeedback, 'id' | 'state' | 'submission' | 'scorePercent'>
/** Staff-only `help.catalog`: every submission object with the help feedback learners would get for it alone. */
export interface HelpFeedbackCatalogObject { cellId: string; label: string; typeName: string; help: Record<HelpFeedbackType, Partial<Pick<HelpFeedbackEntry, 'objects' | 'notes' | 'focus' | 'notices' | 'recognition'>>> }
