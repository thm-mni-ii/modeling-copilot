"""Model sessions and their timestamped browser interactions."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from modeling_api.schemas.common import ApiSchema


class ActivityInteraction(ApiSchema):
    id: UUID
    created_at: AwareDatetime
    type: Literal["tab_hidden", "tab_visible", "focus_lost", "focus_gained", "idle", "active"]


class StoredActivityInteraction(ActivityInteraction):
    session_id: UUID


class ActivitySession(ApiSchema):
    id: UUID
    model_id: UUID
    created_by: str
    created_at: AwareDatetime
    ended_at: AwareDatetime | None = None


class SaveActivitySession(ApiSchema):
    created_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    interactions: list[ActivityInteraction] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_times(self):
        if self.ended_at is not None and self.ended_at < self.created_at:
            raise ValueError("A session cannot end before it starts.")
        for interaction in self.interactions:
            if interaction.created_at < self.created_at:
                raise ValueError("An interaction cannot precede its session.")
            if self.ended_at is not None and interaction.created_at > self.ended_at:
                raise ValueError("An interaction cannot follow the session end.")
        return self
