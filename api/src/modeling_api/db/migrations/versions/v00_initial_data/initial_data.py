"""Idempotent seed data for a new Modeling Copilot database.

Fixed identifiers keep references stable and prevent duplicate seed records.
The initial modeling-language releases and the entry learning path are public
by default. Tasks stay private in the catalog but remain accessible through
published learning paths.
Questionnaires have active releases for embedded use; their catalog remains
admin-only.
"""

from datetime import datetime
from uuid import UUID, uuid5

from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.db.help_questionnaires import HELP_SURVEY_IDS
from modeling_api.schemas.learning_paths import SaveTemplate
from modeling_api.schemas.surveys import Definition
from modeling_api.services.learning_path_store import step_document, template_meta
from modeling_api.db.migrations.versions.v00_initial_data.definitions import (
    SYSTEM_OWNER_ID, ENTRY_LEARNING_PATH_ID, MANIFEST,
    SEED_LANGUAGES, SEED_EXAMPLES, load_data, load_tasks, load_sample_solution,
)


async def _seed_learning_path(path_id, body, created_at):
    """Seed one template plus its step documents; never personal runs."""
    step_ids = [str(step.id) for step in body.steps]
    await db.learning_path_templates.update_one(
        {"_id": str(path_id)},
        {
            "$setOnInsert": {
                **template_meta(body, step_ids),
                "createdBy": SYSTEM_OWNER_ID,
                "revision": 1,
                "createdAt": created_at,
                "updatedAt": created_at,
            }
        },
        upsert=True,
    )
    for step in body.steps:
        await db.learning_path_template_steps.update_one(
            {"_id": str(step.id)},
            {
                "$setOnInsert": {
                    **step_document(step, path_id),
                    "archivedAt": None,
                    "createdAt": created_at,
                    "updatedAt": created_at,
                }
            },
            upsert=True,
        )


async def _seed_language(
    language_id: str, version_id: str, name: str, filename: str, created_at: datetime
) -> None:
    """Store one global language with its initial release unless it already exists."""
    await db.languages.update_one(
        {"_id": language_id},
        {
            "$setOnInsert": {
                "createdAt": created_at,
                "name": name,
                "parent": None,
                "ownerId": SYSTEM_OWNER_ID,
                "latestVersionId": version_id,
                "archivedAt": None,
            }
        },
        upsert=True,
    )
    await db.language_versions.update_one(
        {"_id": version_id},
        {
            "$setOnInsert": {
                "languageId": language_id,
                "versionNumber": "1.0",
                "createdBy": SYSTEM_OWNER_ID,
                "createdAt": created_at,
                "kind": "release",
                "releaseName": "Initial release",
                "description": None,
                "includedLanguageVersions": [],
                "data": load_data(filename),
            }
        },
        upsert=True,
    )


async def seed_initial_data() -> None:
    """Store fixed seed data for a new Modeling Copilot database."""
    created_at = utcnow()
    for phase, questionnaire in load_data("help_questionnaires.json").items():
        survey_id = HELP_SURVEY_IDS[phase]
        await _seed_survey(
            survey_id, str(uuid5(UUID(survey_id), "release:1")),
            questionnaire["title"],
            Definition.model_validate(questionnaire["definition"]).model_dump(exclude_none=True),
            created_at,
        )
    for language_id, version_id, name, filename in SEED_LANGUAGES:
        await _seed_language(language_id, version_id, name, filename, created_at)

    for name in SEED_EXAMPLES:
        await _seed_example(name, created_at)

    await _seed_example_learning_paths(created_at)
    await _seed_entry_learning_path(created_at)


async def _seed_questionnaire_release(survey_id, questionnaire, created_at, *, release_number=2):
    """Upgrade the original seed as a new immutable release, preserving admin edits."""
    previous_ids = {str(uuid5(UUID(survey_id), f"release:{number}")) for number in range(1, release_number)}
    version_id = str(uuid5(UUID(survey_id), f"release:{release_number}"))
    current = await db.surveys.find_one({"_id": survey_id})
    if current and (
        current.get("deletedAt") or "pending" in current
        or current["latestVersionId"] not in previous_ids
        or current.get("activeReleaseId") != current["latestVersionId"]
        or current["version"] >= release_number
    ):
        return
    definition = Definition.model_validate(questionnaire["definition"]).model_dump(exclude_none=True)
    await _seed_survey(
        survey_id, version_id, questionnaire["title"], definition, created_at,
        version_number=release_number,
    )
    if current:
        await db.surveys.update_one(
            {"_id": survey_id, "revision": current["revision"], "latestVersionId": current["latestVersionId"],
             "activeReleaseId": current["latestVersionId"], "pending": {"$exists": False}},
            {"$set": {
                "title": questionnaire["title"], "definition": definition,
                "version": release_number, "latestVersionId": version_id, "latestKind": "release",
                "activeReleaseId": version_id, "activeReleaseVersion": release_number,
                "updatedAt": created_at, "updatedBy": SYSTEM_OWNER_ID,
            }, "$inc": {"revision": 1}},
        )


