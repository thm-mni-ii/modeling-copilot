"""Idempotent upgrades of previously stored learning-path context."""

from datetime import timedelta
from uuid import UUID, uuid5

from modeling_api.db.client import db


async def migrate_learning_path_context() -> None:
    """Move legacy context before removing it from model documents."""
    async for model in db.models.find({"learningPath": {"$type": "object"}}):
        link = model["learningPath"]
        run = await db.learning_path_runs.find_one(
            {"_id": link["runId"], "ownerId": model["ownerId"]}
        )
        if run is None:
            # Preserve unresolved data for repair instead of silently losing context.
            raise ValueError(
                f"Cannot migrate learning-path context for model {model['_id']}."
            )
        query = {"runId": link["runId"], "stepId": link["stepId"]}
        state = await db.learning_path_step_runs.find_one(query) or {}
        attempt = state.get("challenge")
        if not attempt or "config" not in attempt:
            attempt = model.get("challenge")
            if attempt is None and state.get("challenge"):
                config = state["challenge"]
                started = state.get("startedAt", model["createdAt"])
                attempt = {
                    "config": config,
                    "startedAt": started,
                    "endsAt": (
                        started + timedelta(seconds=config["durationSeconds"])
                        if config.get("durationSeconds")
                        else None
                    ),
                }
        if attempt:
            attempt = {**attempt, "stoppedAt": attempt.get("stoppedAt")}
        await db.learning_path_step_runs.update_one(
            query,
            {
                "$setOnInsert": {
                    "_id": str(uuid5(UUID(link["runId"]), link["stepId"])),
                    **query,
                    "unlockedAt": model["createdAt"],
                },
                "$set": {
                    "modelId": model["_id"],
                    "title": state.get("title", model["name"]),
                    "taskVersion": model["taskVersion"],
                    "startedAt": state.get("startedAt")
                    or (attempt["startedAt"] if attempt else model["createdAt"]),
                    "challenge": attempt,
                },
            },
            upsert=True,
        )
        await db.models.update_one(
            {"_id": model["_id"]}, {"$unset": {"learningPath": "", "challenge": ""}}
        )
