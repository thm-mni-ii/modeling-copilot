"""Model and model-version domain logic scoped to the authenticated owner."""

from collections.abc import Collection
from copy import deepcopy
from re import escape
from uuid import UUID

from modeling_api.core.auth import User
from modeling_api.core.errors import conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import (
    Document,
    insert,
    list_page,
    save_version,
    sort_stages,
    to_api,
    utcnow,
)
from modeling_api.schemas.models import (
    CreateModel,
    CreateModelVersion,
    ModelSortField,
    SortOrder,
    UpdateTaskEdit,
    UpdateModel,
)
from modeling_api.services.languages import check_language_refs
from modeling_api.services.learning_path_access import require_model_access
from modeling_api.services.xml_patches import apply_patches, validate_model_xml
from modeling_api.services import task_edit_history


async def list_models(
    skip: int,
    limit: int,
    user: User,
    q: str | None = None,
    archived: bool = False,
    task_bound: bool | None = None,
    sort: ModelSortField = "updatedAt",
    order: SortOrder = "desc",
) -> Document:
    filters: Document = {"ownerId": user.id}
    filters["archivedAt"] = {"$ne": None} if archived else None
    if task_bound is not None:
        filters["taskVersion"] = {"$ne": None} if task_bound else None
    if q and q.strip():
        filters["name"] = {"$regex": escape(q.strip()), "$options": "i"}
    cursor = await db.models.aggregate(
        [
            {"$match": filters},
            {
                "$lookup": {
                    "from": "learning_path_run_steps",
                    "localField": "_id",
                    "foreignField": "modelId",
                    "as": "_pathSteps",
                }
            },
            {"$match": {"_pathSteps": {"$eq": []}}},
            {
                "$facet": {
                    "items": [
                        *sort_stages(sort, descending=order != "asc"),
                        {"$skip": skip},
                        {"$limit": limit},
                        {
                            "$project": {
                                "_pathSteps": 0,
                                "taskEditBaseSignature": 0,
                                "taskEdit": 0,
                            }
                        },
                    ],
                    "count": [{"$count": "total"}],
                }
            },
        ]
    )
    result = await cursor.to_list(length=1)
    page = result[0]
    return {
        "items": [to_api(item) for item in page["items"]],
        "total": page["count"][0]["total"] if page["count"] else 0,
    }


async def create_model(body: CreateModel, user: User) -> Document:
    if body.task_version is not None:
        from modeling_api.services.tasks import ensure_release_reference

        await ensure_release_reference(
            body.task_version.task_id, body.task_version.version_id, user
        )
    return await insert(db.models, model_fields(body, user))


def model_fields(body: CreateModel, user: User) -> Document:
    """Shared initialization for ordinary and path-owned task models."""
    return {
        "name": body.name,
        "ownerId": user.id,
        "latestVersionId": None,
        "taskVersion": (
            body.task_version.model_dump(mode="json", by_alias=True)
            if body.task_version
            else None
        ),
        "taskEditVersionId": None,
        "taskEditRevision": 0,
        "preferences": {},
        "updatedAt": utcnow(),
        "archivedAt": None,
    }


async def get_model(model_id: UUID, user: User) -> Document:
    result = await db.models.find_one({"_id": str(model_id), "ownerId": user.id})
    if result is None:
        raise not_found()
    await require_model_access(model_id, user)
    api_model = to_api(result)
    api_model.pop("taskEditBaseSignature", None)
    api_model["taskEdit"] = await task_edit_history.snapshot(result.get("taskEditVersionId"), str(model_id))
    return api_model


async def update_model(model_id: UUID, body: UpdateModel, user: User) -> Document:
    await get_model(model_id, user)
    changes: Document = {"updatedAt": utcnow()}
    if "name" in body.model_fields_set:
        changes["name"] = body.name
    if "archived" in body.model_fields_set:
        changes["archivedAt"] = utcnow() if body.archived else None
    if "preferences" in body.model_fields_set:
        changes["preferences"] = body.preferences
    await db.models.update_one({"_id": str(model_id), "ownerId": user.id}, {"$set": changes})
    return await get_model(model_id, user)


async def delete_model(model_id: UUID, user: User) -> None:
    """Administrative hard delete; the regular UI archives models instead."""
    await get_model(model_id, user)
    model_id_str = str(model_id)
    if await db.learning_path_run_steps.find_one({"modelId": model_id_str}):
        raise conflict("Models referenced by a learning-path step cannot be deleted.")
    await _purge_model(model_id_str, user.id)


