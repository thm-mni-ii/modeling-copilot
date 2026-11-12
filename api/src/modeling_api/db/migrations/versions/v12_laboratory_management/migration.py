"""Publish the laboratory task, its evaluation requirement and path help choices."""

from uuid import UUID, uuid5

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import LearningPathStep, HelpRequestConfig
from modeling_api.schemas.models import Model, ModelVersion
from modeling_api.schemas.surveys import Definition
from modeling_api.schemas.tasks import Task, TaskVersion
from modeling_api.services.learning_path_store import step_document
from modeling_api.services import help_questionnaire

MIGRATION_ID = "12_laboratory_management"
PREREQUISITE = "11_hotel_chain"
SYNONYM_MODEL_FILES = (
    "synonym_spelling.json",
    "synonym_typos_abbreviations.json",
    "synonym_terms.json",
    "synonym_languages.json",
    "synonym_ambiguity.json",
)


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await migrate_content(apply=False)
    return await run_migration(MIGRATION_ID, lambda: migrate_content(apply=True))


async def migrate_content(*, apply):
    changed = await publish_task(apply=apply)
    changed += await initialize_minimum_scores(apply=apply)
    async for template in db.learning_path_templates.find({"helpRequests.enabled": True}):
        survey_id = str(uuid5(UUID(template["_id"]), "help-questionnaire"))
        survey = await db.surveys.find_one({"_id": survey_id})
        questions = survey.get("definition", {}).get("elements", []) if survey else []
        if any(help_questionnaire.AUTOMATIC_FEEDBACK in question.get("choices", []) for question in questions):
            continue
        print(f"{'Update' if apply else 'Would update'} help choices for learning path {template['_id']}.")
        if apply:
            revision = template["revision"] + 1
            result = await db.learning_path_templates.update_one(
                {"_id": template["_id"], "revision": template["revision"]},
                {"$inc": {"revision": 1}, "$set": {"updatedAt": utcnow()}},
            )
            if not result.matched_count:
                raise RuntimeError("The learning path changed during migration. Retry with path writes stopped.")
            await help_questionnaire.publish(
                template["_id"], template["title"], revision,
                HelpRequestConfig.model_validate(template["helpRequests"]), template.get("createdBy", ""),
            )
        changed += 1
    return changed


async def initialize_minimum_scores(*, apply):
    query = {"kind": "task", "task.minimumScorePercent": {"$exists": False}}
    count = await db.learning_path_template_steps.count_documents(query)
    print(f"{'Initialize' if apply else 'Would initialize'} optional minimum scores for {count} task steps.")
    if apply:
        result = await db.learning_path_template_steps.update_many(
            query, {"$set": {"task.minimumScorePercent": None}}
        )
        return result.modified_count
    return count


async def publish_task(*, apply):
    task = load_data(MIGRATION_ID, "laboratory_management.json")
    solution = load_data(MIGRATION_ID, "sample_solution.json")["model"]
    checks = [load_data(MIGRATION_ID, filename)["model"] for filename in SYNONYM_MODEL_FILES]
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
    Task.model_validate({"id": task["id"], "createdAt": now, **task_fields})
    TaskVersion.model_validate({"id": version["id"], "createdAt": now, **version_fields})
    model_documents = []
    for model in [solution, *checks]:
        model_version = model["version"]
        model_fields = {
            key: value for key, value in model.items()
            if key not in {"id", "name", "ownerId", "version"}
        }
        model_version_fields = {
            key: value for key, value in model_version.items() if key != "id"
        }
        if (
            model_version["modelId"] != model["id"]
            or model["latestVersionId"] != model_version["id"]
            or model["taskVersion"] != {"taskId": task["id"], "versionId": version["id"]}
            or model_version["taskVersion"] != model["taskVersion"]
        ):
            raise RuntimeError(f"Invalid model references for {model['name']}.")
        Model.model_validate({
            "id": model["id"], "name": model["name"], "ownerId": model["ownerId"],
            "createdAt": now, "updatedAt": now, **model_fields,
        })
        ModelVersion.model_validate({
            "id": model_version["id"], "createdAt": now, **model_version_fields,
        })
        model_documents.extend([
            (db.model_versions, model_version["id"], model_version_fields, {}),
            (db.models, model["id"], {
                "name": model["name"], "ownerId": model["ownerId"], **model_fields,
            }, {"updatedAt": now}),
        ])
    step = LearningPathStep.model_validate(resource["step"])
    study_step = LearningPathStep.model_validate(resource["studyStep"])
    survey = resource["completionSurvey"]
    definition = Definition.model_validate(survey["definition"]).model_dump(exclude_none=True)

    path_id = resource["learningPathId"]
    path = await db.learning_path_templates.find_one({"_id": path_id})
    study = await db.learning_path_template_steps.find_one({
        "_id": resource["afterStepId"], "templateId": path_id, "kind": "survey",
        "archivedAt": None,
    })
    if not path or not study:
        raise RuntimeError("The graphical modeling path and final study questionnaire must exist.")
    if study["survey"]["surveyId"] != str(study_step.survey_id):
        raise RuntimeError("The weekly completion stations must reference the same questionnaire.")
    # Remove our own IDs so retries cannot duplicate either new station.
    step_ids = [
        identifier for identifier in path["stepIds"]
        if identifier not in {str(step.id), str(study_step.id)}
    ]
    if not step_ids or step_ids[-1] != study["_id"]:
        raise RuntimeError("The study questionnaire must be the last learning path station.")
    step_ids.extend([str(step.id), str(study_step.id)])

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
    documents = [
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
        *model_documents,
        (db.task_version, version["id"], version_fields, {}),
        (db.task, task["id"], task_fields, {}),
        (db.learning_path_template_steps, str(step.id), {
            **step_document(step, path_id), "archivedAt": None,
        }, {"updatedAt": now}),
        (db.learning_path_template_steps, str(study_step.id), {
            **step_document(study_step, path_id), "archivedAt": None,
        }, {"updatedAt": now}),
    ]
    for collection, identifier, fields, timestamps in documents:
        existing = await collection.find_one({"_id": identifier})
        if existing and any(existing.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Existing document {identifier} differs; refusing to overwrite it.")

    print(
        f"{'Add' if apply else 'Would add'}: {task['name']} with sample solution, "
        f"{len(checks)} synonym-check models, completion questionnaire and weekly completion station"
    )
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
