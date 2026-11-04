"""Add the annotated maintenance task between seminar and study completion."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import LearningPathStep
from modeling_api.schemas.tasks import TaskData
from modeling_api.services.learning_path_store import step_document

MIGRATION_ID = "04_maintenance_management"
PREREQUISITE = "03_update_survey"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await add_station(apply=False)
    return await run_migration(MIGRATION_ID, lambda: add_station(apply=True))


async def add_station(*, apply):
    resource = load_data(MIGRATION_ID, "maintenance_management.json")
    task = resource["task"]
    version = resource["version"]
    TaskData.model_validate(version["data"])
    step = LearningPathStep.model_validate(resource["step"])
    path_id = resource["learningPathId"]
    path = await db.learning_path_templates.find_one({"_id": path_id})
    seminar = await db.learning_path_template_steps.find_one({
        "_id": resource["afterStepId"], "templateId": path_id, "kind": "task",
        "archivedAt": None,
    })
    study = await db.learning_path_template_steps.find_one({
        "_id": resource["beforeStepId"], "templateId": path_id, "kind": "survey",
        "archivedAt": None,
    })
    if not path or not seminar or not study:
        raise RuntimeError("The graphical modeling path, seminar and study stations must exist.")
    # Removing our own ID also accepts a retry after the insertion succeeded.
    step_ids = [identifier for identifier in path["stepIds"] if identifier != str(step.id)]
    if (
        seminar["_id"] not in step_ids or study["_id"] not in step_ids
        or step_ids.index(study["_id"]) != step_ids.index(seminar["_id"]) + 1
    ):
        raise RuntimeError("Seminar and study completion must be consecutive path stations.")
    step_ids.insert(step_ids.index(study["_id"]), str(step.id))
    if seminar["task"].get("afterSurveyId") != str(step.after_survey_id):
        raise RuntimeError("The seminar completion questionnaire differs from the migration.")
    survey = await db.surveys.find_one({"_id": str(step.after_survey_id), "deletedAt": None})
    if not survey or not survey.get("activeReleaseId"):
        raise RuntimeError("The seminar completion questionnaire must have an active release.")
    seminar_version = await db.task_version.find_one({
        "_id": seminar["task"]["releaseId"], "taskId": seminar["task"]["taskId"],
        "kind": "release",
    })
    if not seminar_version or seminar_version.get("workspaceLanguages") != version["workspaceLanguages"]:
        raise RuntimeError("The seminar SERM release differs from the migration.")
    for reference in version["workspaceLanguages"]:
        language = await db.language_versions.find_one({
            "_id": reference["versionId"], "languageId": reference["languageId"],
            "kind": "release",
        })
        if language is None:
            raise RuntimeError(f"Required SERM release {reference['versionId']} is missing.")

    documents = (
        (db.task, task["id"], {k: v for k, v in task.items() if k != "id"}),
        (db.task_version, version["id"], {k: v for k, v in version.items() if k != "id"}),
        (db.learning_path_template_steps, str(step.id), {
            **step_document(step, path_id), "archivedAt": None,
        }),
    )
    for collection, identifier, fields in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")

    print(f"{'Add' if apply else 'Would add'}: Wartungsverwaltung – SERM")
    if not apply:
        return 1
    now = utcnow()
    for collection, identifier, fields in documents:
        await collection.update_one(
            {"_id": identifier}, {"$setOnInsert": {**fields, "createdAt": now}}, upsert=True,
        )
    if step_ids != path["stepIds"]:
        result = await db.learning_path_templates.update_one(
            {"_id": path_id, "revision": path["revision"], "stepIds": path["stepIds"]},
            {"$set": {"stepIds": step_ids, "updatedAt": now}, "$inc": {"revision": 1}},
        )
        if not result.matched_count:
            raise RuntimeError("Learning path changed during migration; rerun after stopping edits.")
    return 1
