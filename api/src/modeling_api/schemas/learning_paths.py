"""Mutable learning-path configuration and personal runs."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from modeling_api.schemas.common import ApiSchema, Name, TaskVersionReference
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
    mode: Literal["all", "any"] = "all"
    conditions: list[UnlockCondition] = Field(default_factory=list, max_length=50)


class LearningPathStep(ApiSchema):
    id: UUID
    title: Name
    task_version: TaskVersionReference
    unlock: UnlockRule = Field(default_factory=UnlockRule)
    challenge: ChallengeConfig | None = None


class SaveTemplate(ApiSchema):
    name: Name
    description: str = Field(default="", max_length=5000)
    published: bool = False
    archived: bool = False
    steps: list[LearningPathStep] = Field(default_factory=list, max_length=200)
    # A timestamp guards concurrent edits; there are no immutable path versions.
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def valid_graph(self):
        ids = {step.id for step in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("Step IDs must be unique.")
        graph = {
            step.id: {c.step_id for c in step.unlock.conditions if c.step_id}
            for step in self.steps
        }
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
    retired_step_ids: list[UUID] = Field(default_factory=list)


class StepRun(LearningPathStep):
    status: Literal["locked", "available", "in_progress", "completed"]
    model_id: UUID | None = None
    completed_at: datetime | None = None
    reasons: list[str] = Field(default_factory=list)
    available_at: datetime | None = None


class PathRun(ApiSchema):
    id: UUID
    owner_id: str
    template_id: UUID
    created_at: datetime
    name: str
    description: str
    steps: list[StepRun]
    completed: int
    total: int
    progress: int


class StartedStep(ApiSchema):
    model_id: UUID


class StepRunContext(ApiSchema):
    """The editor context is owned by the step run, never by the model."""

    id: UUID
    run_id: UUID
    step_id: UUID
    model_id: UUID
    title: Name
    task_version: TaskVersionReference
    started_at: datetime
    completed_at: datetime | None = None
    unlocked_at: datetime | None = None
    challenge: ChallengeAttempt | None = None
