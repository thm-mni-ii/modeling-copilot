"""HTTP endpoints for models, model versions, and task edits."""

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
    TaskEditDocument,
    TaskEditVersionInfo,
    UpdateModel,
    UpdateTaskEdit,
)
from modeling_api.services import models as service
from modeling_api.services import model_activity
from modeling_api.schemas.model_activity import ActivitySession, SaveActivitySession, StoredActivityInteraction

router = APIRouter(prefix="/models", tags=["Models"])


@router.put("/{model_id}/activity/sessions/{session_id}", status_code=204,
            summary="Save an editor session and its pending interactions")
async def save_activity_session(
    model_id: UUID, session_id: UUID, body: SaveActivitySession, user: CurrentUser,
) -> None:
    await model_activity.save_session(model_id, session_id, body, user)


@router.get("/{model_id}/activity/sessions", response_model=Page[ActivitySession],
            summary="List model sessions (administrators only)")
async def list_activity_sessions(model_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 100):
    return await model_activity.list_sessions(model_id, skip, limit, user)


@router.get("/{model_id}/activity/sessions/{session_id}", response_model=ActivitySession,
            summary="Get an editor session (administrators only)")
async def activity_session(model_id: UUID, session_id: UUID, user: CurrentUser):
    return await model_activity.get_session(model_id, session_id, user)


@router.get("/{model_id}/activity/sessions/{session_id}/interactions",
            response_model=Page[StoredActivityInteraction],
            summary="List session interactions chronologically (administrators only)")
async def activity_interactions(
    model_id: UUID, session_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 100,
):
    return await model_activity.list_interactions(model_id, session_id, skip, limit, user)


@router.get(
    "",
    summary="List models",
    description="Lists models owned by the authenticated user. Large task-edit documents are omitted.",
    response_description="A paginated list of model identities.",
)
async def list_models(
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
    q: str | None = Query(default=None, max_length=256, description="Case-insensitive name search."),
    archived: bool = Query(default=False, description="Return archived models instead of active models."),
    task_bound: bool | None = Query(
        default=None,
        alias="taskBound",
        description="Filter by whether a model is assigned to a task release.",
    ),
    linked: bool | None = Query(
        default=None,
        description="Filter by whether a model is linked to a workpiece of a collab-kit room (shared or group work).",
    ),
    sort: ModelSortField = Query(default="updatedAt", description="Field used to sort the result."),
    order: SortOrder = Query(default="desc", description="Sort direction."),
) -> Page[Model]:
    return Page[Model].model_validate(
        await service.list_models(skip, limit, user, q, archived, task_bound, sort, order, linked)
    )


@router.post(
    "",
    status_code=201,
    summary="Create a model",
    description="Creates a model identity. The optional task release is immutable after creation.",
    response_description="The created model identity.",
)
async def create_model(body: CreateModel, response: Response, user: CurrentUser) -> Model:
    result = await service.create_model(body, user)
    created_response(response, result, "models")
    return Model.model_validate(result)


@router.get(
    "/{model_id}",
    summary="Get a model",
    description="Returns one model identity and its mutable workspace metadata.",
    response_description="The requested model identity and mutable metadata.",
)
async def get_model(model_id: UUID, user: CurrentUser) -> Model:
    return Model.model_validate(await service.get_model(model_id, user))


@router.patch(
    "/{model_id}",
    summary="Update model metadata",
    description="Renames, archives, restores, or updates preferences for a model.",
    response_description="The updated model.",
)
async def update_model(model_id: UUID, body: UpdateModel, user: CurrentUser) -> Model:
    return Model.model_validate(await service.update_model(model_id, body, user))


@router.delete(
    "/{model_id}",
    status_code=204,
    summary="Delete a model",
    description="Permanently deletes a model, all of its versions, and associated feedback.",
)
async def delete_model(model_id: UUID, user: CurrentUser) -> None:
    await service.delete_model(model_id, user)


@router.get(
    "/{model_id}/task-edit",
    summary="Get current task edits",
    description="Returns task edits independently from model-version snapshots, or null when no edits exist.",
    response_description="The current task-edit document or null.",
)
async def get_task_edit(model_id: UUID, user: CurrentUser) -> TaskEditDocument | None:
    result = await service.get_task_edit(model_id, user)
    return TaskEditDocument.model_validate(result) if result is not None else None


@router.put(
    "/{model_id}/task-edit",
    summary="Save local task editing actions",
    description=(
        "Publishes an idempotent batch of task editing patches as checkpoints with automatic full releases. The original task text, "
        "structure, formatting, and task references cannot be changed. A stale baseRevision "
        "returns HTTP 409."
    ),
    response_description="The saved task-edit document with its incremented revision.",
)
async def update_task_edit(
    model_id: UUID,
    body: UpdateTaskEdit,
    user: CurrentUser,
) -> TaskEditDocument:
    return TaskEditDocument.model_validate(await service.update_task_edit(model_id, body, user))


@router.get("/{model_id}/task-edit/history", response_model=Page[TaskEditVersionInfo])
async def task_edit_history(model_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 100):
    return await service.list_task_edit_history(model_id, skip, limit, user)


@router.get("/{model_id}/task-edit/history/{version_id}", response_model=TaskEditDocument)
async def task_edit_version(model_id: UUID, version_id: UUID, user: CurrentUser):
    return await service.get_task_edit_version(model_id, version_id, user)


@router.get(
    "/{model_id}/versions",
    summary="List model versions",
    description="Lists version metadata without large model data or task-edit snapshots.",
    response_description="A paginated list of model-version metadata.",
)
async def list_versions(
    model_id: UUID,
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
) -> Page[ModelVersionInfo]:
    return Page[ModelVersionInfo].model_validate(
        await service.list_versions(model_id, skip, limit, user)
    )


@router.post(
    "/{model_id}/versions",
    status_code=201,
    summary="Create a model version",
    description="Stores a full release or a patch-based checkpoint and captures the current task edits.",
    response_description="The created, materialized model version.",
)
async def create_version(
    model_id: UUID,
    body: CreateModelVersion,
    user: CurrentUser,
) -> ModelVersion:
    result = await service.create_version(model_id, body, user)
    return ModelVersion.model_validate(result)


@router.get(
    "/{model_id}/versions/{version_id}",
    summary="Get a model version",
    description="Materializes patch-based checkpoints before returning the complete model data.",
    response_description="The complete materialized model version.",
)
async def get_version(model_id: UUID, version_id: UUID, user: CurrentUser) -> ModelVersion:
    return ModelVersion.model_validate(await service.get_version(model_id, version_id, user))
