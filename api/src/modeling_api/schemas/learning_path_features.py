from datetime import datetime
from typing import Literal

from pydantic import Field

from modeling_api.schemas.common import ApiSchema


TourItem = Literal["feedback-types", "help-request", "mark-object", "automatic-feedback", "help-feedback-walkthrough"]
TourEvent = Literal["opened", "started", "completed", "skipped"]


class FeatureTourEvent(ApiSchema):
    item_id: TourItem | None = None
    event: TourEvent


class FeatureTourProgress(ApiSchema):
    completed_items: list[TourItem] = Field(default_factory=list)
    skipped_items: list[TourItem] = Field(default_factory=list)
    first_opened_at: datetime | None = None


class FeatureTourParticipant(ApiSchema):
    user_id: str
    user_name: str
    opened_count: int
    tour_starts: int
    first_opened_at: datetime | None = None
    completed_items: list[TourItem] = Field(default_factory=list)
    skipped_items: list[TourItem] = Field(default_factory=list)
    last_event_at: datetime


class FeatureTourReport(ApiSchema):
    opened_users: int
    opened_events: int
    tour_starts: int
    participants: list[FeatureTourParticipant]
