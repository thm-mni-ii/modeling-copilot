"""Idempotent seed data for a new Modeling Copilot database.

Fixed identifiers keep references stable and prevent duplicate seed records.
"""

import json
from datetime import datetime
from pathlib import Path

from modeling_api.db.client import db
from modeling_api.db.store import utcnow

# An empty owner marks global, read-only seed data.
SYSTEM_OWNER_ID = ""

UML_CLASS_DIAGRAM_ID = "a7fb2523-f7a0-4d23-b476-72882454b9e8"
UML_CLASS_DIAGRAM_VERSION_ID = "51cd9919-36b9-42d9-861d-8c619a2ac6d5"
UML_CLASS_DIAGRAM_NAME = "UML Class Diagram"

ERM_ID = "b20cd790-923c-4c79-b308-e154cdad331b"
ERM_VERSION_ID = "4dc5862b-2138-48dc-bf3a-c36dbe80dcb8"
ERM_NAME = "ERM"

SERM_ID = "a09ff8fb-5a26-4621-91e7-003cee10c555"
SERM_VERSION_ID = "6f4031c2-8fd1-402c-9a33-50deb8901496"
SERM_NAME = "SERM"

# Language identity, initial release and definition file of every seed language.
_SEED_LANGUAGES = (
    (UML_CLASS_DIAGRAM_ID, UML_CLASS_DIAGRAM_VERSION_ID, UML_CLASS_DIAGRAM_NAME, "uml_class_diagram.json"),
    (ERM_ID, ERM_VERSION_ID, ERM_NAME, "erm.json"),
    (SERM_ID, SERM_VERSION_ID, SERM_NAME, "serm.json"),
)

# Examples with tasks (<name>_tasks.json) and an optional shared sample solution (<name>_sample_solution.json).
_SEED_EXAMPLES = ("order_management", "order_processing", "course_planning")

_INITIAL_DATA_DIR = Path(__file__).with_name("initial_data")


def _load_initial_data(filename: str) -> dict:
    """Load one UTF-8 JSON seed definition."""
    return json.loads((_INITIAL_DATA_DIR / filename).read_text(encoding="utf-8"))


def _tasks(name: str) -> list[dict]:
    """Load all task identities and releases of one example."""
    payload = _load_initial_data(f"{name}_tasks.json")
    tasks = payload.get("tasks")
    if payload.get("schemaVersion") != 1 or not isinstance(tasks, list):
        raise ValueError(f"Unsupported {name} seed-data format.")
    return tasks


def _sample_solution(name: str) -> dict | None:
    """Load the shared sample model of one example and its release, if the example has one."""
    filename = f"{name}_sample_solution.json"
    if not (_INITIAL_DATA_DIR / filename).exists():
        return None
    payload = _load_initial_data(filename)
    model = payload.get("model")
    if payload.get("schemaVersion") != 1 or not isinstance(model, dict):
        raise ValueError(f"Unsupported {name} sample-solution format.")
    return model


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
                "data": _load_initial_data(filename),
            }
        },
        upsert=True,
    )


async def seed_initial_data() -> None:
    """Store fixed seed data for a new Modeling Copilot database."""
    created_at = utcnow()
    for language_id, version_id, name, filename in _SEED_LANGUAGES:
        await _seed_language(language_id, version_id, name, filename, created_at)

    for name in _SEED_EXAMPLES:
        await _seed_example(name, created_at)


async def _seed_example(name: str, created_at: datetime) -> None:
    """Store the sample solution (if any) and tasks of one example."""
    sample_model = _sample_solution(name)
    if sample_model is not None:
        await _seed_sample_solution(sample_model, created_at)

    for task in _tasks(name):
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
                "$set": {"name": task["name"]},
                "$setOnInsert": {"createdAt": created_at, **task_on_insert},
            },
            upsert=True,
        )
        await db.task_version.update_one(
            {"_id": version["id"]},
            {
                "$set": {
                    "releaseName": version["releaseName"],
                    "description": version["description"],
                    "data": version["data"],
                },
                "$setOnInsert": {"createdAt": created_at, **version_on_insert},
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
            "$set": {
                "name": sample_model["name"],
                "ownerId": sample_model["ownerId"],
            },
            "$setOnInsert": {
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
            "$set": {
                "releaseName": sample_version["releaseName"],
                "description": sample_version["description"],
                "data": sample_version["data"],
            },
            "$setOnInsert": {"createdAt": created_at, **model_version_on_insert},
        },
        upsert=True,
    )
