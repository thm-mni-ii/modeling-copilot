"""Initialize help limits and preserve previously delivered feedback usage."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import HelpRequestConfig
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
    missing = {"$or": [
        {"helpRequests.exampleLimit": {"$exists": False}},
        {"helpRequests.solutionLimit": {"$exists": False}},
    ]}
    templates = await db.learning_path_templates.count_documents(missing)
    requests = await db.learning_path_help_requests.count_documents({"$or": [
        {"helpConfig.exampleLimit": {"$exists": False}},
        {"helpConfig.solutionLimit": {"$exists": False}},
    ]})
    steps = await db.learning_path_run_steps.count_documents({"helpUsageInitialized": {"$ne": True}})
    print(f"{'Initialize' if apply else 'Would initialize'} help limits for {templates} paths, "
          f"{requests} requests and usage for {steps} run steps.")
    if not apply:
        return templates + requests + steps

    defaults = HelpRequestConfig()
    async for template in db.learning_path_templates.find(missing):
        config = template.get("helpRequests") or {}
        if not isinstance(config, dict):
            raise RuntimeError("Learning path help settings are invalid; fix them before migration.")
        config.setdefault("exampleLimit", defaults.example_limit)
        config.setdefault("solutionLimit", defaults.solution_limit)
        result = await db.learning_path_templates.update_one(
            {"_id": template["_id"], "revision": template["revision"]},
            {"$set": {"helpRequests": config, "updatedAt": utcnow()}, "$inc": {"revision": 1}},
        )
        if not result.matched_count:
            raise RuntimeError("Learning path changed during migration; retry with path writes stopped.")

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
    return templates + requests + steps
