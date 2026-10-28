"""Stored path documents, separate from the flattened API views."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from modeling_api.schemas.common import ApiSchema, Name
from modeling_api.schemas.challenges import ChallengeConfig
from modeling_api.schemas.learning_paths import UnlockRule, PulseSurveyConfig, HelpRequestConfig


class SurveyReference(ApiSchema):
    survey_id: str


class StationSurveySettings(SurveyReference):
    required: bool = True


class TaskSettings(ApiSchema):
    task_id: str
    release_id: str
    before_survey_id: str | None = None
    after_survey_id: str | None = None
    challenge: ChallengeConfig | None = None


class TaskStepDefinition(ApiSchema):
    template_id: str
    kind: Literal["task"]
    title: Name
    unlock: UnlockRule
    task: TaskSettings


class SurveyStepDefinition(ApiSchema):
    template_id: str
    kind: Literal["survey"]
    title: Name
    unlock: UnlockRule
    survey: StationSurveySettings


StepDefinition = Annotated[
    TaskStepDefinition | SurveyStepDefinition, Field(discriminator="kind")
]


class LearningPathTemplateContent(ApiSchema):
    title: Name
    description: str
    status: Literal["draft", "published", "archived"]
    step_ids: list[str]
    pulse_surveys: PulseSurveyConfig = Field(default_factory=PulseSurveyConfig)
    help_requests: HelpRequestConfig = Field(default_factory=HelpRequestConfig)


class LearningPathStepState(ApiSchema):
    """Personal progress on one template step; the _id derives from run and step."""

    run_id: str
    step_id: str
    opened_at: datetime
    completed_at: datetime | None = None
    model_id: str | None = None
    work_submitted_at: datetime | None = None
    challenge_started_at: datetime | None = None
    challenge_stopped_at: datetime | None = None
    survey_session_id: str | None = None
    before_survey: str | None = None
    after_survey: str | None = None
    active_seconds: int = Field(default=0, ge=0)
    pulse_last_poll_at: datetime | None = None


class LearningPathRunFields(ApiSchema):
    learner_id: str
    template_id: str
    created_at: datetime
    first_finished_at: datetime | None = None
