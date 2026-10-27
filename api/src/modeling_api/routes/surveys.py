"""Authenticated renderer endpoints and administrator-only management."""

from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Response
from modeling_api.routes.deps import CurrentUser, Skip, Limit
from modeling_api.schemas.common import Page
from modeling_api.schemas.surveys import (
    SaveSurvey,
    Survey,
    SubmitResponse,
    SurveyResponse,
    SurveyVersion,
    SurveyVersionInfo,
    ActivateRelease,
)
from modeling_api.services import surveys as service

router = APIRouter(prefix="/surveys", tags=["Surveys"])


@router.get("", response_model=Page[Survey])
async def list_surveys(user: CurrentUser, skip: Skip = 0, limit: Limit = 100):
    return await service.list_surveys(user, skip, limit)


@router.post("", response_model=Survey, status_code=201)
async def create(body: SaveSurvey, user: CurrentUser):
    return await service.save_survey(body, user)


@router.get("/{survey_id}", response_model=Survey)
async def get(survey_id: UUID, user: CurrentUser):
    return await service.get_survey(survey_id, user)


@router.get("/{survey_id}/render", response_model=SurveyVersion)
async def render(
    survey_id: UUID,
    user: CurrentUser,
    mode: Literal["use", "preview", "test"] = "use",
    versionId: UUID | None = None,
):
    return await service.render(survey_id, user, mode, versionId)


@router.get("/{survey_id}/versions", response_model=Page[SurveyVersionInfo])
async def versions(
    survey_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 100
):
    return await service.list_versions(survey_id, user, skip, limit)


@router.get("/{survey_id}/versions/{version_id}", response_model=SurveyVersion)
async def version(survey_id: UUID, version_id: UUID, user: CurrentUser):
    return await service.get_version(survey_id, version_id, user)


@router.post("/{survey_id}/release", response_model=Survey)
async def release(survey_id: UUID, body: ActivateRelease, user: CurrentUser):
    return await service.activate(survey_id, body, user)


@router.get("/{survey_id}/responses", response_model=Page[SurveyResponse])
async def responses(
    survey_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 100
):
    return await service.responses(survey_id, user, skip, limit)


@router.put("/{survey_id}", response_model=Survey)
async def update(survey_id: UUID, body: SaveSurvey, user: CurrentUser):
    return await service.save_survey(body, user, survey_id)


@router.delete("/{survey_id}", status_code=204)
async def delete(survey_id: UUID, user: CurrentUser):
    await service.delete_survey(survey_id, user)
    return Response(status_code=204)


@router.post("/{survey_id}/responses", response_model=SurveyResponse)
async def submit(survey_id: UUID, body: SubmitResponse, user: CurrentUser):
    return await service.submit(survey_id, body, user)
