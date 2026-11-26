"""Authenticated endpoints for a learner's guided-tour progress and events."""

from fastapi import APIRouter

from modeling_api.routes.deps import CurrentUser
from modeling_api.schemas.tours import TourEvent, TourProgress
from modeling_api.services import tours

router = APIRouter(prefix="/tours", tags=["Tours"])


@router.get("/{tour_id}/progress", response_model=TourProgress)
async def tour_progress(tour_id: str, user: CurrentUser):
    return await tours.get_progress(user, tours.get_tour(tour_id))


@router.post("/{tour_id}/events", response_model=TourProgress)
async def tour_event(tour_id: str, body: TourEvent, user: CurrentUser):
    return await tours.record_event(user, tours.get_tour(tour_id), body)
