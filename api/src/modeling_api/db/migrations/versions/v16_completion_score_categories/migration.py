"""Add the completion score scope to task steps; the laboratory task requires 50 % in every category."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.store import utcnow

MIGRATION_ID = "16_completion_score_categories"
PREREQUISITE = "15_laboratory_synonym_models"
LABORATORY_STEP_ID = "90633637-a890-597e-bfc6-682ed472b020"
LABORATORY_MINIMUM = 50


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await migrate_steps(apply=False)
    return await run_migration(MIGRATION_ID, lambda: migrate_steps(apply=True))


async def migrate_steps(*, apply):
    query = {"kind": "task", "task.scoreScope": {"$exists": False}}
    count = await db.learning_path_template_steps.count_documents(query)
    print(f"{'Initialize' if apply else 'Would initialize'} the overall score scope for {count} task steps.")
    if apply:
        await db.learning_path_template_steps.update_many(
            query, {"$set": {"task.scoreScope": "overall", "task.categoryMinimums": []}}
        )
    step = await db.learning_path_template_steps.find_one({"_id": LABORATORY_STEP_ID, "kind": "task"})
    if step is None:
        print("Laboratory step not found; no per-category requirement set.")
        return count
    print(f"{'Require' if apply else 'Would require'} {LABORATORY_MINIMUM} % in every category for the laboratory task.")
    if apply:
        path = await db.learning_path_templates.find_one({"_id": step["templateId"]})
        if path is None:
            raise RuntimeError("The laboratory step's learning path is missing.")
        await db.learning_path_template_steps.update_one(
            {"_id": LABORATORY_STEP_ID},
            {"$set": {"task.minimumScorePercent": LABORATORY_MINIMUM, "task.scoreScope": "eachCategory",
                      "task.categoryMinimums": [], "updatedAt": utcnow()}},
        )
        # Open editor drafts must reload instead of overwriting the new requirement.
        result = await db.learning_path_templates.update_one(
            {"_id": path["_id"], "revision": path["revision"]},
            {"$inc": {"revision": 1}, "$set": {"updatedAt": utcnow()}},
        )
        if not result.matched_count:
            raise RuntimeError("The learning path changed during migration. Retry with path writes stopped.")
    return count + 1
