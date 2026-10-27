"""The editor's supported subset uses SurveyJS property names directly."""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from modeling_api.schemas.common import ApiSchema, JsonObject, Name


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["comment", "radiogroup", "checkbox", "rating", "matrix"]
    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")
    title: Name
    isRequired: bool = False
    choices: list[Name] | None = Field(default=None, max_length=100)
    rows: list[Name] | None = Field(default=None, max_length=100)
    columns: list[Name] | None = Field(default=None, max_length=100)
    isAllRowRequired: bool = False
    rateMin: int = Field(default=1, ge=0, le=100)
    rateMax: int = Field(default=5, ge=1, le=100)

    @model_validator(mode="after")
    def valid_question(self):
        for values in (self.choices, self.rows, self.columns):
            if values is not None and (not values or len(set(values)) != len(values)):
                raise ValueError("Options must be non-empty and unique.")
        if self.type in ("radiogroup", "checkbox") and not self.choices:
            raise ValueError("Choices are required.")
        if self.type == "matrix" and (not self.rows or not self.columns):
            raise ValueError("Likert rows and columns are required.")
        if self.rateMin >= self.rateMax:
            raise ValueError("The rating maximum must exceed its minimum.")
        return self


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    elements: list[Question] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_names(self):
        if len({q.name for q in self.elements}) != len(self.elements):
            raise ValueError("Question names must be unique.")
        return self


class SaveSurvey(ApiSchema):
    title: Name
    definition: Definition
    base_version_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("definition")
    @classmethod
    def bounded_definition(cls, value):
        if len(json.dumps(value.model_dump(exclude_none=True)).encode()) > 1_000_000:
            raise ValueError("Survey definition must not exceed 1 MB.")
        return value


class Survey(ApiSchema):
    id: UUID
    title: str
    definition: Definition
    version: int
    latest_version_id: UUID
    latest_kind: Literal["checkpoint", "release"]
    active_release_id: UUID | None
    active_release_version: int | None
    revision: int
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None


class SurveyVersionInfo(ApiSchema):
    id: UUID
    survey_id: UUID
    version: int
    title: str
    kind: Literal["checkpoint", "release"]
    created_at: datetime
    created_by: str | None
    released_at: datetime | None = None
    released_by: str | None = None


class SurveyVersion(SurveyVersionInfo):
    definition: Definition


class ActivateRelease(ApiSchema):
    version_id: UUID
    expected_revision: int = Field(ge=1)


class SubmitResponse(ApiSchema):
    version_id: UUID
    answers: JsonObject
    mode: Literal["use", "preview", "test"] = "use"

    @field_validator("answers")
    @classmethod
    def bounded_payload(cls, value):
        if len(json.dumps(value, allow_nan=False).encode()) > 100_000:
            raise ValueError("Response payload is too large.")
        return value


class SurveyResponse(ApiSchema):
    id: UUID
    survey_id: UUID
    version: int
    version_id: UUID
    user_id: str
    answers: JsonObject
    is_test: bool
    created_at: datetime
