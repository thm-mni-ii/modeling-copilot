"""The editor's supported subset uses SurveyJS property names directly."""

import json
import re
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
    description: str | None = Field(default=None, max_length=2000)
    page: str | None = Field(default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")
    isRequired: bool = False
    visibleIf: str | None = Field(default=None, max_length=400)
    visibleWhen: Literal["help_requested", "pulse_answered"] | None = None
    choices: list[Name] | None = Field(default=None, max_length=100)
    exclusiveChoices: list[Name] | None = Field(default=None, max_length=100)
    choiceLabels: dict[str, Name] | None = None
    rows: list[Name] | None = Field(default=None, max_length=100)
    columns: list[Name] | None = Field(default=None, max_length=100)
    isAllRowRequired: bool = False
    rateMin: int = Field(default=1, ge=0, le=100)
    rateMax: int = Field(default=5, ge=1, le=100)
    minRateDescription: Name | None = None
    maxRateDescription: Name | None = None

    @model_validator(mode="after")
    def valid_question(self):
        if self.exclusiveChoices is not None and (
            self.type != "checkbox"
            or not self.choices
            or not set(self.exclusiveChoices) <= set(self.choices)
            or len(set(self.exclusiveChoices)) != len(self.exclusiveChoices)
        ):
            raise ValueError("Exclusive choices must be unique checkbox answer options.")
        if self.choiceLabels is not None and (not self.choices or set(self.choiceLabels) != set(self.choices)):
            raise ValueError("Choice labels must match the answer identifiers.")
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


class SurveyPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")
    title: Name
    description: str | None = Field(default=None, max_length=2000)


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    elements: list[Question] = Field(min_length=1, max_length=100)
    introduction: str | None = Field(default=None, max_length=5000)
    pages: list[SurveyPage] = Field(default_factory=list, max_length=20)
    showQuestionNumbers: Literal["on", "off"] = "on"

    @model_validator(mode="after")
    def unique_names(self):
        if all(question.visibleWhen or question.visibleIf for question in self.elements):
            raise ValueError("A questionnaire requires at least one unconditional question.")
        page_names = {page.name for page in self.pages}
        if len(page_names) != len(self.pages):
            raise ValueError("Page names must be unique.")
        if any(
            (question.page not in page_names if self.pages else question.page is not None)
            for question in self.elements
        ):
            raise ValueError("Each question must belong to an existing page when pages are configured.")
        if len({q.name for q in self.elements}) != len(self.elements):
            raise ValueError("Question names must be unique.")
        earlier = {}
        for question in self.elements:
            if question.visibleIf:
                name, choice = visibility_condition(question.visibleIf)
                source = earlier.get(name)
                if not source or source.type not in ("radiogroup", "checkbox") or choice not in source.choices:
                    raise ValueError("Visibility must reference an earlier choice question and one of its options.")
                if (source.type == "checkbox") != question.visibleIf.partition("} ")[2].startswith("contains "):
                    raise ValueError("Checkbox conditions require contains; single-choice conditions require = or !=.")
            earlier[question.name] = question
        return self


def visibility_condition(expression):
    match = re.fullmatch(r"\{([a-zA-Z][a-zA-Z0-9_-]{0,79})\} (?:=|!=|contains) '([^']+)'", expression)
    if not match:
        raise ValueError("Unsupported question visibility condition.")
    return match.groups()


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
    managed_by: str | None = None
    template_id: UUID | None = None


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