async def _purge_model(model_id: str, owner_id: str) -> None:
    """Löscht das Modell mit allem, was an ihm hängt; ohne Prüfung, die macht der Aufrufer."""
    await db.feedback.delete_many({"modelId": model_id})
    await db.model_versions.delete_many({"modelId": model_id})
    await db.task_edit_versions.delete_many({"modelId": model_id})
    session_ids = await db.model_activity_sessions.distinct("_id", {"modelId": model_id})
    await db.model_activity_interactions.delete_many({"sessionId": {"$in": session_ids}})
    await db.model_activity_sessions.delete_many({"modelId": model_id})
    await db.models.delete_one({"_id": model_id, "ownerId": owner_id})


async def delete_room_models(
    room_id: str,
    owner_id: str | None = None,
    *,
    except_owners: Collection[str] = (),
    keep_workpiece_id: str | None = None,
) -> None:
    """Löscht die Arbeitskopien eines Raums, die beim Beitreten entstehen; mit `owner_id` nur die dieser Person.

    `except_owners` nimmt Personen aus, die ihre Kopie gerade noch offen haben; `keep_workpiece_id`
    lässt die Kopien des laufenden Workpieces stehen und löscht nur liegengebliebene älterer Shares.
    Erkannt werden sie an `preferences.collab.roomId`. Was jemand behält, ist ein neues Modell ohne
    diese Verknüpfung und bleibt. Mehrfach aufgerufen ändert es nichts.
    """
    filters: Document = {"preferences.collab.roomId": room_id}
    if owner_id is not None:
        filters["ownerId"] = owner_id
    elif except_owners:
        filters["ownerId"] = {"$nin": list(except_owners)}
    if keep_workpiece_id is not None:
        filters["preferences.collab.workpieceId"] = {"$ne": keep_workpiece_id}
    # Erst lesen, dann löschen, damit der Cursor nicht über eine sich ändernde Collection läuft.
    for model in [model async for model in db.models.find(filters, {"_id": 1, "ownerId": 1})]:
        await _purge_model(model["_id"], model["ownerId"])


async def get_task_edit(model_id: UUID, user: User) -> Document | None:
    model = await get_model(model_id, user)
    return model.get("taskEdit")


async def get_shared_task(model_id: UUID, user: User) -> Document:
    """Title, text, release and the settings of the model's task, as sharing puts them into the room."""
    model = await get_model(model_id, user)
    reference = model.get("taskVersion")
    if reference is None:
        raise conflict("A model without an assigned task cannot share one.")
    version = await db.task_version.find_one(
        {"_id": reference["versionId"], "taskId": reference["taskId"], "kind": "release"}
    )
    task = await db.task.find_one({"_id": reference["taskId"]})
    if version is None or task is None:
        raise not_found()
    data = version.get("data", {})
    return {
        "title": task.get("name", ""),
        "contentHtml": data.get("contentHtml", ""),
        "taskVersion": reference,
        # What the task prescribes for working on it, so the room follows it as the private model does.
        "settings": {
            "autonomyMode": data.get("autonomyMode", "free"),
            "connectionPreviewAllowed": data.get("connectionPreviewAllowed"),
            "evaluationWorkflows": data.get("evaluationWorkflows", []),
            "evaluationAvailable": bool(data.get("sampleSolutions")),
        },
    }


async def ensure_task_questionnaire_completed(model_id):
    from modeling_api.services.learning_path_store import (
        template_document, run_by_model, run_sessions, linked_session,
    )

    found = await run_by_model(model_id)
    if not found:
        return
    run, state = found
    if state.get("completedAt"):
        return
    template = await template_document(run["templateId"])
    step = next((s for s in template["steps"] if s["id"] == state["stepId"]), None)
    survey_id = step.get("task", {}).get("beforeSurveyId") if step else None
    assignment = {"surveyId": survey_id} if survey_id else None
    if assignment:
        session = linked_session(state, assignment, await run_sessions(run), "before")
        if not session or session["status"] != "submitted":
            raise conflict("Complete the questionnaire before working on the task.")


async def update_task_edit(model_id: UUID, body: UpdateTaskEdit, user: User) -> Document:
    model = await get_model(model_id, user)
    await ensure_task_questionnaire_completed(model_id)
    return await task_edit_history.publish(model, body, user)


async def list_task_edit_history(model_id, skip, limit, user):
    return await task_edit_history.list_history(await get_model(model_id, user), skip, limit)


async def get_task_edit_version(model_id, version_id, user):
    return await task_edit_history.get_snapshot(await get_model(model_id, user), str(version_id))


async def list_versions(model_id: UUID, skip: int, limit: int, user: User) -> Document:
    await get_model(model_id, user)
    return await list_page(
        db.model_versions,
        {"modelId": str(model_id)},
        skip,
        limit,
        omit=("data", "taskEditSnapshot"),
    )


async def get_version(model_id: UUID, version_id: UUID, user: User) -> Document:
    await get_model(model_id, user)
    version = await db.model_versions.find_one(
        {"_id": str(version_id), "modelId": str(model_id)}
    )
    if version is None:
        raise not_found()
    result = await _materialize_version(version)
    result["taskEditSnapshot"] = await task_edit_history.snapshot(version.get("taskEditVersionId"), str(model_id))
    return to_api(result)


