"""Reset validation text and complete syntax in every stored language version."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.services.language_definitions import normalize_syntax

MIGRATION_ID = "10_language_syntax_defaults"
PREREQUISITE = "09_submissions_feedback"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await migrate_versions(apply=False)
    return await run_migration(MIGRATION_ID, lambda: migrate_versions(apply=True))


async def migrate_versions(*, apply):
    changed = 0
    # Include releases, checkpoints, archived languages and pinned dependencies.
    async for version in db.language_versions.find({}):
        data = normalize_syntax(version["data"], reset_templates=True)
        if data == version["data"]:
            continue
        print(f'{"Normalize" if apply else "Would normalize"}: language version {version["_id"]}')
        if apply:
            result = await db.language_versions.update_one(
                {"_id": version["_id"], "data": version["data"]},
                {"$set": {"data": data}},
            )
            if not result.matched_count:
                raise RuntimeError(
                    f'Language version {version["_id"]} changed during migration; stop language writes before retrying.'
                )
        changed += 1
    return changed
