"""Add activity indexes without changing historical model data."""

from modeling_api.db.client import create_activity_indexes, db
from modeling_api.db.migrations import require_completed, run_migration

MIGRATION_ID = "07_model_activity_tracking"
PREREQUISITE = "06_private_task_catalog"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        print("Would create activity session and interaction indexes; no historical data is generated.")
        return 0
    return await run_migration(MIGRATION_ID, initialize)


async def initialize():
    await create_activity_indexes()
    return 0