async def _seed_entry_learning_path(created_at):
    """Publish the entry course configuration; never create learner runs."""
    config = MANIFEST["entryCourse"]
    for key in ("questionnaire", "completion"):
        survey = config[key]
        await _seed_questionnaire_release(
            survey["id"], load_data(survey["filename"]), created_at,
            release_number=survey["releaseNumber"],
        )
    survey = config["attitudes"]
    questionnaire = load_data(survey["filename"])
    await _seed_survey(
        survey["id"], str(uuid5(UUID(survey["id"]), "release:1")),
        questionnaire["title"],
        Definition.model_validate(questionnaire["definition"]).model_dump(exclude_none=True),
        created_at,
    )
    await _seed_static_surveys("entry_pulse_surveys.json", created_at)
    task_step_id = config["taskStepId"]
    serm_step_id = config["sermStepId"]
    attitudes_step_id = config["attitudesStepId"]
    template = next(template for template in load_data("learning_paths.json")["templates"]
                    if template["id"] == ENTRY_LEARNING_PATH_ID)
    body = SaveTemplate.model_validate(template["definition"])
    await _seed_learning_path(
        ENTRY_LEARNING_PATH_ID, body, created_at,
    )
    # Upgrade the original one-station seed exactly once. Later admin choices
    # (visibility, feature toggles and station edits) survive future restarts.
    while True:
        current = await db.learning_path_templates.find_one({"_id": ENTRY_LEARNING_PATH_ID})
        if current.get("entrySeedRevision", 0) >= 2:
            break
        # The task stays private in the catalog and is readable through its path.
        step_ids = [step_id for step_id in current["stepIds"] if step_id != task_step_id]
        step_ids.insert(min(1, len(step_ids)), task_step_id)
        meta = template_meta(body, step_ids)
        result = await db.learning_path_templates.update_one(
            {"_id": ENTRY_LEARNING_PATH_ID, "revision": current["revision"]},
            {"$set": {
                "stepIds": step_ids, "pulseSurveys": meta["pulseSurveys"],
                "helpRequests": meta["helpRequests"], "entrySeedRevision": 2,
                "updatedAt": created_at,
            }, "$inc": {"revision": 1}},
        )
        if result.matched_count:
            break

    # Append the independent questionnaire after the first task, without
    # reapplying revision 2's feature toggles or overwriting admin stations.
    while True:
        current = await db.learning_path_templates.find_one({"_id": ENTRY_LEARNING_PATH_ID})
        if current.get("entrySeedRevision", 0) >= 3:
            break
        step_ids = [step_id for step_id in current["stepIds"] if step_id != attitudes_step_id]
        position = step_ids.index(task_step_id) + 1
        step_ids.insert(position, attitudes_step_id)
        result = await db.learning_path_templates.update_one(
            {"_id": ENTRY_LEARNING_PATH_ID, "revision": current["revision"]},
            {"$set": {"stepIds": step_ids, "entrySeedRevision": 3, "updatedAt": created_at},
             "$inc": {"revision": 1}},
        )
        if result.matched_count:
            break


    # Preserve the existing questionnaire station ID (and its responses),
    # moving it after SERM rather than replacing it with the new task.
    while True:
        current = await db.learning_path_templates.find_one({"_id": ENTRY_LEARNING_PATH_ID})
        if current.get("entrySeedRevision", 0) >= 4:
            break
        step_ids = [step_id for step_id in current["stepIds"] if step_id not in (serm_step_id, attitudes_step_id)]
        position = step_ids.index(task_step_id) + 1
        step_ids[position:position] = [serm_step_id, attitudes_step_id]
        result = await db.learning_path_templates.update_one(
            {"_id": ENTRY_LEARNING_PATH_ID, "revision": current["revision"]},
            {"$set": {"stepIds": step_ids, "entrySeedRevision": 4, "updatedAt": created_at},
             "$inc": {"revision": 1}},
        )
        if result.matched_count:
            break


