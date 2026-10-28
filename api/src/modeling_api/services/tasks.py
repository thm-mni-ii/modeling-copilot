"""Domain logic for the shared, administrator-managed task catalog."""

from html.parser import HTMLParser
from re import escape
from uuid import UUID

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, insert, list_page, save_version, to_api, utcnow
from modeling_api.schemas.tasks import CreateTask, CreateTaskVersion, UpdateTask
from modeling_api.services.languages import check_language_refs
from modeling_api.services import dagu


class _TaskReferenceMarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[str, str]] = []
        self.connection_references: list[tuple[str, str]] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        connection_language_id = values.get("data-task-connection-language-id")
        connection_type = values.get("data-task-connection-type")
        if connection_language_id is not None or connection_type is not None:
            if not connection_language_id or not connection_type:
                raise ApiError(
                    422,
                    "INVALID_CONNECTION_MARK",
                    "Connection marks require languageId and connectionType.",
                )
            self.connection_references.append((connection_language_id, connection_type))

        language_id = values.get("data-task-element-language-id")
        element_type = values.get("data-task-element-type")
        if language_id is None and element_type is None:
            return
        if not language_id or not element_type:
            raise ApiError(
                422,
                "INVALID_ELEMENT_MARK",
                "Element marks require languageId and elementType.",
            )
        self.references.append((language_id, element_type))


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "This action requires administrator access.")


async def list_tasks(
    skip: int,
    limit: int,
    user: User,
    q: str | None = None,
    archived: bool = False,
    mine: bool = False,
    visibility: str | None = None,
) -> Document:
    filters: Document = {"archivedAt": {"$ne": None} if archived and user.is_admin else None}
    if not user.is_admin:
        filters["visibility"] = "published"
    if mine:
        filters["ownerId"] = user.id
    if visibility is not None and user.is_admin:
        filters["visibility"] = visibility
    if q and q.strip():
        filters["name"] = {"$regex": escape(q.strip()), "$options": "i"}
    total = await db.task.count_documents(filters)
    cursor = await db.task.aggregate(
        [
            {"$match": filters},
            {"$sort": {"name": 1, "_id": 1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "task_version",
                    "localField": "latestReleaseId",
                    "foreignField": "_id",
                    "as": "latestRelease",
                }
            },
            {
                "$project": {
                    "name": 1,
                    "parent": 1,
                    "ownerId": 1,
                    "createdAt": 1,
                    "latestVersionId": 1,
                    "latestReleaseId": 1,
                    "latestReleaseCreatedBy": {"$arrayElemAt": ["$latestRelease.createdBy", 0]},
                    "visibility": {"$ifNull": ["$visibility", "private"]},
                    "archivedAt": 1,
                }
            },
        ]
    )
    return {"items": [to_api(task) async for task in cursor], "total": total}


async def create_task(body: CreateTask, user: User) -> Document:
    _require_admin(user)
    parent_version: Document | None = None
    if body.parent is not None:
        parent_version = await db.task_version.find_one(
            {"_id": str(body.parent.version_id), "taskId": str(body.parent.task_id)}
        )
        if parent_version is None:
            raise not_found()

    task = await insert(
        db.task,
        {
            "name": body.name,
            "parent": body.parent.model_dump(mode="json", by_alias=True) if body.parent else None,
            "ownerId": user.id,
            "latestVersionId": None,
            "latestReleaseId": None,
            "visibility": "private",
            "archivedAt": None,
        },
    )
    if parent_version is None:
        return task

    try:
        await save_version(
            db.task,
            db.task_version,
            "taskId",
            task["id"],
            None,
            user.id,
            {
                "kind": "checkpoint",
                "releaseName": None,
                "description": f"Branch of task version {parent_version['versionNumber']}",
                "workspaceLanguages": parent_version.get("workspaceLanguages", []),
                "data": parent_version["data"],
            },
        )
    except Exception:
        await db.task.delete_one({"_id": task["id"]})
        raise
    return await get_task(UUID(task["id"]), user)


