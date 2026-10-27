"""Mutable learning-path configuration and personal runs."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from modeling_api.schemas.common import (
    ApiSchema,
    Name,
    TaskVersionReference,
)
from modeling_api.schemas.challenges import ChallengeConfig, ChallengeAttempt


class UnlockCondition(ApiSchema):
    type: Literal["completed", "score", "at", "after"]
    step_id: UUID | None = None
    value: float | None = Field(default=None, ge=0, le=100)
    at: AwareDatetime | None = None
    timezone: str = "Europe/Berlin"
    seconds: int | None = Field(default=None, ge=0, le=315360000)

    @model_validator(mode="after")
    def valid_condition(self):
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError("Unknown timezone.") from exc
        if self.type == "score":
            raise ValueError("Score conditions are not available yet.")
        if self.type in ("completed", "score") and self.step_id is None:
            raise ValueError("A source step is required.")
        if self.type == "score" and self.value is None:
            raise ValueError("A minimum percentage is required.")
        if self.type == "at" and self.at is None:
            raise ValueError("A timestamp with timezone is required.")
        if self.type == "after" and self.seconds is None:
            raise ValueError("A delay is required.")
        return self


class UnlockRule(ApiSchema):
    # sequence: every earlier, active, non-optional step must be completed.
    mode: Literal["sequence", "all", "any"] = "sequence"
    conditions: list[UnlockCondition] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def sequence_has_no_conditions(self):
        if self.mode == "sequence" and self.conditions:
            raise ValueError("Sequential unlocking takes no explicit conditions.")
        return self


class LearningPathStep(ApiSchema):
    id: UUID
    title: Name
    type: Literal["task", "survey"] = "task"
    task_version: TaskVersionReference | None = None
    survey_id: UUID | None = None
    before_survey_id: UUID | None = None
    after_survey_id: UUID | None = None
    required: bool = True
    unlock: UnlockRule = Field(default_factory=UnlockRule)
    challenge: ChallengeConfig | None = None

    @model_validator(mode="after")
    def valid_activity(self):
        if self.type == "task":
            if not self.task_version or self.survey_id or not self.required:
                raise ValueError("Tasks require a task release and must be required.")
        elif (
            not self.survey_id
            or self.task_version
            or self.challenge
            or self.before_survey_id
            or self.after_survey_id
        ):
            raise ValueError(
                "Questionnaires require a survey and cannot have task settings."
            )
        return self


class PulseSurveyConfig(ApiSchema):
    enabled: bool = False
    survey_ids: list[UUID] = Field(default_factory=list, max_length=100)
    min_gap_seconds: int = Field(default=600, ge=1, le=86400)
    max_gap_seconds: int | None = Field(default=1800, ge=1, le=86400)
    max_per_session: int = Field(default=3, ge=1, le=100)
    max_per_task: int | None = Field(default=None, ge=1, le=1000)
    min_active_seconds: int = Field(default=120, ge=0, le=86400)
    exclude_step_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def valid_pulse(self):
        if self.enabled and not self.survey_ids:
            raise ValueError("Enabled pulse surveys require a questionnaire pool.")
        if len(set(self.survey_ids)) != len(self.survey_ids):
            raise ValueError("Pulse questionnaire IDs must be unique.")
        if self.max_gap_seconds is not None and self.max_gap_seconds < self.min_gap_seconds:
            raise ValueError("Maximum pulse gap must be at least the minimum gap.")
        return self


class PulsePoll(ApiSchema):
    session_key: UUID
    active_seconds_delta: int = Field(default=0, ge=0, le=30)


class PulseOffer(ApiSchema):
    id: UUID
    survey_id: UUID


class PulsePollResult(ApiSchema):
    offer: PulseOffer | None = None
    next_poll_seconds: int = Field(default=30, ge=1, le=30)


class SaveTemplate(ApiSchema):
    name: Name
    description: str = Field(default="", max_length=5000)
    published: bool = False
    archived: bool = False
    steps: list[LearningPathStep] = Field(default_factory=list, max_length=200)
    revision: int = Field(default=0, ge=0)
    pulse_surveys: PulseSurveyConfig = Field(default_factory=PulseSurveyConfig)

    @model_validator(mode="after")
    def valid_graph(self):
        ids = {step.id for step in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("Step IDs must be unique.")
        task_ids = {step.id for step in self.steps if step.type == "task"}
        if not set(self.pulse_surveys.exclude_step_ids) <= task_ids:
            raise ValueError("Pulse exclusions must reference existing task steps.")
        graph = {
            step.id: {c.step_id for c in step.unlock.conditions if c.step_id}
            for step in self.steps
        }
        by_id = {step.id: step for step in self.steps}
        for index, step in enumerate(self.steps):
            if step.unlock.mode == "sequence":
                # Implicit edges: a sequential step waits for every earlier required step.
                graph[step.id] |= {
                    earlier.id
                    for earlier in self.steps[:index]
                    if earlier.type == "task" or earlier.required
                }
        for step in self.steps:
            for condition in step.unlock.conditions:
                source = by_id.get(condition.step_id)
                if source and source.type == "survey":
                    if not source.required:
                        raise ValueError(
                            "Optional questionnaires cannot be prerequisites."
                        )
                    if condition.type == "score":
                        raise ValueError("Questionnaires have no task score.")
        visited, active = set(), set()

        def visit(node):
            if node not in ids:
                raise ValueError("A rule references a missing step.")
            if node in active:
                raise ValueError("Unlock rules must not contain cycles.")
            if node in visited:
                return
            active.add(node)
            for child in graph[node]:
                visit(child)
            active.remove(node)
            visited.add(node)

        for node in ids:
            visit(node)
        if self.published and not self.steps:
            raise ValueError("A published path requires at least one step.")
        return self


class PathTemplate(SaveTemplate):
    id: UUID
    owner_id: str
    created_at: datetime
    updated_at: datetime
    retired_step_ids: list[UUID] = Field(default_factory=list)


class TaskSurveyProgress(ApiSchema):
    survey_id: UUID
    completed: bool = False


class StepRun(LearningPathStep):
    status: Literal["locked", "available", "in_progress", "completed", "skipped"]
    model_id: UUID | None = None
    completed_at: datetime | None = None
    reasons: list[str] = Field(default_factory=list)
    available_at: datetime | None = None


class PathRun(ApiSchema):
    id: UUID
    owner_id: str
    template_id: UUID
    template_revision: int
    created_at: datetime
    first_finished_at: datetime | None = None
    name: str
    description: str
    steps: list[StepRun]
    completed: int
    coins: int = Field(default=0, ge=0)
    total: int
    progress: int
    skipped: int = 0
    finished: bool = False


class StartedStep(ApiSchema):
    model_id: UUID


class PathModelContext(ApiSchema):
    """Read view of the current template, personal state and model binding."""

    id: UUID
    run_id: UUID
    step_id: UUID
    model_id: UUID
    coins: int = Field(default=0, ge=0)
    title: Name
    task_version: TaskVersionReference
    started_at: datetime
    completed_at: datetime | None = None
    challenge: ChallengeAttempt | None = None
    removed: bool = False
    template_revision: int
    completion_requested: bool = False
    before_survey: TaskSurveyProgress | None = None
    after_survey: TaskSurveyProgress | None = None
