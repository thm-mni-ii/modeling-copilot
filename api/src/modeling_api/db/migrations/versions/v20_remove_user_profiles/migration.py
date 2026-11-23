"""Remove identity profiles while preserving IDs and application activity."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration

MIGRATION_ID = "20_remove_user_profiles"
PREREQUISITE = "19_initialize_dashboard"
RETAINED_FIELDS = ("_id", "firstSeenAt", "lastSeenAt", "isStaff")


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await sanitize(apply=False)
    return await run_migration(MIGRATION_ID, lambda: sanitize(apply=True))


async def sanitize(*, apply):
    count = await db.submission_users.count_documents({})
    print(f"{'Sanitize' if apply else 'Would sanitize'} {count} user directory entries; "
          "retain only IDs, firstSeenAt, lastSeenAt and isStaff.")
    if not apply:
        return count
    # An inclusion projection also removes unknown historical profile fields.
    result = await db.submission_users.update_many(
        {}, [{"$project": {field: 1 for field in RETAINED_FIELDS}}],
    )
    return result.modified_count
