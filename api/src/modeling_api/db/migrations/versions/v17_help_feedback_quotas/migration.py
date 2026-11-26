"""Initialize help limits and preserve previously delivered feedback usage."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.schemas.learning_paths import TaskHelpFeedbackConfig
from modeling_api.services.help_requests import usage

MIGRATION_ID = "17_help_feedback_quotas"
PREREQUISITE = "16_completion_score_categories"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await initialize(apply=False)
    return await run_migration(MIGRATION_ID, lambda: initialize(apply=True))


async def initialize(*, apply):
    requests = await db.learning_path_help_requests.count_documents({"$or": [
        {"helpConfig.exampleLimit": {"$exists": False}},
        {"helpConfig.solutionLimit": {"$exists": False}},
    ]})
    steps = await db.learning_path_run_steps.count_documents({"helpUsageInitialized": {"$ne": True}})
    print(f"{'Initialize' if apply else 'Would initialize'} help limits for "
          f"{requests} requests and usage for {steps} run steps.")
    if not apply:
        return requests + steps

    defaults = TaskHelpFeedbackConfig()

    await db.learning_path_help_requests.update_many(
        {"helpConfig": None},
        {"$set": {"helpConfig": {}}},
    )
    for field, value in (("exampleLimit", defaults.example_limit), ("solutionLimit", defaults.solution_limit)):
        await db.learning_path_help_requests.update_many(
            {f"helpConfig.{field}": {"$exists": False}},
            {"$set": {f"helpConfig.{field}": value}},
        )
    async for state in db.learning_path_run_steps.find({"helpUsageInitialized": {"$ne": True}}):
        await usage(state["runId"], state["stepId"], defaults)
    return requests + steps
