"""HTTP endpoints for feedback attached to immutable model versions."""

from uuid import UUID

from fastapi import APIRouter, Response

from modeling_api.routes.deps import CurrentUser, Limit, Skip, created_response
from modeling_api.schemas.common import Page
from modeling_api.schemas.feedback import CreateFeedback, Feedback, FeedbackInfo
from modeling_api.services import feedback as service

router = APIRouter(
    prefix="/models/{model_id}/versions/{version_id}/feedback", tags=["Feedback"]
)


@router.get(
    "",
    summary="List version feedback",
    description=(
        "Returns feedback metadata for one model version owned by the authenticated user. "
        "The potentially large feedback payload is omitted."
    ),
    response_description="A paginated list of feedback metadata.",
)
async def list_feedback(
    model_id: UUID,
    version_id: UUID,
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
) -> Page[FeedbackInfo]:
    return Page[FeedbackInfo].model_validate(
        await service.list_feedback(model_id, version_id, skip, limit, user)
    )


@router.post(
    "",
    status_code=201,
    responses={200: {"model": Feedback, "description": "Existing idempotent result."}},
    summary="Store version feedback",
    description=(
        "Stores feedback for an immutable model version. Repeating the same source and external "
        "feedback ID is idempotent when the payload is unchanged."
    ),
    response_description="The newly stored feedback.",
)
async def create_feedback(
    model_id: UUID,
    version_id: UUID,
    body: CreateFeedback,
    response: Response,
    user: CurrentUser,
) -> Feedback:
    result, created = await service.create_feedback(model_id, version_id, body, user)
    created_response(
        response, result, f"models/{model_id}/versions/{version_id}/feedback", created
    )
    return Feedback.model_validate(result)


@router.get(
    "/{feedback_id}",
    summary="Get version feedback",
    description="Returns one feedback record including its complete payload.",
    response_description="The requested feedback record.",
)
async def get_feedback(
    model_id: UUID, version_id: UUID, feedback_id: UUID, user: CurrentUser
) -> Feedback:
    return Feedback.model_validate(
        await service.get_feedback(model_id, version_id, feedback_id, user)
    )
