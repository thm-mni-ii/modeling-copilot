"""Schemas for feedback attached to one immutable model version."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from modeling_api.schemas.common import ApiSchema, JsonObject, Name


class FeedbackInfo(ApiSchema):
    """Feedback metadata without the potentially large payload."""

    id: UUID = Field(description="Stable feedback identifier.")
    model_id: UUID = Field(description="Owning model identifier.")
    model_version_id: UUID = Field(description="Immutable model-version identifier.")
    source: Name = Field(description="Feedback producer or integration name.")
    external_feedback_id: Name = Field(
        description="Producer-defined result identifier used for idempotency."
    )
    created_at: datetime = Field(description="UTC creation timestamp.")
    created_by: str = Field(description="Identifier of the submitting user.")


class Feedback(FeedbackInfo):
    """Complete feedback record."""

    data: JsonObject = Field(description="Complete free-form feedback payload.")


class CreateFeedback(ApiSchema):
    """Request to store feedback for one model version."""

    source: Name = Field(description="Feedback producer or integration name.")
    external_feedback_id: Name = Field(
        description="Producer-defined result identifier used for idempotency."
    )
    data: JsonObject = Field(description="Complete free-form feedback payload.")
