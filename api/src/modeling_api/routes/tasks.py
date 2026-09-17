"""HTTP endpoints for the shared task catalog."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from modeling_api.routes.deps import CurrentUser, Limit, Skip, created_response
from modeling_api.schemas.common import Page
from modeling_api.schemas.models import ModelVersion
from modeling_api.schemas.tasks import (
    CreateTask,
    CreateTaskVersion,
    Task,
    TaskVersion,
    TaskVersionInfo,
    TaskVisibility,
    UpdateTask,
)
from modeling_api.services import tasks as service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get(
    "",
    summary="List tasks",
    description=(
        "Lists the shared task catalog. Non-administrators only receive active, published tasks; "
        "administrators may filter by ownership, archive state, and visibility."
    ),
    response_description="A paginated list of task identities.",
)
async def list_tasks(
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
    q: Annotated[
        str | None,
        Query(max_length=256, description="Case-insensitive task-name search."),
    ] = None,
    archived: bool = Query(default=False, description="Return archived tasks instead of active tasks."),
    mine: bool = Query(default=False, description="Return only tasks owned by the authenticated user."),
    visibility: TaskVisibility | None = Query(
        default=None,
        description="Administrator-only visibility filter.",
    ),
) -> Page[Task]:
    return Page[Task].model_validate(
        await service.list_tasks(skip, limit, user, q, archived, mine, visibility)
    )


@router.post(
    "",
    status_code=201,
    summary="Create or branch a task",
    description=(
        "Creates an empty task, or copies an existing task version into the new task as its first "
        "checkpoint. Administrator access is required."
    ),
    response_description="The created task identity.",
)
async def create_task(body: CreateTask, response: Response, user: CurrentUser) -> Task:
    result = await service.create_task(body, user)
    created_response(response, result, "tasks")
    return Task.model_validate(result)


@router.get(
    "/{task_id}",
    summary="Get a task",
    description="Returns private tasks to administrators and published tasks to authenticated users.",
    response_description="The requested task identity and publication metadata.",
)
async def get_task(task_id: UUID, user: CurrentUser) -> Task:
    return Task.model_validate(await service.get_task(task_id, user))


@router.patch(
    "/{task_id}",
    summary="Update task metadata",
    description="Renames, archives, restores, publishes, or privatizes a task. Administrator access is required.",
    response_description="The updated task.",
)
async def update_task(task_id: UUID, body: UpdateTask, user: CurrentUser) -> Task:
    return Task.model_validate(await service.update_task(task_id, body, user))


@router.get(
    "/{task_id}/versions",
    summary="List task versions",
    description="Administrators receive checkpoints and releases; other users receive releases only.",
    response_description="A paginated list of task-version metadata without task data.",
)
async def list_versions(
    task_id: UUID,
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
) -> Page[TaskVersionInfo]:
    return Page[TaskVersionInfo].model_validate(
        await service.list_versions(task_id, skip, limit, user)
    )


@router.post(
    "/{task_id}/versions",
    status_code=201,
    summary="Create a task version",
    description=(
        "Creates the next checkpoint or release after validating language references, inline task "
        "references, and sample solutions. Administrator access is required."
    ),
    response_description="The created task version.",
)
async def create_version(
    task_id: UUID,
    body: CreateTaskVersion,
    user: CurrentUser,
) -> TaskVersion:
    return TaskVersion.model_validate(await service.create_version(task_id, body, user))


@router.get(
    "/{task_id}/versions/{version_id}",
    summary="Get a task version",
    description="Non-administrators can retrieve releases only.",
    response_description="The complete task version including task data.",
)
async def get_version(task_id: UUID, version_id: UUID, user: CurrentUser) -> TaskVersion:
    return TaskVersion.model_validate(await service.get_version(task_id, version_id, user))


@router.get(
    "/{task_id}/versions/{version_id}/sample-solutions/{model_id}/{model_version_id}",
    summary="Get a sample solution",
    description=(
        "Returns a released model version only when it is explicitly referenced by the requested "
        "task release."
    ),
    response_description="The complete, materialized sample-solution model version.",
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
