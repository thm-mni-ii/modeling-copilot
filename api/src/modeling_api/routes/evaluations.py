"""Authenticated evaluation endpoints."""

from uuid import UUID

from fastapi import APIRouter

from modeling_api.routes.deps import CurrentUser, Limit, Skip
from modeling_api.schemas.common import Page
from modeling_api.schemas.evaluations import Evaluation, EvaluationDetail, EvaluationWorkflow, StartEvaluation
from modeling_api.services import evaluations as service

router = APIRouter(tags=["Evaluations"])


@router.get("/evaluation-workflows", response_model=list[EvaluationWorkflow])
async def list_workflows(user: CurrentUser) -> list[EvaluationWorkflow]:
    if not user.is_admin:
        from modeling_api.core.errors import ApiError
        raise ApiError(403, "FORBIDDEN", "Workflow configuration requires administrator access.")
    return [EvaluationWorkflow.model_validate(item) for item in await service.list_workflows()]


@router.post("/models/{model_id}/evaluations", status_code=201, response_model=Evaluation)
async def start_evaluation(model_id: UUID, body: StartEvaluation, user: CurrentUser) -> Evaluation:
    return Evaluation.model_validate(await service.start(model_id, user))


@router.get("/models/{model_id}/evaluations", response_model=Page[Evaluation])
async def list_evaluations(model_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 20) -> Page[Evaluation]:
    return Page[Evaluation].model_validate(await service.list_for_model(model_id, user, skip, limit))


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationDetail)
async def get_evaluation(evaluation_id: UUID, user: CurrentUser) -> EvaluationDetail:
    return EvaluationDetail.model_validate(await service.detail(evaluation_id, user))