async def _seed_example(name: str, created_at: datetime) -> None:
    """Store the sample solution (if any) and tasks of one example."""
    sample_model = load_sample_solution(name)
    if sample_model is not None:
        await _seed_sample_solution(sample_model, created_at)

    for task in load_tasks(name):
        version = task["version"]
        task_on_insert = {
            key: value
            for key, value in task.items()
            if key not in {"id", "name", "version"}
        }
        version_on_insert = {
            key: value
            for key, value in version.items()
            if key not in {"id", "releaseName", "description", "data"}
        }

        await db.task.update_one(
            {"_id": task["id"]},
            {
                "$setOnInsert": {"name": task["name"], "createdAt": created_at, **task_on_insert},
            },
            upsert=True,
        )
        await db.task_version.update_one(
            {"_id": version["id"]},
            {
                # Existing models and task edits depend on this immutable release.
                "$setOnInsert": {
                    "releaseName": version["releaseName"],
                    "description": version["description"],
                    "data": version["data"],
                    "createdAt": created_at,
                    **version_on_insert,
                },
            },
            upsert=True,
        )


async def _seed_sample_solution(sample_model: dict, created_at: datetime) -> None:
    """Store the shared sample model of one example and its release."""
    sample_version = sample_model["version"]
    model_on_insert = {
        key: value
        for key, value in sample_model.items()
        if key not in {"id", "name", "ownerId", "version"}
    }
    model_version_on_insert = {
        key: value
        for key, value in sample_version.items()
        if key not in {"id", "releaseName", "description", "data"}
    }

    await db.models.update_one(
        {"_id": sample_model["id"]},
        {
            "$setOnInsert": {
                "name": sample_model["name"],
                "ownerId": sample_model["ownerId"],
                "createdAt": created_at,
                "updatedAt": created_at,
                **model_on_insert,
            },
        },
        upsert=True,
    )
    await db.model_versions.update_one(
        {"_id": sample_version["id"]},
        {
            "$setOnInsert": {
                "releaseName": sample_version["releaseName"],
                "description": sample_version["description"],
                "data": sample_version["data"],
                "createdAt": created_at,
                **model_version_on_insert,
            },
        },
        upsert=True,
    )


async def _seed_static_surveys(filename, created_at):
    for survey in load_data(filename)["surveys"]:
        await _seed_survey(
            survey["id"], survey["versionId"], survey["title"],
            Definition.model_validate(survey["definition"]).model_dump(exclude_none=True),
            created_at, version_number=survey["versionNumber"],
        )


async def _seed_example_learning_paths(created_at):
    """Load example content from JSON; never create personal learner runs."""
    await _seed_static_surveys("example_surveys.json", created_at)
    for template in load_data("learning_paths.json")["templates"]:
        if template["id"] != ENTRY_LEARNING_PATH_ID:
            await _seed_learning_path(
                template["id"], SaveTemplate.model_validate(template["definition"]), created_at,
            )


async def _seed_survey(survey_id, version_id, title, definition, created_at, *, version_number=1):
    version = {
        "_id": version_id,
        "surveyId": survey_id,
        "version": version_number,
        "title": title,
        "definition": definition,
        "kind": "release",
        "createdAt": created_at,
        "createdBy": SYSTEM_OWNER_ID,
        "releasedAt": created_at,
        "releasedBy": SYSTEM_OWNER_ID,
    }
    await db.survey_versions.update_one(
        {"_id": version_id}, {"$setOnInsert": version}, upsert=True
    )
    await db.surveys.update_one(
        {"_id": survey_id},
        {
            "$setOnInsert": {
                "title": title,
                "definition": definition,
                "version": version_number,
                "latestVersionId": version_id,
                "latestKind": "release",
                "activeReleaseId": version_id,
                "activeReleaseVersion": version_number,
                "revision": 1,
                "schemaVersion": 2,
                "deletedAt": None,
                "createdAt": created_at,
                "updatedAt": created_at,
                "createdBy": SYSTEM_OWNER_ID,
                "updatedBy": SYSTEM_OWNER_ID,
            }
        },
        upsert=True,
    )
