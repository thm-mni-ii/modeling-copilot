"""Independent annotation history, published atomically through a model's head pointer."""

from copy import deepcopy
from hashlib import sha256
import json

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.schemas.models import JsonPatch
from modeling_api.services.task_documents import task_document
from modeling_api.services.task_edits import EDIT_MARKS, validate_task_edit_document
from modeling_api.services.json_patches import apply_json_patches


# Bound replay work independently of the number of client save requests.
AUTO_RELEASE_ACTIONS = 500
AUTO_RELEASE_PATCH_BYTES = 256_000


def patch_bytes(operations):
    return len(json.dumps(operations, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def patch_digest(patch):
    return sha256(json.dumps(patch.model_dump(mode="json", by_alias=True), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def edit_entries(document):
    entries = {}

    def visit(node):
        for mark in node.get("marks", []):
            if mark["type"] in EDIT_MARKS:
                attrs = mark["attrs"]
                entry = entries.setdefault(attrs["editId"], {"editType": attrs["editType"], "text": "", "attrs": attrs})
                entry["text"] += node.get("text", "")
        for child in node.get("content", []):
            visit(child)

    visit(document)
    return entries


def changes_between(previous, current):
    before, after = edit_entries(previous), edit_entries(current)
    changes = []
    for edit_id in sorted(before.keys() | after.keys()):
        if before.get(edit_id) == after.get(edit_id):
            continue
        entry = after.get(edit_id) or before[edit_id]
        changes.append({"kind": "create" if edit_id not in before else "remove" if edit_id not in after else "update",
                        "editId": edit_id, "editType": entry["editType"], "text": entry["text"][:240]})
    return changes


async def snapshot(event_id, model_id):
    if not event_id:
        return None
    version = await db.task_edit_versions.find_one({"modelId": model_id, "patches.id": event_id})
    if version is None:
        raise not_found()
    action = next(patch for patch in version["patches"] if patch["id"] == event_id)
    document = await materialize(version, action["revision"])
    return {"schemaVersion": 1, "versionId": event_id, "revision": action["revision"],
            "updatedAt": version["savedAt"], "document": document}


async def original_document(model_id):
    model = await db.models.find_one({"_id": model_id}, {"taskVersion": 1})
    reference = model.get("taskVersion") if model else None
    if not reference:
        raise not_found()
    task = await db.task_version.find_one({"_id": reference["versionId"], "taskId": reference["taskId"], "kind": "release"})
    if task is None:
        raise not_found()
    data = task.get("data", {})
    return data.get("contentDocument") or task_document(data.get("contentHtml", ""))


async def materialize(version, revision):
    """Replay only the selected release phase, including states inside a batch."""
    if version["kind"] == "release" and revision == version["revision"]:
        return version["document"]
    base_id = version["baseReleaseId"]
    if base_id:
        base = await db.task_edit_versions.find_one({"_id": base_id, "modelId": version["modelId"], "kind": "release"})
        if base is None:
            raise not_found()
        document = base["document"]
    else:
        document = await original_document(version["modelId"])
    # Load a phase in one query; follow pointers to exclude competing unpublished branches.
    cursor = db.task_edit_versions.find({
        "modelId": version["modelId"], "baseReleaseId": base_id,
        "revision": {"$lt": version["revision"]},
    }, {"document": 0})
    phase = {item["_id"]: item async for item in cursor}
    chain, current = [version], version
    while current["previousVersionId"] != base_id:
        previous = phase.get(current["previousVersionId"])
        if previous is None or previous["revision"] + 1 != current["startRevision"]:
            raise conflict("The task checkpoint chain is incomplete.")
        chain.append(previous)
        current = previous
    operations = [JsonPatch.model_validate(operation)
                  for item in reversed(chain) for patch in item["patches"]
                  if patch["revision"] <= revision for operation in patch["operations"]]
    return apply_json_patches(document, operations)


async def published_versions(model, projection):
    """Walk published batch metadata without fetching document snapshots."""
    version_id = model.get("taskEditVersionId")
    while version_id:
        version = await db.task_edit_versions.find_one(
            {"_id": version_id, "modelId": model["id"]},
            {"previousVersionId": 1, "startRevision": 1, "revision": 1, **projection},
        )
        if version is None:
            raise not_found()
        yield version
        version_id = version["previousVersionId"]


async def list_history(model, skip, limit):
    items = []
    total = model.get("taskEditRevision", 0)
    if skip >= total:
        return {"items": [], "total": total}
    projection = {"savedAt": 1, "patches.id": 1, "patches.revision": 1,
                  "patches.createdAt": 1, "patches.changes": 1}
    async for version in published_versions(model, projection):
        if version["startRevision"] <= skip + limit:
            items.extend({"id": patch["id"], "revision": patch["revision"],
                          "createdAt": patch["createdAt"], "savedAt": version["savedAt"],
                          "changes": patch["changes"]}
                         for patch in version["patches"] if skip < patch["revision"] <= skip + limit)
        if version["startRevision"] <= skip + 1:
            break
    return {"items": sorted(items, key=lambda item: item["revision"]), "total": total}


async def get_snapshot(model, event_id):
    target = await db.task_edit_versions.find_one(
        {"modelId": model["id"], "patches.id": event_id}, {"revision": 1})
    if target:
        async for version in published_versions(model, {}):
            if version["_id"] == target["_id"]:
                return await snapshot(event_id, model["id"])
            if version["revision"] <= target["revision"]:
                break
    raise not_found()


async def publish(model, body, user):
    reference = model.get("taskVersion")
    if reference is None:
        raise conflict("A model without an assigned task cannot have task edits.")
    ids = [str(patch.id) for patch in body.patches]
    if len(set(ids)) != len(ids):
        raise conflict("Task editing actions must have unique identifiers.")
    # The same batch can safely be retried after a lost response.
    if body.base_revision != model.get("taskEditRevision", 0):
        stored_actions = {}
        async for version in published_versions(model, {"patches.id": 1, "patches.patchDigest": 1, "patches.revision": 1}):
            stored_actions.update((patch["id"], patch) for patch in version["patches"])
            if version["startRevision"] <= body.base_revision + 1:
                break
        if ids[-1] in stored_actions:
            for offset, patch in enumerate(body.patches, 1):
                stored = stored_actions.get(str(patch.id))
                if stored is None or stored["patchDigest"] != patch_digest(patch) or stored["revision"] != body.base_revision + offset:
                    raise conflict("An editing action identifier was reused with different content.")
            return await snapshot(model.get("taskEditVersionId"), model["id"])
        raise conflict("Task edits changed in another session. Restore your local draft after reloading.")
    original = await original_document(model["id"])
    previous = await snapshot(model.get("taskEditVersionId"), model["id"])
    document = previous["document"] if previous else original
    previous_id = model.get("taskEditVersionId")
    now = utcnow()
    head = await db.task_edit_versions.find_one({"_id": previous_id, "modelId": model["id"]},
                                               {"kind": 1, "baseReleaseId": 1, "actionsSinceRelease": 1, "bytesSinceRelease": 1}) if previous_id else None
    base_id = head["_id"] if head and head["kind"] == "release" else head["baseReleaseId"] if head else None
    action_count = head["actionsSinceRelease"] if head else 0
    byte_count = head["bytesSinceRelease"] if head else 0
    versions, actions = [], []
    for offset, patch in enumerate(body.patches, 1):
        next_document = apply_json_patches(document, patch.operations)
        validate_task_edit_document(next_document, original)
        operations = [operation.model_dump(mode="json", by_alias=True, exclude_unset=True) for operation in patch.operations]
        action_count += 1
        changes = changes_between(document, next_document)
        byte_count += patch_bytes({"operations": operations, "changes": changes})
        # MongoDB stores datetimes with millisecond precision; retries must compare equally.
        created_at = patch.created_at.replace(microsecond=patch.created_at.microsecond // 1000 * 1000)
        actions.append({"id": str(patch.id), "revision": body.base_revision + offset,
                        "createdAt": created_at, "patchDigest": patch_digest(patch),
                        "operations": operations, "changes": changes})
        document = next_document
        release = action_count >= AUTO_RELEASE_ACTIONS or byte_count >= AUTO_RELEASE_PATCH_BYTES
        if release or offset == len(body.patches):
            version = {"_id": str(patch.id), "modelId": model["id"], "previousVersionId": previous_id,
                       "baseReleaseId": base_id, "kind": "release" if release else "checkpoint",
                       "startRevision": actions[0]["revision"], "revision": actions[-1]["revision"],
                       "savedAt": now, "createdBy": user.id, "patches": actions,
                       "actionsSinceRelease": 0 if release else action_count,
                       "bytesSinceRelease": 0 if release else byte_count}
            if release:
                version["document"] = deepcopy(document)
                base_id, action_count, byte_count = version["_id"], 0, 0
            versions.append(version)
            previous_id, actions = version["_id"], []
    for version in versions:
        try:
            await db.task_edit_versions.insert_one(version)
        except DuplicateKeyError:
            existing = await db.task_edit_versions.find_one({"_id": version["_id"]})
            comparable = ("modelId", "previousVersionId", "baseReleaseId", "kind", "patches", "document", "createdBy")
            if existing is None or any(existing.get(key) != version.get(key) for key in comparable):
                raise conflict("An editing action identifier was reused.") from None
    query = {"_id": model["id"], "ownerId": user.id, "taskEditRevision": body.base_revision}
    if body.base_revision == 0:
        query.pop("taskEditRevision")
        query["$or"] = [{"taskEditRevision": 0}, {"taskEditRevision": {"$exists": False}}]
    result = await db.models.update_one(query, {"$set": {
        "taskEditVersionId": ids[-1], "taskEditRevision": versions[-1]["revision"], "updatedAt": now,
    }})
    if not result.matched_count:
        current = await db.models.find_one({"_id": model["id"]})
        if current and current.get("taskEditVersionId") == ids[-1]:
            return await snapshot(ids[-1], model["id"])
        raise conflict("Task edits changed in another session. Your local editing actions have been retained.")
    return await snapshot(ids[-1], model["id"])
