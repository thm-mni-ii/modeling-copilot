"""Schemas for workflow-backed model evaluations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from modeling_api.schemas.common import ApiSchema, JsonObject, ModelVersionReference, TaskVersionReference

EvaluationState = Literal["queued", "running", "succeeded", "failed", "cancelled", "unknown"]


class WorkflowStep(ApiSchema):
    id: str
    label: str
    description: str | None = None
    status: str = "pending"
    result_summary: str | None = None
    result: JsonObject | None = None


class EvaluationWorkflow(ApiSchema):
    name: str
    description: str | None = None
    labels: JsonObject = Field(default_factory=dict)
    steps: list[WorkflowStep] = Field(default_factory=list)


class Evaluation(ApiSchema):
    id: UUID
    owner_id: str
    task: TaskVersionReference
    submission: ModelVersionReference
    dag_name: str
    dag_run_id: str
    started_at: datetime
    state: EvaluationState = "queued"
    workflow: EvaluationWorkflow


class EvaluationDetail(Evaluation):
    submission_snapshot: JsonObject
    steps: list[WorkflowStep] = Field(default_factory=list)
    final_result: JsonObject | None = None


class StartEvaluation(ApiSchema):
    """Intentionally empty: the task's admin-selected workflow is authoritative."""
