from typing import Literal

from modeling_api.schemas.common import ApiSchema


TourEventName = Literal["opened", "started", "step", "completed", "skipped"]


class TourEvent(ApiSchema):
    event: TourEventName
    step_id: str | None = None


class TourProgress(ApiSchema):
    completed: bool
    skipped: bool
