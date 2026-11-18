import type { ApiId, ApiPage, JsonObject, ModelVersionReference, TaskVersionReference } from './common'

export interface EvaluationStep { id: string; label: string; description: string | null; status: string; resultSummary: string | null; result: JsonObject | null }
export interface EvaluationWorkflow { name: string; description: string | null; labels: JsonObject; steps: EvaluationStep[] }
export interface Evaluation { id: ApiId; ownerId: string; task: TaskVersionReference; submission: ModelVersionReference; dagName: string; dagRunId: string; startedAt: string; state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'unknown'; workflow: EvaluationWorkflow; parameters?: EvaluationParameters }
export interface TextEvidenceThresholds { spelling: number; meaning: number; meaningFloor: number }
// Must match TEXT_EVIDENCE_DEFAULTS in dagu/workflow-services/workflow-data/src/main.py.
export const textEvidenceDefaults: TextEvidenceThresholds = { spelling: 0.85, meaning: 0.85, meaningFloor: 0.7 }
// Admin-only overrides of the tier thresholds; null or absent runs the workflow defaults.
export interface EvaluationParameters { textEvidence?: TextEvidenceThresholds | null }
export interface EvaluationDetail extends Evaluation { submissionSnapshot: JsonObject; steps: EvaluationStep[]; finalResult: JsonObject | null; scorePercent: number | null }
export type EvaluationPage = ApiPage<Evaluation>
/** Learner-facing result: state, score and recognition overview only. */
export interface EvaluationFeedback { id: ApiId; startedAt: string; workflowName: string; submission: ModelVersionReference; state: Evaluation['state']; scorePercent: number | null; recognitions: { referenceKey: string; recognition: JsonObject }[] }
/** What the modeling view needs to decide on task completion; served by both detail and feedback. */
export type EvaluationOutcome = Pick<EvaluationFeedback, 'id' | 'state' | 'submission' | 'scorePercent'>
