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
ORDER_MANAGEMENT_TASK_ID = "05813885-10a8-424e-b418-7029716e7a5e"
ORDER_MANAGEMENT_TASK_VERSION_ID = "428fb4fb-68c8-43c5-8c10-3b6698be39d2"

_INITIAL_DATA_DIR = Path(__file__).with_name("initial_data")

ORDER_MANAGEMENT_CONTENT = """<h2>Task: UML Class Diagram for Order Management</h2>
<p>A <span style="color: rgb(30, 136, 229);"><strong>Customer</strong></span> with a <span style="color: rgb(67, 160, 71);"><em>customerNumber</em></span> places <span style="color: rgb(30, 136, 229);"><strong>Orders</strong></span>, each identified by an <span style="color: rgb(67, 160, 71);"><em>orderNumber</em></span>. An <span style="color: rgb(30, 136, 229);"><strong>Order</strong></span> consists of at least one <span style="color: rgb(30, 136, 229);"><strong>Order Item</strong></span> with a <span style="color: rgb(67, 160, 71);"><em>quantity</em></span>.<br>
Each <span style="color: rgb(30, 136, 229);"><strong>Order Item</strong></span> refers to exactly one <span style="color: rgb(30, 136, 229);"><strong>Product</strong></span>, identified by a <span style="color: rgb(67, 160, 71);"><em>productNumber</em></span>. <span style="color: rgb(30, 136, 229);"><strong>Products</strong></span> implement the <span style="color: rgb(251, 140, 0);"><strong>Sellable</strong></span> interface.</p>"""


def _uml_class_diagram() -> dict:
    """Load the complete DiagramLanguage definition for the UML example."""
    return json.loads((_INITIAL_DATA_DIR / "uml_class_diagram.json").read_text(encoding="utf-8"))


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
    await db.task.update_one(
        {"_id": ORDER_MANAGEMENT_TASK_ID},
        {
            "$setOnInsert": {
                "createdAt": created_at,
                "name": "Order Management",
                "parent": None,
                "ownerId": SYSTEM_OWNER_ID,
                "latestVersionId": ORDER_MANAGEMENT_TASK_VERSION_ID,
                "latestReleaseId": ORDER_MANAGEMENT_TASK_VERSION_ID,
                "visibility": "published",
                "archivedAt": None,
            }
        },
        upsert=True,
    )
    await db.task_version.update_one(
        {"_id": ORDER_MANAGEMENT_TASK_VERSION_ID},
        {
            "$setOnInsert": {
                "taskId": ORDER_MANAGEMENT_TASK_ID,
                "versionNumber": "1.0",
                "createdBy": SYSTEM_OWNER_ID,
                "createdAt": created_at,
                "kind": "release",
                "releaseName": "Initial release",
                "description": None,
                "workspaceLanguages": [
                    {
                        "languageId": UML_CLASS_DIAGRAM_ID,
                        "versionId": UML_CLASS_DIAGRAM_VERSION_ID,
                        "source": "required",
                    }
                ],
                "data": {
                    "contentHtml": ORDER_MANAGEMENT_CONTENT,
                    "autonomyMode": "free",
                    "sampleSolutions": [],
                },
            }
        },
        upsert=True,
    )
