"""Idempotent seed data for a new Modeling Copilot database.

Fixed identifiers keep references stable and prevent duplicate seed records.
"""

import json
from pathlib import Path

from modeling_api.db.client import db
from modeling_api.db.store import utcnow

# An empty owner marks global, read-only seed data.
SYSTEM_OWNER_ID = ""

UML_CLASS_DIAGRAM_ID = "a7fb2523-f7a0-4d23-b476-72882454b9e8"
UML_CLASS_DIAGRAM_VERSION_ID = "51cd9919-36b9-42d9-861d-8c619a2ac6d5"
UML_CLASS_DIAGRAM_NAME = "UML Class Diagram"

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

    for task in _order_management_tasks():
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
