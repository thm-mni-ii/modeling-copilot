"""Idempotent seed data for a new Modeling Copilot database.

Fixed identifiers keep references stable and prevent duplicate seed records.
"""

import json
from pathlib import Path
from uuid import UUID, uuid5

from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import SaveTemplate
from modeling_api.services.learning_path_store import step_document, template_meta
from modeling_api.schemas.surveys import Definition

# An empty owner marks global, read-only seed data.
SYSTEM_OWNER_ID = ""

UML_CLASS_DIAGRAM_ID = "a7fb2523-f7a0-4d23-b476-72882454b9e8"
UML_CLASS_DIAGRAM_VERSION_ID = "51cd9919-36b9-42d9-861d-8c619a2ac6d5"
UML_CLASS_DIAGRAM_NAME = "UML Class Diagram"
ORDER_MANAGEMENT_LEARNING_PATH_ID = "5eff2fa9-17c4-4bd5-b44e-fc98bc05f325"

_INITIAL_DATA_DIR = Path(__file__).with_name("initial_data")


def _load_initial_data(filename: str) -> dict:
    """Load one UTF-8 JSON seed definition."""
    return json.loads((_INITIAL_DATA_DIR / filename).read_text(encoding="utf-8"))


def _uml_class_diagram() -> dict:
    """Load the complete DiagramLanguage definition for the UML example."""
    return _load_initial_data("uml_class_diagram.json")


def _order_management_tasks() -> list[dict]:
    """Load all Order Management task identities and releases."""
    payload = _load_initial_data("order_management_tasks.json")
    tasks = payload.get("tasks")
    if payload.get("schemaVersion") != 1 or not isinstance(tasks, list):
        raise ValueError("Unsupported Order Management seed-data format.")
    return tasks


def _order_management_sample_solution() -> dict:
    """Load the shared Order Management sample model and its release."""
    payload = _load_initial_data("order_management_sample_solution.json")
    model = payload.get("model")
    if payload.get("schemaVersion") != 1 or not isinstance(model, dict):
        raise ValueError("Unsupported Order Management sample-solution format.")
    return model


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


async def seed_initial_data() -> None:
    """Store fixed seed data for a new Modeling Copilot database."""
    created_at = utcnow()
    language_data = _uml_class_diagram()

    await db.languages.update_one(
        {"_id": UML_CLASS_DIAGRAM_ID},
        {
            "$setOnInsert": {
                "createdAt": created_at,
                "name": UML_CLASS_DIAGRAM_NAME,
                "parent": None,
                "ownerId": SYSTEM_OWNER_ID,
                "latestVersionId": UML_CLASS_DIAGRAM_VERSION_ID,
                "archivedAt": None,
            }
        },
        upsert=True,
    )
    await db.language_versions.update_one(
        {"_id": UML_CLASS_DIAGRAM_VERSION_ID},
        {
            "$setOnInsert": {
                "languageId": UML_CLASS_DIAGRAM_ID,
                "versionNumber": "1.0",
                "createdBy": SYSTEM_OWNER_ID,
                "createdAt": created_at,
                "kind": "release",
                "releaseName": "Initial release",
                "description": None,
                "includedLanguageVersions": [],
                "data": language_data,
            }
        },
        upsert=True,
    )

    sample_model = _order_management_sample_solution()
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
                "createdAt": created_at,
                **model_version_on_insert,
                "releaseName": sample_version["releaseName"],
                "description": sample_version["description"],
                "data": sample_version["data"],
            },
        },
        upsert=True,
    )

    tasks = _order_management_tasks()
    for task in tasks:
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
                "$setOnInsert": {
                    "createdAt": created_at,
                    "name": task["name"],
                    **task_on_insert,
                },
            },
            upsert=True,
        )
        await db.task_version.update_one(
            {"_id": version["id"]},
            {
                "$setOnInsert": {
                    "createdAt": created_at,
                    **version_on_insert,
                    "releaseName": version["releaseName"],
                    "description": version["description"],
                    "data": version["data"],
                },
            },
            upsert=True,
        )

    challenges = [
        {
            "type": "solo",
            "title": "Solo Challenge",
            "description": "Start by modeling independently and see how far you can get without support. Help remains available at any time.",
            "icon": "mdi-account-outline",
            "color": "#356458",
        },
        {
            "type": "time",
            "title": "Time Challenge",
            "description": "Try to get as far as you can in 15 minutes. The timer keeps running when you switch tabs. You can continue working after time runs out.",
            "icon": "mdi-timer-outline",
            "color": "#93691d",
            "durationSeconds": 900,
        },
        {
            "type": "help_budget",
            "title": "Help Budget Challenge",
            "description": "Try to use no more than three internal hints. Additional help remains available at any time.",
            "icon": "mdi-lightbulb-outline",
            "color": "#536b94",
            "helpBudget": 3,
        },
    ]
    steps = []
    for index, task in enumerate(tasks * 2):
        repeated = index >= len(tasks)
        steps.append(
            {
                "id": str(
                    uuid5(
                        UUID(ORDER_MANAGEMENT_LEARNING_PATH_ID),
                        f"{task['id']}:repeat" if repeated else task["id"],
                    )
                ),
                "title": f"{task['name']} · Review" if repeated else task["name"],
                "taskVersion": {
                    "taskId": task["id"],
                    "versionId": task["version"]["id"],
                },
                "unlock": {"mode": "sequence", "conditions": []},
                "challenge": challenges[index] if index < len(challenges) else None,
            }
        )
    # Seed configuration only. Personal step runs, challenge timestamps and model
    # references are created by start_step, never during database initialization.
    await _seed_learning_path(
        ORDER_MANAGEMENT_LEARNING_PATH_ID,
        SaveTemplate(
            name="Order Management",
            description="Six practice stations: three Order Management tasks with one challenge each, followed by the same tasks for review. Complete each station to unlock the next.",
            published=True,
            archived=False,
            steps=steps,
        ),
        created_at,
    )

    await seed_survey_learning_path(tasks, created_at)
    await seed_pulse_learning_path(tasks, created_at)


