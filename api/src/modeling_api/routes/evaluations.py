"""Authenticated evaluation endpoints."""

from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from modeling_api.core.errors import ApiError
from modeling_api.routes.deps import CurrentUser, Limit, Skip
from modeling_api.schemas.common import Page
from modeling_api.schemas.evaluations import Evaluation, EvaluationDetail, EvaluationFeedback, EvaluationWorkflow, StartEvaluation
from modeling_api.services import evaluations as service
from modeling_api.services import evaluation_export

router = APIRouter(tags=["Evaluations"])


@router.get("/evaluation-workflows", response_model=list[EvaluationWorkflow])
async def list_workflows(user: CurrentUser) -> list[EvaluationWorkflow]:
    if not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "Workflow configuration requires administrator access.")
    return [EvaluationWorkflow.model_validate(item) for item in await service.list_workflows()]


@router.post("/models/{model_id}/evaluations", status_code=201, response_model=Evaluation)
async def start_evaluation(model_id: UUID, body: StartEvaluation, user: CurrentUser) -> Evaluation:
    result = await service.start(
        model_id, user, text_evidence=body.text_evidence.model_dump(by_alias=True) if body.text_evidence else None)
    return Evaluation.model_validate(result if service.can_view_analysis(user) else service.student_evaluation(result))


@router.get("/models/{model_id}/evaluations", response_model=Page[Evaluation])
async def list_evaluations(model_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 20) -> Page[Evaluation]:
    return Page[Evaluation].model_validate(await service.list_for_model(model_id, user, skip, limit))


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationDetail,
            summary="Full evaluation run (moderators and administrators only)")
async def get_evaluation(evaluation_id: UUID, user: CurrentUser) -> EvaluationDetail:
    if not service.can_view_analysis(user):
        raise ApiError(403, "FORBIDDEN", "Evaluation details require moderator or administrator access.")
    return EvaluationDetail.model_validate(await service.detail(evaluation_id, user))


@router.get("/evaluations/{evaluation_id}/feedback", response_model=EvaluationFeedback,
            summary="Learner feedback of an evaluation",
            description="State while running; after a successful run the score and recognition overview only.")
async def get_feedback(evaluation_id: UUID, user: CurrentUser) -> EvaluationFeedback:
    return EvaluationFeedback.model_validate(await service.feedback(evaluation_id, user))


@router.get("/evaluations/{evaluation_id}/archive.zip", response_class=StreamingResponse)
async def download_evaluation(evaluation_id: UUID, user: CurrentUser) -> StreamingResponse:
    archive = await evaluation_export.create_archive(evaluation_id, user)

    def chunks():
        try:
            while content := archive.read(1024 * 1024):
                yield content
        finally:
            archive.close()

    return StreamingResponse(chunks(), media_type="application/zip", background=BackgroundTask(archive.close),
                             headers={"Content-Disposition": f'attachment; filename="evaluation-{evaluation_id}.zip"'})
