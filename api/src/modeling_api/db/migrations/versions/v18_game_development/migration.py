"""Add the game development case study and update shared path labels."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import LearningPathStep
from modeling_api.schemas.models import Model, ModelVersion
from modeling_api.schemas.surveys import Definition
from modeling_api.schemas.tasks import Task, TaskVersion
from modeling_api.services.learning_path_store import step_document

MIGRATION_ID = "18_game_development"
PREREQUISITE = "17_help_feedback_quotas"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await update_labels(apply=False)
    return await run_migration(MIGRATION_ID, lambda: update_labels(apply=True))


async def update_labels(*, apply):
    resource = load_data(MIGRATION_ID, "labels.json")
    path_id = resource["learningPathId"]
    path = await db.learning_path_templates.find_one({"_id": path_id})
    if not path:
        raise RuntimeError("The graphical modeling path must exist.")
    now = utcnow()
    documents, step_ids, additions = await prepare_game_development(path, now)

    # Resolve every fixed identity before writing; positions and titles may change.
    changes = []
    for label in resource["steps"]:
        step = await db.learning_path_template_steps.find_one({
            "_id": label["id"], "templateId": path_id,
            "kind": label["kind"], "archivedAt": None,
        })
        if not step or step["_id"] not in path["stepIds"]:
            raise RuntimeError(f"Required path station {label['id']} is missing or archived.")
        if step["title"] != label["title"]:
            changes.append((step, label["title"]))

    path_changed = path["title"] != resource["title"] or path["stepIds"] != step_ids
    count = int(path_changed) + len(changes) + additions
    if path_changed:
        print(f"{'Rename' if apply else 'Would rename'} path: {path['title']} -> {resource['title']}")
    for step, title in changes:
        print(f"{'Rename' if apply else 'Would rename'} station {step['_id']}: {step['title']} -> {title}")
    if not apply or not count:
        return count

    # Publish referenced content before exposing the appended stations.
    for collection, identifier, fields, timestamps in documents:
        await collection.update_one(
            {"_id": identifier},
            {"$setOnInsert": {**fields, "createdAt": now, **timestamps}}, upsert=True,
        )
    # Invalidate open path editor drafts before changing their station labels.
    result = await db.learning_path_templates.update_one(
        {"_id": path_id, "revision": path["revision"], "stepIds": path["stepIds"],
         "title": path["title"]},
        {"$set": {"title": resource["title"], "stepIds": step_ids, "updatedAt": now},
         "$inc": {"revision": 1}},
    )
    if not result.matched_count:
        raise RuntimeError("Learning path changed during migration; retry with path writes stopped.")
    for step, title in changes:
        result = await db.learning_path_template_steps.update_one(
            {"_id": step["_id"], "templateId": path_id, "kind": step["kind"],
             "archivedAt": None, "title": step["title"]},
            {"$set": {"title": title, "updatedAt": now}},
        )
        if not result.matched_count:
            raise RuntimeError("Path station changed during migration; retry with path writes stopped.")
    return count


async def prepare_game_development(path, now):
    resource = load_data(MIGRATION_ID, "game_development.json")
    if resource["learningPathId"] != path["_id"]:
        raise RuntimeError("Game development must belong to the graphical modeling path.")
    task = resource["task"]
    version = task["version"]
    task_fields = {key: value for key, value in task.items() if key not in {"id", "version"}}
    version_fields = {key: value for key, value in version.items() if key != "id"}
    Task.model_validate({"id": task["id"], "createdAt": now, **task_fields})
    TaskVersion.model_validate({"id": version["id"], "createdAt": now, **version_fields})
    if (version["taskId"] != task["id"] or version["kind"] != "release"
            or task["latestVersionId"] != version["id"] or task["latestReleaseId"] != version["id"]):
        raise RuntimeError("Invalid game development task release references.")
    for reference in version["workspaceLanguages"]:
        if not await db.language_versions.find_one({
            "_id": reference["versionId"], "languageId": reference["languageId"], "kind": "release",
        }):
            raise RuntimeError("The required SERM language release is missing.")

    solution = load_data(MIGRATION_ID, "sample_solution.json")["model"]
    solution_version = solution["version"]
    solution_fields = {key: value for key, value in solution.items() if key not in {"id", "version"}}
    solution_version_fields = {key: value for key, value in solution_version.items() if key != "id"}
    reference = {"modelId": solution["id"], "versionId": solution_version["id"]}
    task_reference = {"taskId": task["id"], "versionId": version["id"]}
    if (reference not in version["data"].get("sampleSolutions", [])
            or solution["latestVersionId"] != solution_version["id"]
            or solution_version["modelId"] != solution["id"]
            or solution_version["kind"] != "release"
            or solution["taskVersion"] != task_reference
            or solution_version["taskVersion"] != task_reference):
        raise RuntimeError("Invalid game development sample solution references.")
    Model.model_validate({"id": solution["id"], "createdAt": now, "updatedAt": now, **solution_fields})
    ModelVersion.model_validate({"id": solution_version["id"], "createdAt": now, **solution_version_fields})
    documents = [
        (db.model_versions, solution_version["id"], solution_version_fields, {}),
        (db.models, solution["id"], solution_fields, {"updatedAt": now}),
    ]
    survey = resource["weeklySurvey"]
    definition = Definition.model_validate(survey["definition"]).model_dump(exclude_none=True)
    documents.extend([
        (db.survey_versions, survey["versionId"], {
            "surveyId": survey["id"], "version": survey["version"], "title": survey["title"],
            "definition": definition, "kind": "release", "createdBy": "", "releasedBy": "",
        }, {"releasedAt": now}),
        (db.surveys, survey["id"], {
            "title": survey["title"], "definition": definition, "version": survey["version"],
            "latestVersionId": survey["versionId"], "latestKind": "release",
            "activeReleaseId": survey["versionId"], "activeReleaseVersion": survey["version"],
            "revision": 1, "schemaVersion": 2, "deletedAt": None, "createdBy": "", "updatedBy": "",
        }, {"updatedAt": now}),
    ])
    documents.extend([
        (db.task_version, version["id"], version_fields, {}),
        (db.task, task["id"], task_fields, {}),
    ])
    steps = [LearningPathStep.model_validate(step) for step in resource["steps"]]
    if (len(steps) != 2 or steps[0].type != "task" or steps[1].type != "survey"
            or str(steps[0].task_version.task_id) != task["id"]
            or str(steps[0].task_version.version_id) != version["id"]
            or steps[0].after_survey_id is not None
            or str(steps[1].survey_id) != resource["weeklySurvey"]["id"]):
        raise RuntimeError("Invalid game development station references.")
    if steps[0].minimum_score_percent is not None and not version["data"].get("sampleSolutions"):
        raise RuntimeError("A minimum score requires a game development sample solution.")
    new_ids = [str(step.id) for step in steps]
    step_ids = [identifier for identifier in path["stepIds"] if identifier not in new_ids]
    if not step_ids or step_ids[-1] != resource["afterStepId"]:
        raise RuntimeError("Game development must follow the third weekly completion station.")
    for step in steps:
        documents.append((db.learning_path_template_steps, str(step.id), {
            **step_document(step, path["_id"]), "archivedAt": None,
        }, {"updatedAt": now}))

    # Check every conflict before the first insert so retries cannot overwrite edits.
    additions = 0
    for collection, identifier, fields, _ in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")
        additions += int(existing is None)
    print(f"Game development: {additions} document(s) to add; append task and weekly completion 4.")
    return documents, step_ids + new_ids, additions
