"""Add the private laboratory task and its completion survey before study completion."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import LearningPathStep
from modeling_api.schemas.models import Model, ModelVersion
from modeling_api.schemas.surveys import Definition
from modeling_api.schemas.tasks import Task, TaskVersion
from modeling_api.services.learning_path_store import step_document

MIGRATION_ID = "12_laboratory_management"
PREREQUISITE = "11_hotel_chain"


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
    task = load_data(MIGRATION_ID, "laboratory_management.json")
    solution = load_data(MIGRATION_ID, "sample_solution.json")["model"]
    resource = load_data(MIGRATION_ID, "learning_path.json")
    version = task["version"]
    solution_version = solution["version"]
    now = utcnow()
    solution_reference = {"modelId": solution["id"], "versionId": solution_version["id"]}
    if (
        solution_version["modelId"] != solution["id"]
        or solution_reference not in version["data"].get("sampleSolutions", [])
    ):
        raise RuntimeError("The task release must reference its bundled sample solution.")
    task_fields = {key: value for key, value in task.items() if key not in {"id", "version"}}
    version_fields = {key: value for key, value in version.items() if key != "id"}
    solution_fields = {
        key: value
        for key, value in solution.items()
        if key not in {"id", "name", "ownerId", "version"}
    }
    solution_version_fields = {
        key: value for key, value in solution_version.items() if key != "id"
    }
    Task.model_validate({"id": task["id"], "createdAt": now, **task_fields})
    TaskVersion.model_validate({"id": version["id"], "createdAt": now, **version_fields})
    Model.model_validate({
        "id": solution["id"], "name": solution["name"], "ownerId": solution["ownerId"],
        "createdAt": now, "updatedAt": now, **solution_fields,
    })
    ModelVersion.model_validate({
        "id": solution_version["id"], "createdAt": now, **solution_version_fields,
    })
    step = LearningPathStep.model_validate(resource["step"])
    survey = resource["completionSurvey"]
    definition = Definition.model_validate(survey["definition"]).model_dump(exclude_none=True)

    path_id = resource["learningPathId"]
    path = await db.learning_path_templates.find_one({"_id": path_id})
    study = await db.learning_path_template_steps.find_one({
        "_id": resource["beforeStepId"], "templateId": path_id, "kind": "survey",
        "archivedAt": None,
    })
    if not path or not study:
        raise RuntimeError("The graphical modeling path and final study questionnaire must exist.")
    # Remove our own ID so retries cannot duplicate the laboratory station.
    step_ids = [identifier for identifier in path["stepIds"] if identifier != str(step.id)]
    if not step_ids or step_ids[-1] != study["_id"]:
        raise RuntimeError("The study questionnaire must be the last learning path station.")
    step_ids.insert(len(step_ids) - 1, str(step.id))

    for reference in version["workspaceLanguages"]:
        release = await db.language_versions.find_one({
            "_id": reference["versionId"],
            "languageId": reference["languageId"],
            "kind": "release",
            "versionNumber": "2.0",
        })
        if release is None:
            raise RuntimeError(f"Required language release {reference['versionId']} (2.0) is missing.")

    # Publish releases before their identities, then attach the station to the path.
    documents = (
        (db.survey_versions, survey["versionId"], {
            "surveyId": survey["id"], "version": survey["version"],
            "title": survey["title"], "definition": definition, "kind": "release",
            "createdBy": "", "releasedBy": "",
        }, {"releasedAt": now}),
        (db.surveys, survey["id"], {
            "title": survey["title"], "definition": definition,
            "version": survey["version"], "latestVersionId": survey["versionId"],
            "latestKind": "release", "activeReleaseId": survey["versionId"],
            "activeReleaseVersion": survey["version"], "revision": 1,
            "schemaVersion": 2, "deletedAt": None, "createdBy": "", "updatedBy": "",
        }, {"updatedAt": now}),
        (db.model_versions, solution_version["id"], solution_version_fields, {}),
        (db.models, solution["id"], {
            "name": solution["name"], "ownerId": solution["ownerId"], **solution_fields,
        }, {"updatedAt": now}),
        (db.task_version, version["id"], version_fields, {}),
        (db.task, task["id"], task_fields, {}),
        (db.learning_path_template_steps, str(step.id), {
            **step_document(step, path_id), "archivedAt": None,
        }, {"updatedAt": now}),
    )
    for collection, identifier, fields, timestamps in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")

    print(f"{'Add' if apply else 'Would add'}: {task['name']} with sample solution and completion questionnaire")
    if not apply:
        return 1
    for collection, identifier, fields, timestamps in documents:
        await collection.update_one(
            {"_id": identifier},
            {"$setOnInsert": {**fields, "createdAt": now, **timestamps}}, upsert=True,
        )
    if step_ids != path["stepIds"]:
        result = await db.learning_path_templates.update_one(
            {"_id": path_id, "revision": path["revision"], "stepIds": path["stepIds"]},
            {"$set": {"stepIds": step_ids, "updatedAt": now}, "$inc": {"revision": 1}},
        )
        if not result.matched_count:
            raise RuntimeError("Learning path changed during migration; rerun after stopping edits.")
    return 1
