"""Non-blocking learning situations and their immutable start settings."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from modeling_api.schemas.common import ApiSchema, Name


class ChallengeConfig(ApiSchema):
    type: Literal["solo", "time", "help_budget"]
    title: Name
    description: str = Field(min_length=1, max_length=3000, pattern=r"\S")
    icon: str = Field(pattern=r"^mdi-[a-z0-9-]{1,80}$")
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    duration_seconds: int | None = Field(default=None, strict=True, ge=1, le=86400)
    help_budget: int | None = Field(default=None, strict=True, ge=0, le=1000)

    @model_validator(mode="after")
    def valid_parameters(self):
        if (self.type == "time") != (self.duration_seconds is not None):
            raise ValueError("Only time challenges require durationSeconds.")
        if (self.type == "help_budget") != (self.help_budget is not None):
            raise ValueError("Only help-budget challenges require helpBudget.")
        return self


class ChallengeAttempt(ApiSchema):
    config: ChallengeConfig
    started_at: datetime
    ends_at: datetime | None = None
    stopped_at: datetime | None = None


class StartStep(ApiSchema):
    acknowledged_challenge: ChallengeConfig | None = None