async def get_task(task_id: UUID, user: User) -> Document:
    result = await db.task.find_one({"_id": str(task_id)})
    if result is None or (not user.is_admin and result.get("visibility", "private") != "published"):
        raise not_found()
    return to_api(result)


async def update_task(task_id: UUID, body: UpdateTask, user: User) -> Document:
    _require_admin(user)
    await get_task(task_id, user)
    changes: Document = {}
    if "name" in body.model_fields_set:
        changes["name"] = body.name
    if "archived" in body.model_fields_set:
        changes["archivedAt"] = utcnow() if body.archived else None
    if "visibility" in body.model_fields_set:
        changes["visibility"] = body.visibility
    await db.task.update_one({"_id": str(task_id)}, {"$set": changes})
    return await get_task(task_id, user)


async def list_versions(task_id: UUID, skip: int, limit: int, user: User) -> Document:
    await get_task(task_id, user)
    filters: Document = {"taskId": str(task_id)}
    if not user.is_admin:
        filters["kind"] = "release"
    return await list_page(
        db.task_version, filters, skip, limit, omit=("data",)
    )


async def get_version(task_id: UUID, version_id: UUID, user: User) -> Document:
    await get_task(task_id, user)
    version = await db.task_version.find_one(
        {"_id": str(version_id), "taskId": str(task_id)}
    )
    if version is None or (version.get("kind") != "release" and not user.is_admin):
        raise not_found()
    return to_api(version)


async def _validate_task_references(body: CreateTaskVersion) -> None:
    parser = _TaskReferenceMarkParser()
    try:
        parser.feed(body.data.content_html)
    except ApiError:
        raise
    except Exception as error:
        raise ApiError(422, "INVALID_TASK_HTML", "The task HTML is invalid.") from error

    selected_versions = {
        str(reference.language_id): str(reference.version_id)
        for reference in body.workspace_languages
    }
    catalogs: dict[str, tuple[set[str], set[str]]] = {}

    async def catalog(language_id: str) -> tuple[set[str], set[str]]:
        version_id = selected_versions.get(language_id)
        if version_id is None:
            raise ApiError(
                422,
                "UNKNOWN_TASK_LANGUAGE",
                "A task reference points to a language that is not selected for the task.",
            )
        if language_id not in catalogs:
            version = await db.language_versions.find_one(
                {"_id": version_id, "languageId": language_id}
            )
            if version is None:
                raise not_found()
            elements = {
                str(element.get("type"))
                for element in version.get("data", {}).get("elements", [])
                if element.get("type") is not None
            }
            connections = {
                str(connection.get("type"))
                for connection in version.get("data", {}).get("connections", [])
                if connection.get("type") is not None
            }
            catalogs[language_id] = (elements, connections)
        return catalogs[language_id]

    for language_id, element_type in parser.references:
        available_elements, _ = await catalog(language_id)
        if element_type not in available_elements:
            raise ApiError(
                422,
                "UNKNOWN_TASK_ELEMENT",
                f"Model element '{element_type}' does not exist in the selected language version.",
            )
    for language_id, connection_type in parser.connection_references:
        _, available_connections = await catalog(language_id)
        if connection_type not in available_connections:
            raise ApiError(
                422,
                "UNKNOWN_TASK_CONNECTION",
                f"Connection '{connection_type}' does not exist in the selected language version.",
            )