async def _materialize_version(version: Document) -> Document:
    """Returns a version with complete data.xml while keeping storage compact."""
    data = version.get("data", {})
    if version.get("kind") == "release" or isinstance(data.get("xml"), str):
        return version

    base_release_id = version.get("baseReleaseId")
    if not base_release_id:
        raise conflict("The checkpoint has no base release.")
    release = await db.model_versions.find_one(
        {
            "_id": base_release_id,
            "modelId": version["modelId"],
            "kind": "release",
        }
    )
    if release is None or not isinstance(release.get("data", {}).get("xml"), str):
        raise conflict("The checkpoint base release is unavailable.")

    patch_xml: list[str] = []
    found_target = False
    cursor = db.model_versions.find(
        {
            "modelId": version["modelId"],
            "kind": "checkpoint",
            "baseReleaseId": base_release_id,
        }
    ).sort([("createdAt", 1), ("_id", 1)])
    async for checkpoint in cursor:
        patch_xml.extend(patch["xml"] for patch in checkpoint.get("patches", []))
        if checkpoint["_id"] == version["_id"]:
            found_target = True
            break
    if not found_target:
        raise conflict("The checkpoint does not belong to the expected release phase.")

    result = deepcopy(version)
    result["data"] = {
        **deepcopy(release["data"]),
        **deepcopy(version.get("data", {})),
        "xml": apply_patches(release["data"]["xml"], patch_xml),
    }
    return result


async def create_version(model_id: UUID, body: CreateModelVersion, user: User) -> Document:
    model = await get_model(model_id, user)
    if model.get("latestVersionId"):
        await ensure_task_questionnaire_completed(model_id)
    # Models store direct language selections only. Dependencies are resolved
    # from the selected language versions when needed.
    await check_language_refs(body.workspace_languages)
    model_task = model.get("taskVersion")
    supplied_task = (
        body.task_version.model_dump(mode="json", by_alias=True) if body.task_version else None
    )
    if supplied_task != model_task:
        raise conflict("A model's assigned task version cannot be changed.")
    if body.task_version is not None:
        from modeling_api.services.tasks import ensure_release_reference

        task_release = await ensure_release_reference(
            body.task_version.task_id, body.task_version.version_id, user
        )
        selected_languages = {
            (str(reference.language_id), str(reference.version_id))
            for reference in body.workspace_languages
        }
        required_languages = {
            (str(reference["languageId"]), str(reference["versionId"]))
            for reference in task_release.get("workspaceLanguages", [])
            if reference.get("source") == "required"
        }
        if not required_languages.issubset(selected_languages):
            raise conflict(
                "Language versions required by the task cannot be changed."
            )

    previous = None
    if body.base_version_id is not None:
        previous = await db.model_versions.find_one(
            {"_id": str(body.base_version_id), "modelId": str(model_id)}
        )
        if previous is None:
            raise conflict()

    fields = body.model_dump(
        mode="json",
        by_alias=True,
        exclude={"base_version_id", "base_release_id"},
    )
    task_edit_id = model.get("taskEditVersionId") if model_task else None
    if "task_edit_version_id" in body.model_fields_set:
        task_edit_id = str(body.task_edit_version_id) if body.task_edit_version_id else None
        if task_edit_id:
            await task_edit_history.get_snapshot(model, task_edit_id)
    fields["taskEditVersionId"] = task_edit_id
    if body.kind == "release":
        validate_model_xml(body.data["xml"])
        fields.pop("patches", None)
    else:
        if previous is None:
            raise conflict("A release must be saved before the first checkpoint.")
        base_release_id = (
            previous["_id"] if previous.get("kind") == "release" else previous.get("baseReleaseId")
        )
        if not base_release_id:
            raise conflict("No base release could be determined for the checkpoint.")
        if body.base_release_id is not None and str(body.base_release_id) != base_release_id:
            raise conflict("The base release changed. Reload the model before saving again.")
        previous_materialized = await _materialize_version(previous)
        apply_patches(
            previous_materialized["data"]["xml"],
            [patch.xml for patch in body.patches],
        )
        fields["baseReleaseId"] = base_release_id

    result = await save_version(
        db.models,
        db.model_versions,
        "modelId",
        str(model_id),
        str(body.base_version_id) if body.base_version_id else None,
        user.id,
        fields,
    )
    await db.models.update_one({"_id": str(model_id)}, {"$set": {"updatedAt": utcnow()}})
    stored = await db.model_versions.find_one({"_id": str(result["id"])})
    if stored is None:
        raise not_found()
    result = await _materialize_version(stored)
    result["taskEditSnapshot"] = await task_edit_history.snapshot(stored.get("taskEditVersionId"), str(model_id))
    return to_api(result)
