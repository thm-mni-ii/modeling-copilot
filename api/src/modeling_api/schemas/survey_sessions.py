"""Survey sessions: one release, one answer set and an explicit lifecycle."""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from modeling_api.schemas.common import ApiSchema, JsonObject
from modeling_api.schemas.surveys import SurveyVersion


class SurveySessionInput(ApiSchema):
    session_id: UUID
    answers: JsonObject = Field(default_factory=dict)
    revision: int = Field(default=0, ge=0)

    @field_validator("answers")
    @classmethod
    def bounded_answers(cls, value):
        if len(json.dumps(value, allow_nan=False).encode()) > 100_000:
            raise ValueError("Response payload is too large.")
        return value


class SurveySessionView(ApiSchema):
    session_id: UUID
    version: SurveyVersion
    answers: JsonObject
    revision: int
    release_changed: bool
    status: Literal["draft", "submitted", "skipped"]


class SurveySessionFields(ApiSchema):
    user_id: str
    release_id: str
    status: Literal["draft", "submitted", "skipped"]
    revision: int = 0
    answers: JsonObject = Field(default_factory=dict)
    is_test: bool = False
    context_flags: dict[Literal["help_requested", "pulse_answered"], bool] = Field(default_factory=dict)
    created_at: datetime
    completed_at: datetime | None = None
