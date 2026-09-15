"""HTTP-Endpunkte für Modelle und ihre Speicherstände (dünn, Logik in services/)."""

from uuid import UUID

from fastapi import APIRouter, Query, Response

from modeling_api.routes.deps import CurrentUser, Limit, Skip, created_response
from modeling_api.schemas.common import Page
from modeling_api.schemas.models import (
    CreateModel,
    CreateModelVersion,
    Model,
    ModelSortField,
    ModelVersion,
    ModelVersionInfo,
    SortOrder,
    UpdateModel,
)
from modeling_api.services import models as service

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("", summary="Eigene Modelle auflisten")
async def list_models(
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
    q: str | None = Query(default=None, max_length=256),
    archived: bool = False,
    sort: ModelSortField = "updatedAt",
    order: SortOrder = "desc",
) -> Page[Model]:
    return Page[Model].model_validate(
        await service.list_models(skip, limit, user, q, archived, sort, order)
    )


@router.post("", status_code=201, summary="Modell anlegen (Identität, noch ohne Version)")
async def create_model(body: CreateModel, response: Response, user: CurrentUser) -> Model:
    result = await service.create_model(body, user)
    created_response(response, result, "models")
    return Model.model_validate(result)


@router.get("/{model_id}", summary="Ein Modell laden")
async def get_model(model_id: UUID, user: CurrentUser) -> Model:
    return Model.model_validate(await service.get_model(model_id, user))


@router.patch("/{model_id}", summary="Modell umbenennen, archivieren oder reaktivieren")
async def update_model(model_id: UUID, body: UpdateModel, user: CurrentUser) -> Model:
    return Model.model_validate(await service.update_model(model_id, body, user))


@router.delete("/{model_id}", status_code=204, summary="Modell und seine Speicherstände löschen")
async def delete_model(model_id: UUID, user: CurrentUser) -> None:
    await service.delete_model(model_id, user)


@router.get("/{model_id}/versions", summary="Speicherlauf auflisten (ohne data/annotations)")
async def list_versions(
    model_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 20
) -> Page[ModelVersionInfo]:
    return Page[ModelVersionInfo].model_validate(
        await service.list_versions(model_id, skip, limit, user)
    )


@router.post("/{model_id}/versions", status_code=201, summary="Release oder Patch-Checkpoint sichern")
async def create_version(
    model_id: UUID, body: CreateModelVersion, user: CurrentUser
) -> ModelVersion:
    result = await service.create_version(model_id, body, user)
    return ModelVersion.model_validate(result)


@router.get("/{model_id}/versions/{version_id}", summary="Einen Speicherstand laden (mit data)")
async def get_version(model_id: UUID, version_id: UUID, user: CurrentUser) -> ModelVersion:
    return ModelVersion.model_validate(await service.get_version(model_id, version_id, user))
