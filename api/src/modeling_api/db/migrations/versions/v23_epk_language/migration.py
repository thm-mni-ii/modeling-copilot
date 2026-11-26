"""Publish EPK as a global language; existing languages stay untouched."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.migrations.versions.v00_initial_data.definitions import SYSTEM_OWNER_ID
from modeling_api.db.store import utcnow
from modeling_api.schemas.languages import CreateLanguageVersion

MIGRATION_ID = "23_epk_language"
PREREQUISITE = "22_help_choice_labels"
LANGUAGE_ID = "2a611b6a-bd2a-4b08-a503-154920b428d9"
VERSION_ID = "e90bc975-7d92-46b5-b81f-6e4b03e27fec"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await publish(apply=False)
    return await run_migration(MIGRATION_ID, lambda: publish(apply=True))


async def publish(*, apply):
    data = load_data(MIGRATION_ID, "epk.json")
    # Ungültige Seed-Daten sollen hier auffallen und nicht erst im Editor
    CreateLanguageVersion.model_validate({"baseVersionId": None, "kind": "release", "data": data})
    if await db.languages.find_one({"_id": LANGUAGE_ID}):
        print("EPK already exists; nothing to publish.")
        return 0
    print(f'{"Publish" if apply else "Would publish"}: EPK release 1.0')
    if not apply:
        return 1
    created_at = utcnow()
    await db.language_versions.update_one(
        {"_id": VERSION_ID},
        {"$setOnInsert": {
            "languageId": LANGUAGE_ID, "versionNumber": "1.0",
            "createdBy": SYSTEM_OWNER_ID, "createdAt": created_at,
            "kind": "release", "releaseName": "Initial release", "description": None,
            "includedLanguageVersions": [], "data": data,
        }},
        upsert=True,
    )
    await db.languages.update_one(
        {"_id": LANGUAGE_ID},
        {"$setOnInsert": {
            "createdAt": created_at, "name": "EPK", "parent": None,
            "ownerId": SYSTEM_OWNER_ID, "latestVersionId": VERSION_ID, "archivedAt": None,
        }},
        upsert=True,
    )
    return 1
