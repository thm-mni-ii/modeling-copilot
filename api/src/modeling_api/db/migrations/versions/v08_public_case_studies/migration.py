"""Publish ten case studies with informative feedback and fixed releases."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.tasks import Task, TaskVersion

MIGRATION_ID = "08_public_case_studies"
PREREQUISITE = "07_model_activity_tracking"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await publish_case_studies(apply=False)
    return await run_migration(MIGRATION_ID, lambda: publish_case_studies(apply=True))


async def publish_case_studies(*, apply):
    resource = load_data(MIGRATION_ID, "case_studies.json")
    tasks = resource["tasks"]
    now = utcnow()
    documents = []
    language_releases = set()
    for task in tasks:
        version = task["version"]
        task_fields = {key: value for key, value in task.items() if key not in {"id", "version"}}
        version_fields = {key: value for key, value in version.items() if key != "id"}
        Task.model_validate({"id": task["id"], "createdAt": now, **task_fields})
        TaskVersion.model_validate({"id": version["id"], "createdAt": now, **version_fields})
        for reference in version["workspaceLanguages"]:
            language_releases.add((reference["languageId"], reference["versionId"]))
        # Publish the identity only after its immutable release exists.
        documents.extend((
            (db.task_version, version["id"], version_fields),
            (db.task, task["id"], task_fields),
        ))

    for language_id, version_id in language_releases:
        release = await db.language_versions.find_one({
            "_id": version_id, "languageId": language_id, "kind": "release",
        })
        if release is None:
            raise RuntimeError(f"Required language release {version_id} is missing.")

    # Check every fixed identity before inserting any case-study content.
    for collection, identifier, fields in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")

    for task in tasks:
        print(f"{'Publish' if apply else 'Would publish'}: {task['name']}")
    if apply:
        for collection, identifier, fields in documents:
            await collection.update_one(
                {"_id": identifier}, {"$setOnInsert": {**fields, "createdAt": now}}, upsert=True,
            )
    return len(tasks)
