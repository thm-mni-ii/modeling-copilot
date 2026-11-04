"""Discard legacy task-edit data and initialize the checkpoint-based task-edit history."""

import re

from pymongo import ASCENDING

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration

MIGRATION_ID = "05_task_edit_history"
PREREQUISITE = "04_maintenance_management"

# Intermediate development collections plus the current history, which restarts empty.
DISCARDED_COLLECTIONS = ("task_edit_events", "task_edit_documents", "task_edit_versions")
LEGACY_NAME = re.compile(r"task[_-]?edit", re.IGNORECASE)
# Current fields with their initial values; every other task-edit key is legacy.
CURRENT_FIELDS = {
    "models": {"taskEditVersionId": None, "taskEditRevision": 0},
    "model_versions": {"taskEditVersionId": None},
    "evaluations": {},
}


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await reset_task_edits(apply=False)
    return await run_migration(MIGRATION_ID, lambda: reset_task_edits(apply=True))


async def top_level_keys(collection):
    cursor = await collection.aggregate([
        {"$project": {"fields": {"$objectToArray": "$$ROOT"}}},
        {"$unwind": "$fields"},
        {"$group": {"_id": "$fields.k"}},
    ])
    return {item["_id"] async for item in cursor}


async def legacy_indexes(name):
    indexes = []
    async for index in await db[name].list_indexes():
        if any(LEGACY_NAME.search(field) for field in index["key"]):
            indexes.append(index["name"])
    return indexes


async def update_plans(name):
    """Return (label, filter, update) tuples for one collection."""
    current = CURRENT_FIELDS[name]
    legacy = sorted(key for key in await top_level_keys(db[name])
                    if LEGACY_NAME.search(key) and key not in current)
    conditions = [{field: {"$exists": True}} for field in legacy]
    for field, value in current.items():
        conditions += [{field: {"$exists": False}}, {field: {"$ne": value}}]
    update = {}
    if current:
        update["$set"] = dict(current)
    if legacy:
        update["$unset"] = {field: "" for field in legacy}
    plans = [(f"{name} (legacy fields: {', '.join(legacy) or '-'})", {"$or": conditions}, update)] if conditions else []
    if name == "evaluations":
        # Evaluation results stay; only the embedded edit copy handed to the workflow is dropped.
        plans.append((f"{name} (submission snapshots)",
                      {"submissionSnapshot.taskEditSnapshot": {"$ne": None}},
                      {"$set": {"submissionSnapshot.taskEditSnapshot": None}}))
    return plans


async def reset_task_edits(*, apply):
    verb = "Update" if apply else "Would update"
    changed = 0
    for name in CURRENT_FIELDS:
        for label, query, update in await update_plans(name):
            count = await db[name].count_documents(query)
            print(f"{verb} {label}: {count} document(s)")
            changed += count
            if apply and count:
                await db[name].update_many(query, update)
        for index in await legacy_indexes(name):
            print(f"{'Drop' if apply else 'Would drop'} index {name}.{index}")
            if apply:
                await db[name].drop_index(index)

    existing = set(await db.list_collection_names())
    for name in DISCARDED_COLLECTIONS:
        if name not in existing:
            continue
        count = await db[name].estimated_document_count()
        print(f"{'Drop' if apply else 'Would drop'} collection {name}: {count} document(s)")
        changed += count
        if apply:
            await db[name].drop()

    if apply:
        await db.task_edit_versions.create_index(
            [("modelId", ASCENDING), ("patches.id", ASCENDING)], unique=True)
        await db.task_edit_versions.create_index(
            [("modelId", ASCENDING), ("baseReleaseId", ASCENDING), ("revision", ASCENDING)])
    return changed
