import type { ApiId, ApiPage, JsonObject, ModelVersionReference, TaskVersionReference } from './common'

export interface EvaluationStep { id: string; label: string; description: string | null; status: string; resultSummary: string | null; result: JsonObject | null }
export interface EvaluationWorkflow { name: string; description: string | null; labels: JsonObject; steps: EvaluationStep[] }
export interface Evaluation { id: ApiId; ownerId: string; task: TaskVersionReference; submission: ModelVersionReference; dagName: string; dagRunId: string; startedAt: string; state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'unknown'; workflow: EvaluationWorkflow }
export interface EvaluationDetail extends Evaluation { submissionSnapshot: JsonObject; steps: EvaluationStep[]; finalResult: JsonObject | null }
export type EvaluationPage = ApiPage<Evaluation>
