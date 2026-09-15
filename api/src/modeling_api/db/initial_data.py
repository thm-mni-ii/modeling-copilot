"""Idempotente Startdaten für eine neue Modeling-Copilot-Datenbank.

Die IDs sind absichtlich fest vergeben.  So wird beim erneuten API-Start kein
zweiter Satz erzeugt und Referenzen auf die Startdaten bleiben stabil.
"""

import json
from pathlib import Path

from modeling_api.db.client import db
from modeling_api.db.store import utcnow

# Initialdaten gehören keinem konkreten Nutzer.  Ein leerer Besitzer markiert
# sie als globalen, schreibgeschützten Startbestand.
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
    """Lädt die vollständige DiagramLanguage-Definition des UML-Beispiels."""
    return json.loads((_INITIAL_DATA_DIR / "uml_class_diagram.json").read_text(encoding="utf-8"))


async def seed_initial_data() -> None:
    """Speichert Startdaten und führt kleine, idempotente Metadatenmigrationen aus."""
    created_at = utcnow()
    language_data = _uml_class_diagram()

    # One-time, idempotent migration of the previous API vocabulary.
    for collection in (
        db.language_versions,
        db.model_versions,
        db.task_statement_versions,
    ):
        await collection.update_many(
            {"versionName": {"$exists": True}, "releaseName": {"$exists": False}},
            {"$rename": {"versionName": "releaseName"}},
        )
        await collection.update_many(
            {"versionName": {"$exists": True}}, {"$unset": {"versionName": ""}}
        )
    await db.language_versions.update_many({"kind": "named"}, {"$set": {"kind": "release"}})
    await db.model_versions.update_many({"kind": "named"}, {"$set": {"kind": "release"}})
    await db.model_versions.update_many({}, {"$unset": {"languageVersions": ""}})
    await db.model_versions.update_many({}, {"$unset": {"previousVersionId": ""}})
    await db.languages.update_many(
        {"archivedAt": {"$exists": False}}, {"$set": {"archivedAt": None}}
    )

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
    # Keep the fixed, global example compatible with the current editor data
    # interface. User-created language versions are never touched.
    await db.language_versions.update_one(
        {
            "_id": UML_CLASS_DIAGRAM_VERSION_ID,
            "languageId": UML_CLASS_DIAGRAM_ID,
        },
        {
            "$set": {
                "kind": "release",
                "releaseName": "Initial release",
                "versionNumber": "1.0",
                "description": None,
                "data.feedback": language_data["feedback"],
            },
            "$unset": {"versionName": "", "data.id": "", "data.name": "", "data.tags": ""},
        },
    )

    await db.task_statements.update_one(
        {"_id": ORDER_MANAGEMENT_TASK_ID},
        {
            "$setOnInsert": {
                "createdAt": created_at,
                "source": "initial-data",
                "externalTaskId": "order-management",
                "ownerId": SYSTEM_OWNER_ID,
                "latestVersionId": ORDER_MANAGEMENT_TASK_VERSION_ID,
            }
        },
        upsert=True,
    )
    await db.task_statement_versions.update_one(
        {"_id": ORDER_MANAGEMENT_TASK_VERSION_ID},
        {
            "$setOnInsert": {
                "taskStatementId": ORDER_MANAGEMENT_TASK_ID,
                "versionNumber": "1.0",
                "createdBy": SYSTEM_OWNER_ID,
                "createdAt": created_at,
                "releaseName": "Initial release",
                "externalVersionId": "1",
                "data": {
                    "title": "A3 – Order Management",
                    "content": ORDER_MANAGEMENT_CONTENT,
                },
            }
        },
        upsert=True,
    )
    await db.task_statement_versions.update_one(
        {"_id": ORDER_MANAGEMENT_TASK_VERSION_ID},
        {
            "$set": {"releaseName": "Initial release", "versionNumber": "1.0"},
            "$unset": {"versionName": ""},
        },
    )
