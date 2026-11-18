"""Schemas for workflow-backed model evaluations."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

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


class ReferenceRecognition(ApiSchema):
    reference_key: str
    recognition: JsonObject


class EvaluationFeedback(ApiSchema):
    """Learner-facing result; never carries artifacts, logs or reference-model content."""

    id: UUID
    started_at: datetime
    workflow_name: str
    submission: ModelVersionReference
    state: EvaluationState
    score_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    recognitions: list[ReferenceRecognition] = Field(default_factory=list)
    feedback: list[JsonObject] = Field(default_factory=list, description="Requested feedback entries other than the recognition overview, by type.")


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
    parameters: JsonObject = Field(default_factory=dict)
    feedback: EvaluationFeedback | None = Field(default=None, description="Published learner feedback, when already available.")


class EvaluationDetail(Evaluation):
    submission_snapshot: JsonObject
    steps: list[WorkflowStep] = Field(default_factory=list)
    final_result: JsonObject | None = None
    score_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False,
                                      description="Final model score. Null until the scoring integration supplies it.")


Threshold = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class TextEvidenceThresholds(ApiSchema):
    """Admin overrides of the text-evidence tier thresholds; workflow-data owns the defaults."""

    spelling: Threshold
    meaning: Threshold
    meaning_floor: Threshold

    @model_validator(mode="after")
    def floor_below_meaning(self):
        if self.meaning_floor > self.meaning:
            raise ValueError("meaningFloor must not exceed meaning")
        return self


class StartEvaluation(ApiSchema):
    """The task's admin-selected workflow is authoritative; administrators may tune its parameters."""

    text_evidence: TextEvidenceThresholds | None = Field(
        default=None, description="Tier thresholds for this run; null keeps the workflow defaults.")
    help_request_id: UUID | None = Field(
        default=None, description="Completed help request whose requested feedback type this run produces.")
