"""Publish the public hotel chain task with an immutable release."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.tasks import Task, TaskVersion

MIGRATION_ID = "11_hotel_chain"
PREREQUISITE = "10_language_syntax_defaults"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await publish_task(apply=False)
    return await run_migration(MIGRATION_ID, lambda: publish_task(apply=True))


async def publish_task(*, apply):
    task = load_data(MIGRATION_ID, "hotel_chain.json")
    version = task["version"]
    now = utcnow()
    task_fields = {key: value for key, value in task.items() if key not in {"id", "version"}}
    version_fields = {key: value for key, value in version.items() if key != "id"}
    Task.model_validate({"id": task["id"], "createdAt": now, **task_fields})
    TaskVersion.model_validate({"id": version["id"], "createdAt": now, **version_fields})

    for reference in version["workspaceLanguages"]:
        release = await db.language_versions.find_one({
            "_id": reference["versionId"],
            "languageId": reference["languageId"],
            "kind": "release",
            "versionNumber": "2.0",
        })
        if release is None:
            raise RuntimeError(f"Required language release {reference['versionId']} (2.0) is missing.")

    # Publish the identity only after its immutable release exists.
    documents = (
        (db.task_version, version["id"], version_fields),
        (db.task, task["id"], task_fields),
    )
    for collection, identifier, fields in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")

    print(f"{'Publish' if apply else 'Would publish'}: {task['name']}")
    if apply:
        for collection, identifier, fields in documents:
            await collection.update_one(
                {"_id": identifier}, {"$setOnInsert": {**fields, "createdAt": now}}, upsert=True,
            )
    return 1
