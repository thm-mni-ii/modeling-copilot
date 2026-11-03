"""Add the annotated seminar task to the graphical data modeling path."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.registry import LANGUAGE_UPGRADE_ID
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import LearningPathStep
from modeling_api.schemas.tasks import TaskData
from modeling_api.services.learning_path_store import step_document

MIGRATION_ID = "02_seminar_management"
FINAL_SURVEY_STEP_ID = "d39da402-aaa6-59e3-92e1-69aa0ff1e64d"


async def migrate(*, apply=False):
    await require_completed(LANGUAGE_UPGRADE_ID)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await add_station(apply=False)
    return await run_migration(MIGRATION_ID, lambda: add_station(apply=True))


async def add_station(*, apply):
    resource = load_data(MIGRATION_ID, "seminar_management.json")
    task = resource["task"]
    version = resource["version"]
    TaskData.model_validate(version["data"])
    step = LearningPathStep.model_validate(resource["step"])
    path_id = resource["learningPathId"]
    path = await db.learning_path_templates.find_one({"_id": path_id})
    if path is None:
        raise RuntimeError(f"Learning path {path_id} is missing.")
    for reference in version["workspaceLanguages"]:
        language = await db.language_versions.find_one({
            "_id": reference["versionId"], "languageId": reference["languageId"],
            "kind": "release",
        })
        if language is None:
            raise RuntimeError(f"Required SERM release {reference['versionId']} is missing.")

    now = utcnow()
    documents = (
        (db.task, task["id"], {k: v for k, v in task.items() if k != "id"}),
        (db.task_version, version["id"], {k: v for k, v in version.items() if k != "id"}),
        (db.learning_path_template_steps, str(step.id), {
            **step_document(step, path_id), "archivedAt": None,
        }),
    )
    # Validate all fixed identities before writing; retries never replace edits.
    for collection, identifier, fields in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")

    print(f"{'Add' if apply else 'Would add'}: Seminarverwaltung – SERM")
    if not apply:
        return 1
    for collection, identifier, fields in documents:
        await collection.update_one(
            {"_id": identifier}, {"$setOnInsert": {**fields, "createdAt": now}}, upsert=True,
        )

    step_ids = list(path["stepIds"])
    if str(step.id) not in step_ids:
        index = step_ids.index(FINAL_SURVEY_STEP_ID) + 1 if FINAL_SURVEY_STEP_ID in step_ids else len(step_ids)
        step_ids.insert(index, str(step.id))
        result = await db.learning_path_templates.update_one(
            {"_id": path_id, "revision": path["revision"], "stepIds": path["stepIds"]},
            {"$set": {"stepIds": step_ids, "updatedAt": now}, "$inc": {"revision": 1}},
        )
        if not result.matched_count:
            raise RuntimeError("Learning path changed during migration; rerun after stopping edits.")
    return 1
