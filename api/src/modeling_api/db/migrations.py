"""Explicit migration prerequisites and per-database execution records."""

from pymongo.errors import DuplicateKeyError

from modeling_api.db.client import db
from modeling_api.db.store import utcnow

BASELINE_ID = "00_initial_data"
LANGUAGE_UPGRADE_ID = "01_connection_rule_aliases"


async def require_completed(*migration_ids):
    for migration_id in migration_ids:
        record = await db.schema_migrations.find_one({"_id": migration_id})
        if not record or record.get("status") != "completed":
            raise RuntimeError(f"Migration {migration_id} must complete first; run the numbered scripts in api/scripts with --apply.")


async def run_migration(migration_id, action):
    """Serialize apply calls and allow idempotent actions to resume after errors."""
    previous = await db.schema_migrations.find_one({"_id": migration_id})
    if previous and previous.get("status") == "completed":
        print(f"{migration_id} already completed; skipping.")
        return 0
    lock = {"_id": migration_id, "status": "running", "startedAt": utcnow()}
    if previous and previous.get("status") == "failed":
        # Preserve initialization mode so a partially seeded new DB can resume.
        if "mode" in previous:
            lock["mode"] = previous["mode"]
        claimed = await db.schema_migrations.replace_one(
            {"_id": migration_id, "status": "failed"}, lock,
        )
        if not claimed.matched_count:
            raise RuntimeError("Migration state changed; rerun to check its status.")
    else:
        try:
            await db.schema_migrations.insert_one(lock)
        except DuplicateKeyError:
            raise RuntimeError("Migration already claimed; check schema_migrations before retrying.") from None
    try:
        changed = await action()
    except Exception:
        await db.schema_migrations.update_one(
            {"_id": migration_id}, {"$set": {"status": "failed", "failedAt": utcnow()}},
        )
        raise
    await db.schema_migrations.update_one(
        {"_id": migration_id},
        {"$set": {"status": "completed", "completedAt": utcnow(), "changedRecords": changed}},
    )
    return changed
