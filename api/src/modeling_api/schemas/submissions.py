"""Submission configurations, named runs and versioned human reviews."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from modeling_api.schemas.common import (
    ApiSchema,
    JsonObject,
    Name,
    TaskVersionReference,
)


class AssignmentData(ApiSchema):
    name: Name
    description: str = Field(default="", max_length=10000)
    task_version: TaskVersionReference | None = None


class SaveAssignment(AssignmentData):
    base_revision: int = Field(default=0, ge=0)
    archived: bool = False


class RunGrant(ApiSchema):
    user_id: str = Field(min_length=1, max_length=256)
    manage: bool = False
    review: bool = False
    publish: bool = False


class RunData(ApiSchema):
    name: Name
    deadline: AwareDatetime
    state: Literal["open", "closed", "archived"] = "open"
    participation: Literal["all", "selected"] = "all"
    participant_ids: list[str] = Field(default_factory=list, max_length=1000)
    grants: list[RunGrant] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_users(self):
        if len(set(self.participant_ids)) != len(self.participant_ids):
            raise ValueError("Participants must be unique.")
        ids = [grant.user_id for grant in self.grants]
        if len(set(ids)) != len(ids):
            raise ValueError("Grants must be unique per user.")
        return self


class StartRun(RunData):
    assignment_revision: int = Field(ge=1)


class SaveRun(RunData):
    base_revision: int = Field(ge=1)


class SubmitModel(ApiSchema):
    model_id: UUID | None = None
    version_id: UUID | None = None
    package: JsonObject | None = None
    base_submission_id: UUID | None = None
    model_name: Name | None = None

    @model_validator(mode="after")
    def single_source(self):
        if self.package is not None:
            if self.model_id or self.version_id:
                raise ValueError("Choose one submission source.")
        elif not self.model_id or not self.version_id:
            raise ValueError("A saved model version or package is required.")
        return self


class ReviewEntry(ApiSchema):
    id: UUID
    cell_id: str = Field(min_length=1, max_length=256)
    state: Literal["correct", "incorrect", "hint"]
    comment: str = Field(default="", max_length=10000)
    # The server supplies authorship; clients cannot reassign it.
    created_by: str = ""
    updated_by: str = ""
    updated_at: datetime | None = None


class SaveReview(ApiSchema):
    base_revision: int = Field(ge=0)
    entries: list[ReviewEntry] = Field(default_factory=list, max_length=1000)
    score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False, strict=True)
    action: Literal["save", "complete", "reopen"] = "save"


class PublishReview(ApiSchema):
    submission_id: UUID
    review_id: str = Field(min_length=1, max_length=256)
    revision: int = Field(ge=1)


class PublishReviews(ApiSchema):
    reviews: list[PublishReview] = Field(min_length=1, max_length=100)


class SetResolved(ApiSchema):
    entry_id: UUID
    review_id: str = Field(min_length=1, max_length=256)
    publication: int = Field(ge=1)
    resolved: bool


class OverlayImage(ApiSchema):
    src: str = Field(default="", max_length=200000)
    width: int = Field(ge=8, le=96)
    height: int = Field(ge=8, le=96)


class OverlayOffset(ApiSchema):
    x: float = Field(default=0, ge=-200, le=200)
    y: float = Field(default=0, ge=-200, le=200)


class GlobalOverlay(ApiSchema):
    image: OverlayImage
    icon: str | None = Field(
        default=None, max_length=128, pattern=r"^mdi-[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    tooltip: str | None = Field(default=None, max_length=256)
    align: Literal["left", "center", "right"] = "right"
    vertical_align: Literal["top", "middle", "bottom"] = "top"
    offset: OverlayOffset = Field(default_factory=OverlayOffset)
    cursor: Literal[
        "default",
        "pointer",
        "help",
        "move",
        "text",
        "wait",
        "crosshair",
        "not-allowed",
        "grab",
        "grabbing",
    ] = "pointer"

    @model_validator(mode="after")
    def validate_overlay(self):
        if self.icon and not self.color:
            raise ValueError("An MDI overlay requires a hex color.")
        if not self.icon and not self.image.src:
            raise ValueError("An image overlay requires an image source.")
        return self


class GlobalFeedbackData(ApiSchema):
    correct: GlobalOverlay
    incorrect: GlobalOverlay
    hint: GlobalOverlay


class SaveGlobalFeedback(ApiSchema):
    base_revision: int = Field(ge=0)
    overlays: GlobalFeedbackData
