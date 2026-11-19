"""Add task-bound structure comparison models without changing the laboratory task."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.models import Model, ModelVersion

MIGRATION_ID = "14_laboratory_structure_models"
PREREQUISITE = "13_language_comparison_groups"
MODEL_KEYS = ("M01", "M02", "M03", "M04", "M05", "M06a", "M06b", "M07", "M08")


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await publish_models(apply=False)
    return await run_migration(MIGRATION_ID, lambda: publish_models(apply=True))


async def publish_models(*, apply):
    now = utcnow()
    documents = []
    for key in MODEL_KEYS:
        model = load_data(MIGRATION_ID, f"{key.lower()}.json")["model"]
        version = model["version"]
        task_ref = model["taskVersion"]
        if (version["modelId"] != model["id"] or model["latestVersionId"] != version["id"]
                or version["taskVersion"] != task_ref):
            raise RuntimeError(f"Invalid model/version references for {key}.")
        if not await db.task_version.find_one({"_id": task_ref["versionId"], "taskId": task_ref["taskId"], "kind": "release"}):
            raise RuntimeError("Required laboratory task release is missing.")
        for language in version["workspaceLanguages"]:
            if not await db.language_versions.find_one({"_id": language["versionId"], "languageId": language["languageId"], "kind": "release"}):
                raise RuntimeError("Required language release is missing.")
        fields = {name: value for name, value in model.items() if name not in {"id", "version"}}
        version_fields = {name: value for name, value in version.items() if name != "id"}
        Model.model_validate({"id": model["id"], "createdAt": now, "updatedAt": now, **fields})
        ModelVersion.model_validate({"id": version["id"], "createdAt": now, **version_fields})
        documents.extend([
            (db.model_versions, version["id"], version_fields, {}),
            (db.models, model["id"], fields, {"updatedAt": now}),
        ])
    # Validate every conflict before inserting the first document.
    for collection, identifier, fields, _ in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(name) != value for name, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")
    print(f"{'Add' if apply else 'Would add'} {len(MODEL_KEYS)} laboratory structure models (M06 split into a/b).")
    if apply:
        for collection, identifier, fields, timestamps in documents:
            await collection.update_one(
                {"_id": identifier},
                {"$setOnInsert": {**fields, "createdAt": now, **timestamps}}, upsert=True,
            )
    return len(MODEL_KEYS)