async def seed_survey_learning_path(tasks, created_at):
    """Example content only: never create personal runs, instances or answers."""
    path_id = uuid5(UUID(ORDER_MANAGEMENT_LEARNING_PATH_ID), "survey-example")
    steps = []
    survey_titles = [
        "Start questionnaire",
        "Reflection on task 1",
        "Closing questionnaire",
    ]
    survey_questions = [
        "How familiar are you with class diagrams?",
        "How clear was the modeling task?",
        "How helpful was this learning path?",
    ]
    references = []
    for index, title in enumerate(survey_titles):
        survey_id = str(uuid5(path_id, f"survey:{index}"))
        version_id = str(uuid5(path_id, f"release:{index}"))
        definition = Definition.model_validate(
            {
                "elements": [
                    {
                        "type": "rating",
                        "name": "experience",
                        "title": survey_questions[index],
                        "isRequired": True,
                        "rateMin": 1,
                        "rateMax": 5,
                    },
                    {
                        "type": "comment",
                        "name": "comment",
                        "title": "Additional comments (optional)",
                    },
                ]
            }
        ).model_dump(exclude_none=True)
        demo_title = f"Example: {title} (demonstration only)"
        await _seed_survey(survey_id, version_id, demo_title, definition, created_at)
        references.append((survey_id, version_id))
    for index in range(5):
        is_survey = index % 2 == 0
        step = {
            "id": str(uuid5(path_id, f"activity:{index}")),
            "type": "survey" if is_survey else "task",
            "title": (
                survey_titles[index // 2]
                if is_survey
                else f"Task {index // 2 + 1}: {tasks[index // 2]['name']}"
            ),
            "required": index != 4,
            "unlock": {"mode": "sequence", "conditions": []},
        }
        if is_survey:
            step.update(
                surveyId=references[index // 2][0],
            )
        else:
            task = tasks[index // 2]
            step["beforeSurveyId"] = references[0][0]
            step["afterSurveyId"] = references[1][0]
            step["taskVersion"] = {
                "taskId": task["id"],
                "versionId": task["version"]["id"],
            }
        steps.append(step)
    await _seed_learning_path(
        path_id,
        SaveTemplate(
            name="Example: Modeling with questionnaires",
            description="Demonstration data, not validated research instruments. Standalone questionnaires and two modeling tasks with required questionnaires before and after each task.",
            published=True,
            steps=steps,
        ),
        created_at,
    )


async def _seed_survey(survey_id, version_id, title, definition, created_at):
    version = {
        "_id": version_id,
        "surveyId": survey_id,
        "version": 1,
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
                "version": 1,
                "latestVersionId": version_id,
                "latestKind": "release",
                "activeReleaseId": version_id,
                "activeReleaseVersion": 1,
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


LIKERT_UNSURE = "Kann ich gerade nicht einschätzen"


def _pulse_definition(name, title, high):
    return Definition.model_validate({
        "elements": [{
            "type": "radiogroup", "name": name, "title": title, "isRequired": True,
            "choices": ["1 – gar nicht", "2", "3", "4", f"5 – {high}", LIKERT_UNSURE],
        }]
    }).model_dump(exclude_none=True)


async def seed_pulse_learning_path(tasks, created_at):
    namespace = UUID(ORDER_MANAGEMENT_LEARNING_PATH_ID)
    survey_ids = []
    for name, title, high in (
        ("random_understand", "Wie gut verstehst du gerade, was du bei dieser Aufgabe tun sollst?", "sehr gut"),
        ("random_need", "Wie stark brauchst du gerade Unterstützung, um diese Aufgabe zu bearbeiten?", "sehr stark"),
    ):
        survey_id = uuid5(namespace, f"pulse:{name}")
        survey_ids.append(str(survey_id))
        await _seed_survey(
            str(survey_id), str(uuid5(survey_id, "release:1")),
            f"Example: {name.upper()} (demonstration only)",
            _pulse_definition(name, title, high), created_at,
        )
    path_id = uuid5(namespace, "pulse-example")
    await _seed_learning_path(
        path_id,
        SaveTemplate(
            name="Example: Modeling with random pulse questions",
            description="Demonstration tasks with optional random pulse questionnaires during active modeling.",
            published=True,
            steps=[
                {
                    "id": str(uuid5(path_id, f"task:{index}")), "title": task["name"],
                    "taskVersion": {"taskId": task["id"], "versionId": task["version"]["id"]},
                }
                for index, task in enumerate(tasks[:3])
            ],
            pulseSurveys={
                "enabled": True, "surveyIds": survey_ids, "minGapSeconds": 600,
                "maxGapSeconds": 1800, "maxPerSession": 3, "maxPerTask": None,
                "minActiveSeconds": 120, "excludeStepIds": [],
            },
        ),
        created_at,
    )
