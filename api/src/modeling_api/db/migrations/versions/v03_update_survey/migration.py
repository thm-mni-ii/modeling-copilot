"""Separate task completion from the final study questionnaire."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import LearningPathStep
from modeling_api.schemas.surveys import Definition
from modeling_api.services.learning_path_store import step_document

MIGRATION_ID = "03_update_survey"
PREREQUISITE = "02_seminar_management"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await update_surveys(apply=False)
    return await run_migration(MIGRATION_ID, lambda: update_surveys(apply=True))


async def update_surveys(*, apply):
    resource = load_data(MIGRATION_ID, "completion_surveys.json")
    path_id = resource["learningPathId"]
    path = await db.learning_path_templates.find_one({"_id": path_id})
    seminar = await db.learning_path_template_steps.find_one({
        "_id": resource["seminarStepId"], "templateId": path_id, "kind": "task",
    })
    if not path or not seminar or seminar["_id"] not in path["stepIds"]:
        raise RuntimeError("The graphical modeling path and seminar station must exist.")
    if seminar["task"].get("afterSurveyId") not in (
        "a4d7b24f-d026-5132-bcf0-184014c82719", resource["seminarCompletionSurveyId"],
    ):
        raise RuntimeError("The seminar completion was edited; refusing to replace it.")

    now = utcnow()
    releases = []
    for survey in resource["surveys"]:
        definition = Definition.model_validate(survey["definition"]).model_dump(exclude_none=True)
        fields = {
            "surveyId": survey["id"], "version": survey["version"],
            "title": survey["title"], "definition": definition, "kind": "release",
        }
        existing = await db.survey_versions.find_one({"_id": survey["versionId"]})
        if existing and any(existing.get(k) != v for k, v in fields.items()):
            raise RuntimeError(f"Survey release {survey['versionId']} conflicts with the migration.")
        current = await db.surveys.find_one({"_id": survey["id"]})
        allowed = {survey["versionId"], survey.get("previousVersionId")}
        if current and (
            current.get("latestVersionId") not in allowed
            or current.get("activeReleaseId") not in allowed
            or current.get("pending") is not None or current.get("deletedAt") is not None
        ):
            raise RuntimeError(f"Survey {survey['id']} was edited; refusing to replace it.")
        releases.append((survey, fields, current))

    step = LearningPathStep.model_validate(resource["studyStep"])
    step_fields = {**step_document(step, path_id), "archivedAt": None}
    existing_step = await db.learning_path_template_steps.find_one({"_id": str(step.id)})
    if existing_step and any(existing_step.get(k) != v for k, v in step_fields.items()):
        raise RuntimeError("The study questionnaire station conflicts with the migration.")

    print(f"{'Publish' if apply else 'Would publish'}: two task completions and final study questionnaire")
    if not apply:
        return len(releases)

    for survey, fields, current in releases:
        await db.survey_versions.update_one(
            {"_id": survey["versionId"]},
            {"$setOnInsert": {**fields, "createdAt": now, "createdBy": "",
                              "releasedAt": now, "releasedBy": ""}}, upsert=True,
        )
        metadata = {
            "title": fields["title"], "definition": fields["definition"],
            "version": survey["version"], "latestVersionId": survey["versionId"],
            "latestKind": "release", "activeReleaseId": survey["versionId"],
            "activeReleaseVersion": survey["version"], "updatedAt": now, "updatedBy": "",
        }
        if current is None:
            await db.surveys.update_one(
                {"_id": survey["id"]}, {"$setOnInsert": {
                    **metadata, "revision": 1, "schemaVersion": 2, "deletedAt": None,
                    "createdAt": now, "createdBy": "",
                }}, upsert=True,
            )
        elif current.get("activeReleaseId") != survey["versionId"]:
            result = await db.surveys.update_one(
                {"_id": survey["id"], "revision": current["revision"],
                 "latestVersionId": current["latestVersionId"],
                 "activeReleaseId": current["activeReleaseId"]},
                {"$set": metadata, "$inc": {"revision": 1}},
            )
            if not result.matched_count:
                raise RuntimeError("Questionnaire changed during migration; rerun after stopping edits.")

    await db.learning_path_template_steps.update_one(
        {"_id": str(step.id)},
        {"$setOnInsert": {**step_fields, "createdAt": now, "updatedAt": now}}, upsert=True,
    )
    if seminar["task"].get("afterSurveyId") != resource["seminarCompletionSurveyId"]:
        result = await db.learning_path_template_steps.update_one(
            {"_id": seminar["_id"], "task": seminar["task"]},
            {"$set": {"task.afterSurveyId": resource["seminarCompletionSurveyId"], "updatedAt": now}},
        )
        if not result.matched_count:
            raise RuntimeError("Seminar station changed during migration; rerun after stopping edits.")
    step_ids = list(path["stepIds"])
    if str(step.id) not in step_ids:
        step_ids.insert(step_ids.index(seminar["_id"]) + 1, str(step.id))
    if step_ids != path["stepIds"] or seminar["task"].get("afterSurveyId") != resource["seminarCompletionSurveyId"]:
        result = await db.learning_path_templates.update_one(
            {"_id": path_id, "revision": path["revision"], "stepIds": path["stepIds"]},
            {"$set": {"stepIds": step_ids, "updatedAt": now}, "$inc": {"revision": 1}},
        )
        if not result.matched_count:
            raise RuntimeError("Learning path changed during migration; rerun after stopping edits.")
    return len(releases)
