"""Make every task private in the shared catalog."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration

MIGRATION_ID = "06_private_task_catalog"
PREREQUISITE = "05_task_edit_history"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await privatize_tasks(apply=False)
    return await run_migration(MIGRATION_ID, lambda: privatize_tasks(apply=True))


async def privatize_tasks(*, apply):
    query = {"visibility": {"$ne": "private"}}
    count = await db.task.count_documents(query)
    print(f"{'Make private' if apply else 'Would make private'} {count} task(s).")
    if apply and count:
        await db.task.update_many(query, {"$set": {"visibility": "private"}})
    return count