async def _validate_sample_solutions(body: CreateTaskVersion, user: User) -> None:
    keys = [
        (str(reference.model_id), str(reference.version_id))
        for reference in body.data.sample_solutions
    ]
    if len(keys) != len(set(keys)):
        raise ApiError(422, "DUPLICATE_REFERENCE", "A sample solution is selected more than once.")
    inherited: set[tuple[str, str]] = set()
    if body.base_version_id is not None:
        previous = await db.task_version.find_one({"_id": str(body.base_version_id)})
        inherited = {
            (str(reference.get("modelId")), str(reference.get("versionId")))
            for reference in previous.get("data", {}).get("sampleSolutions", [])
        } if previous else set()
    for model_id, version_id in keys:
        if (model_id, version_id) in inherited:
            continue
        model = await db.models.find_one({"_id": model_id, "ownerId": user.id})
        version = await db.model_versions.find_one(
            {"_id": version_id, "modelId": model_id, "kind": "release"}
        )
        if model is None or version is None:
            raise ApiError(
                422,
                "INVALID_SAMPLE_SOLUTION",
                "Sample solutions must be releases of models owned by the current user.",
            )


async def _validate_evaluation_workflows(body: CreateTaskVersion) -> None:
    names = body.data.evaluation_workflows
    if len(names) != len(set(names)):
        raise ApiError(422, "DUPLICATE_EVALUATION_WORKFLOW", "A workflow can be selected only once.")
    if not names:
        return
    available = {workflow["name"] for workflow in await dagu.list_workflows()}
    unknown = set(names) - available
    if unknown:
        raise ApiError(422, "UNKNOWN_EVALUATION_WORKFLOW", "A selected workflow is no longer available in Dagu.")


async def create_version(task_id: UUID, body: CreateTaskVersion, user: User) -> Document:
    _require_admin(user)
    await get_task(task_id, user)
    language_ids = [str(reference.language_id) for reference in body.workspace_languages]
    if len(language_ids) != len(set(language_ids)):
        raise ApiError(
            422,
            "DUPLICATE_TASK_LANGUAGE",
            "A task can use only one version of each modeling language.",
        )
    await check_language_refs(body.workspace_languages)
    if body.kind == "release":
        for reference in body.workspace_languages:
            language_release = await db.language_versions.find_one(
                {
                    "_id": str(reference.version_id),
                    "languageId": str(reference.language_id),
                    "kind": "release",
                }
            )
            if language_release is None:
                raise ApiError(
                    422,
                    "TASK_LANGUAGE_NOT_RELEASED",
                    "Task releases can use released language versions only.",
                )
    await _validate_task_references(body)
    await _validate_sample_solutions(body, user)
    await _validate_evaluation_workflows(body)
    fields = body.model_dump(mode="json", by_alias=True, exclude={"base_version_id"})
    result = await save_version(
        db.task,
        db.task_version,
        "taskId",
        str(task_id),
        str(body.base_version_id) if body.base_version_id else None,
        user.id,
        fields,
    )
    if body.kind == "release":
        await db.task.update_one(
            {"_id": str(task_id)},
            {"$set": {"latestReleaseId": result["id"], "visibility": "published"}},
        )
    return result


async def ensure_release_reference(task_id: UUID, version_id: UUID, user: User | None = None) -> Document:
    if user is not None:
        await get_task(task_id, user)
    version = await db.task_version.find_one(
        {"_id": str(version_id), "taskId": str(task_id), "kind": "release"}
    )
    if version is None:
        raise not_found()
    return to_api(version)


async def get_sample_solution(
    task_id: UUID,
    version_id: UUID,
    model_id: UUID,
    model_version_id: UUID,
    user: User,
) -> Document:
    task_version = await get_version(task_id, version_id, user)
    wanted = {"modelId": str(model_id), "versionId": str(model_version_id)}
    if wanted not in task_version["data"].get("sampleSolutions", []):
        raise not_found()
    solution = await db.model_versions.find_one(
        {"_id": str(model_version_id), "modelId": str(model_id), "kind": "release"}
    )
    if solution is None:
        raise not_found()
    from modeling_api.services.models import _materialize_version

    return to_api(await _materialize_version(solution))


def same_content(left: Document, right: Document) -> bool:
    """Compatibility helper still shared by the feedback import service."""
    import json

    dump = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return dump(left) == dump(right)
