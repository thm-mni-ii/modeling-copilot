"""Authenticated endpoints for learning-path templates and personal runs."""

from uuid import UUID
from typing import Literal
from fastapi import APIRouter
from modeling_api.routes.deps import CurrentUser, Skip, Limit
from modeling_api.schemas.learning_paths import (
    SaveTemplate,
    PathTemplate,
    PathRun,
    StartedStep,
    PathModelContext,
)
from modeling_api.schemas.common import Page
from modeling_api.schemas.survey_sessions import SurveySessionInput, SurveySessionView
from modeling_api.schemas.challenges import StartStep
from modeling_api.services import learning_paths as service

router = APIRouter(tags=["Learning paths"])


@router.get(
    "/learning-path-runs/by-model/{model_id}/context",
    response_model=PathModelContext | None,
)
async def model_context(model_id: UUID, user: CurrentUser):
    return await service.get_model_context(model_id, user)


@router.post(
    "/learning-path-runs/{run_id}/steps/{step_id}/challenge/stop",
    response_model=PathModelContext,
)
async def stop_challenge(run_id: UUID, step_id: UUID, user: CurrentUser):
    return await service.stop_time_challenge(run_id, step_id, user)


@router.get("/learning-path-templates", response_model=Page[PathTemplate])
async def templates(user: CurrentUser, skip: Skip = 0, limit: Limit = 100):
    return await service.list_templates(user, skip, limit)


@router.post("/learning-path-templates", status_code=201, response_model=PathTemplate)
async def create(body: SaveTemplate, user: CurrentUser):
    return await service.save_template(body, user)


@router.get("/learning-path-templates/{template_id}", response_model=PathTemplate)
async def template(template_id: UUID, user: CurrentUser):
    return await service.get_template(template_id, user)


@router.put("/learning-path-templates/{template_id}", response_model=PathTemplate)
async def save(template_id: UUID, body: SaveTemplate, user: CurrentUser):
    return await service.save_template(body, user, template_id)


@router.post("/learning-path-templates/{template_id}/runs", response_model=PathRun)
async def start(template_id: UUID, user: CurrentUser):
    return await service.start_run(template_id, user)


@router.get("/learning-path-runs", response_model=Page[PathRun])
async def runs(user: CurrentUser, skip: Skip = 0, limit: Limit = 100):
    return await service.list_runs(user, skip, limit)


@router.get("/learning-path-runs/{run_id}", response_model=PathRun)
async def run(run_id: UUID, user: CurrentUser):
    return await service.get_run(run_id, user)


@router.post(
    "/learning-path-runs/{run_id}/steps/{step_id}/start", response_model=StartedStep
)
async def start_step(
    run_id: UUID, step_id: UUID, user: CurrentUser, body: StartStep | None = None
):
    return await service.start_step(run_id, step_id, user, body)


@router.post(
    "/learning-path-runs/{run_id}/steps/{step_id}/resume",
    response_model=PathModelContext,
)
async def resume_step(run_id: UUID, step_id: UUID, user: CurrentUser):
    return await service.resume_step(run_id, step_id, user)


@router.post(
    "/learning-path-runs/{run_id}/steps/{step_id}/complete", response_model=PathRun
)
async def complete_step(run_id: UUID, step_id: UUID, user: CurrentUser):
    return await service.complete_step(run_id, step_id, user)


@router.post(
    "/learning-path-runs/{run_id}/steps/{step_id}/survey/open",
    response_model=SurveySessionView,
)
async def open_survey(
    run_id: UUID,
    step_id: UUID,
    user: CurrentUser,
    phase: Literal["before", "after"] | None = None,
):
    return await service.open_survey(run_id, step_id, user, phase)


@router.put("/learning-path-runs/{run_id}/steps/{step_id}/survey/draft")
async def draft_survey(
    run_id: UUID,
    step_id: UUID,
    body: SurveySessionInput,
    user: CurrentUser,
    phase: Literal["before", "after"] | None = None,
):
    return await service.save_survey_session(
        run_id, step_id, body, user, "draft", phase
    )


@router.post("/learning-path-runs/{run_id}/steps/{step_id}/survey/submit")
async def submit_survey(
    run_id: UUID,
    step_id: UUID,
    body: SurveySessionInput,
    user: CurrentUser,
    phase: Literal["before", "after"] | None = None,
):
    return await service.save_survey_session(
        run_id, step_id, body, user, "submit", phase
    )


@router.post("/learning-path-runs/{run_id}/steps/{step_id}/survey/skip")
async def skip_survey(
    run_id: UUID,
    step_id: UUID,
    body: SurveySessionInput,
    user: CurrentUser,
    phase: Literal["before", "after"] | None = None,
):
    return await service.save_survey_session(run_id, step_id, body, user, "skip", phase)
