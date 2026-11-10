"""Initialize additive submission storage without rewriting existing user data."""

from pymongo.errors import CollectionInvalid, OperationFailure

from modeling_api.db.client import create_submission_indexes, db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow

MIGRATION_ID = "09_submissions_feedback"
PREREQUISITE = "08_public_case_studies"
COLLECTIONS = (
    "submission_assignments",
    "submission_runs",
    "submission_participants",
    "submissions",
    "submission_reviews",
    "submission_publications",
    "submission_resolutions",
    "submission_settings",
    "submission_users",
)


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        existing = set(await db.list_collection_names())
        settings = await db.submission_settings.find_one(
            {"_id": "feedback"}, {"_id": 1}
        )
        print(
            f"Would create {len(set(COLLECTIONS) - existing)} submission collection(s) and ensure submission indexes."
        )
        print(
            "Existing global feedback settings would be preserved."
            if settings
            else "Would initialize global feedback settings at revision 1; built-in revision 0 remains available."
        )
        print(
            "Models, languages, submissions, publications and historical peer data are not rewritten or deleted."
        )
        return int(settings is None)
    return await run_migration(MIGRATION_ID, initialize)


async def initialize():
    existing = set(await db.list_collection_names())
    for name in COLLECTIONS:
        if name in existing:
            continue
        try:
            await db.create_collection(name)
        except CollectionInvalid:
            # Another startup may already have created the collection via an index.
            if name not in await db.list_collection_names():
                raise
        except OperationFailure as error:
            if error.code != 48:  # NamespaceExists during concurrent creation.
                raise
    await create_submission_indexes()
    overlays = load_data(MIGRATION_ID, "feedback_defaults.json")
    legacy_overlays = load_data(MIGRATION_ID, "feedback_legacy_defaults.json")
    now = utcnow()
    result = await db.submission_settings.update_one(
        {"_id": "feedback"},
        {
            "$setOnInsert": {
                "revision": 1,
                "overlays": overlays,
                "history": [{"revision": 0, "overlays": legacy_overlays}],
                "createdAt": now,
                "updatedAt": now,
                "updatedBy": MIGRATION_ID,
            }
        },
        upsert=True,
    )
    return int(result.upserted_id is not None)
