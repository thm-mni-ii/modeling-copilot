"""Move path-wide feedback limits to task stations without replacing overrides."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import HelpRequestConfig, TaskHelpFeedbackConfig

MIGRATION_ID = "21_task_help_feedback"
PREREQUISITE = "20_remove_user_profiles"
LEGACY_LIMIT_FIELDS = ("exampleLimit", "solutionLimit")


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await migrate_limits(apply=False)
    return await run_migration(MIGRATION_ID, lambda: migrate_limits(apply=True))


async def migrate_limits(*, apply):
    pending = []
    query = {"$or": [{f"helpRequests.{field}": {"$exists": True}} for field in LEGACY_LIMIT_FIELDS]}
    # Validate all affected settings before the first write, including archived stations.
    async for template in db.learning_path_templates.find(query):
        config = template["helpRequests"]
        limits = {field: config[field] for field in LEGACY_LIMIT_FIELDS if field in config}
        TaskHelpFeedbackConfig.model_validate(limits)
        HelpRequestConfig.model_validate({key: value for key, value in config.items() if key not in limits})
        steps = []
        async for step in db.learning_path_template_steps.find({"templateId": template["_id"], "kind": "task"}):
            # Path saves reject feedback limits on releases without sample solutions; those stations offer no automatic feedback.
            release = await db.task_version.find_one(
                {"_id": step["task"].get("releaseId"), "taskId": step["task"].get("taskId"), "kind": "release"},
                {"data.sampleSolutions": 1})
            if not (release or {}).get("data", {}).get("sampleSolutions"):
                continue
            feedback = step["task"].get("helpFeedback") or {}
            merged = {**limits, **feedback}
            TaskHelpFeedbackConfig.model_validate(merged)
            if merged != feedback:
                steps.append((step, merged))
        pending.append((template, steps))

    count = len(pending) + sum(len(steps) for _, steps in pending)
    print(f"{'Move' if apply else 'Would move'} path-wide feedback limits for {len(pending)} paths; "
          f"update {count - len(pending)} task stations and preserve explicit station limits.")
    if not apply:
        return count

    now = utcnow()
    for template, steps in pending:
        # Retain the source limits until all stations are copied so interrupted runs can resume.
        for step, feedback in steps:
            result = await db.learning_path_template_steps.update_one(
                {"_id": step["_id"], "templateId": template["_id"], "kind": "task", "task": step["task"]},
                {"$set": {"task.helpFeedback": feedback, "updatedAt": now}},
            )
            if not result.matched_count:
                raise RuntimeError("Task station changed during migration; retry with path writes stopped.")
        result = await db.learning_path_templates.update_one(
            {"_id": template["_id"], "revision": template["revision"], "helpRequests": template["helpRequests"]},
            {"$unset": {f"helpRequests.{field}": "" for field in LEGACY_LIMIT_FIELDS},
             "$set": {"updatedAt": now}, "$inc": {"revision": 1}},
        )
        if not result.matched_count:
            raise RuntimeError("Learning path changed during migration; retry with path writes stopped.")
    return count
