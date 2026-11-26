"""Tour registry and per-learner tour progress/events."""

from dataclasses import dataclass

from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import utcnow


@dataclass(frozen=True)
class Tour:
    id: str
    title: str
    # Bump when changed tour content should appear as new for every learner.
    version: int
    steps: tuple[tuple[str, str], ...]  # ordered (step id, English title)


# Step order and ids must match the steps in web/src/tours/learningPath.ts.
TOURS = {
    tour.id: tour
    for tour in (
        Tour("help-feedback", "Automatic feedback tour", 1, (
            ("intro", "Introduction to the help functions"),
            ("check", "Check"),
            ("clarify", "Explanation"),
            ("next-step", "Next step"),
            ("example", "Example"),
            ("solution", "Solution"),
            ("request-help", "Request help"),
            ("describe-problem", "Describe the problem"),
            ("load-questionnaire", "Load the questionnaire"),
            ("estimate-duration", "Estimate how long you are stuck"),
            ("choose-support", "Choose support"),
            ("confirm-support", "Confirm the choice"),
            ("mark-problem", "Mark the problem area"),
            ("choose-action", "Choose automatic check"),
            ("start-check", "Start the check"),
            ("choose-source", "Choose the help source"),
        )),
    )
}


def get_tour(tour_id):
    tour = TOURS.get(tour_id)
    if not tour:
        raise not_found()
    return tour


async def get_progress(user, tour):
    filters = {"userId": user.id, "tourId": tour.id, "tourVersion": tour.version}
    completed = await db.tour_events.find_one({**filters, "event": "completed"}, {"_id": 1})
    skipped = await db.tour_events.find_one({**filters, "event": "skipped"}, {"_id": 1})
    return {"completed": completed is not None, "skipped": skipped is not None and completed is None}


async def record_event(user, tour, body):
    step_ids = {step_id for step_id, _ in tour.steps}
    if body.step_id is not None and body.step_id not in step_ids:
        raise ApiError(422, "INVALID_TOUR_EVENT", "Unknown tour step.")
    if body.event == "step" and body.step_id is None:
        raise ApiError(422, "INVALID_TOUR_EVENT", "A step event requires a step.")
    if body.event in ("opened", "started", "completed") and body.step_id is not None:
        raise ApiError(422, "INVALID_TOUR_EVENT", "This tour event cannot reference a step.")
    await db.tour_events.insert_one({
        "userId": user.id,
        "tourId": tour.id,
        "tourVersion": tour.version,
        "event": body.event,
        "stepId": body.step_id,
        "at": utcnow(),
    })
    return await get_progress(user, tour)
