"""HTTP-Endpunkte für den globalen Aufgabenkatalog."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from modeling_api.routes.deps import CurrentUser, Limit, Skip, created_response
from modeling_api.schemas.common import Page
from modeling_api.schemas.tasks import (
    CreateTask,
    CreateTaskVersion,
    Task,
    TaskVisibility,
    TaskVersion,
    TaskVersionInfo,
    UpdateTask,
)
from modeling_api.schemas.models import ModelVersion
from modeling_api.services import tasks as service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", summary="Globalen Aufgabenkatalog auflisten")
async def list_tasks(
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
    q: Annotated[str | None, Query(max_length=256)] = None,
    archived: bool = False,
    mine: bool = False,
    visibility: TaskVisibility | None = None,
) -> Page[Task]:
    return Page[Task].model_validate(await service.list_tasks(skip, limit, user, q, archived, mine, visibility))


@router.post(
    "",
    status_code=201,
    summary="Aufgabe anlegen oder von einer Fassung branchen",
)
async def create_task(body: CreateTask, response: Response, user: CurrentUser) -> Task:
    result = await service.create_task(body, user)
    created_response(response, result, "tasks")
    return Task.model_validate(result)


@router.get("/{task_id}", summary="Eine Aufgabe laden")
async def get_task(task_id: UUID, user: CurrentUser) -> Task:
    return Task.model_validate(await service.get_task(task_id, user))


@router.patch("/{task_id}", summary="Aufgabe umbenennen, archivieren oder reaktivieren")
async def update_task(task_id: UUID, body: UpdateTask, user: CurrentUser) -> Task:
    return Task.model_validate(await service.update_task(task_id, body, user))


@router.get("/{task_id}/versions", summary="Fassungen auflisten (ohne data)")
async def list_versions(
    task_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 20
) -> Page[TaskVersionInfo]:
    return Page[TaskVersionInfo].model_validate(
        await service.list_versions(task_id, skip, limit, user)
    )


@router.post(
    "/{task_id}/versions",
    status_code=201,
    summary="Checkpoint oder Release speichern",
)
async def create_version(
    task_id: UUID, body: CreateTaskVersion, user: CurrentUser
) -> TaskVersion:
    return TaskVersion.model_validate(await service.create_version(task_id, body, user))


@router.get("/{task_id}/versions/{version_id}", summary="Eine Fassung laden (mit data)")
async def get_version(task_id: UUID, version_id: UUID, user: CurrentUser) -> TaskVersion:
    return TaskVersion.model_validate(await service.get_version(task_id, version_id, user))


@router.get(
    "/{task_id}/versions/{version_id}/sample-solutions/{model_id}/{model_version_id}",
    summary="Freigegebene Musterlösung laden",
)
async def get_sample_solution(
    task_id: UUID,
    version_id: UUID,
    model_id: UUID,
    model_version_id: UUID,
    user: CurrentUser,
) -> ModelVersion:
    return ModelVersion.model_validate(
        await service.get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    )
