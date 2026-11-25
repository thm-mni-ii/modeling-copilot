"""Initialize Dashboard indexes and preserve existing help-feedback tour progress."""

from pymongo.errors import DuplicateKeyError

from modeling_api.db.client import create_dashboard_indexes, db
from modeling_api.db.migrations import require_completed, run_migration

MIGRATION_ID = "19_initialize_dashboard"
PREREQUISITE = "18_game_development"
LEGACY_EVENTS = {
    "tourVersion": "help-feedback-v1",
    "$or": [
        {"itemId": None, "event": "opened"},
        {"itemId": "help-feedback-walkthrough", "event": {"$in": ["started", "completed", "skipped"]}},
    ],
}


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
    pending = []
    # Validate every matching legacy event before creating indexes or copying data.
    async for legacy in db.learning_path_feature_events.find(LEGACY_EVENTS):
        event = {
            "_id": legacy["_id"],
            "userId": legacy["userId"],
            "tourId": "help-feedback",
            "tourVersion": 1,
            "event": legacy["event"],
            # Earlier events did not record the walkthrough step.
            "stepId": None,
            "at": legacy["at"],
        }
        existing = await db.tour_events.find_one({"_id": event["_id"]})
        if existing is not None:
            if any(existing.get(key) != value for key, value in event.items()):
                raise RuntimeError(f"Conflicting tour event {event['_id']}; existing data was preserved.")
        else:
            pending.append(event)

    print(f"{'Copy' if apply else 'Would copy'} {len(pending)} legacy help-feedback tour event(s).")
    print(f"{'Ensure' if apply else 'Would ensure'} dashboard, tour and analytics access log indexes.")
    if not apply:
        return len(pending)

    await create_dashboard_indexes()
    changed = 0
    for event in pending:
        try:
            # Stable source IDs allow retries; the full filter rejects conflicting concurrent writes.
            result = await db.tour_events.update_one(event, {"$setOnInsert": event}, upsert=True)
        except DuplicateKeyError:
            raise RuntimeError(f"Conflicting tour event {event['_id']}; retry with tour writes stopped.") from None
        changed += int(result.upserted_id is not None)
    return changed
