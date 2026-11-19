"""User-level tour progress and staff reporting for learning-path features."""

from modeling_api.core.errors import ApiError
from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.services.fbs_users import resolve_names
from modeling_api.services.learning_path_progress import require_access

# Bump this when new tour content should appear as new for every learner.
TOUR_VERSION = "help-feedback-v1"
TOUR_ITEMS = ("feedback-types", "help-request", "mark-object", "automatic-feedback", "help-feedback-walkthrough")


async def get_progress(user):
    filters = {"userId": user.id, "tourVersion": TOUR_VERSION}
    completed = set(await db.learning_path_feature_events.distinct(
        "itemId", {**filters, "event": "completed"}
    ))
    skipped = set(await db.learning_path_feature_events.distinct(
        "itemId", {**filters, "event": "skipped"}
    ))
    skipped.difference_update(completed)
    first_opened = await db.learning_path_feature_events.find_one(
        {**filters, "event": "opened"}, {"at": 1}, sort=[("at", 1)]
    )
    return {
        "completedItems": sorted(item for item in completed if item in TOUR_ITEMS),
        "skippedItems": sorted(item for item in skipped if item in TOUR_ITEMS),
        "firstOpenedAt": first_opened["at"] if first_opened else None,
    }


async def record_event(user, body):
    if body.item_id and body.event == "opened":
        raise ApiError(422, "INVALID_TOUR_EVENT", "Opening the tour menu cannot reference an item.")
    if not body.item_id and body.event != "opened":
        raise ApiError(422, "INVALID_TOUR_EVENT", "This tour event requires an item.")
    await db.learning_path_feature_events.insert_one({
        "userId": user.id,
        "tourVersion": TOUR_VERSION,
        "itemId": body.item_id,
        "event": body.event,
        "at": utcnow(),
    })
    return await get_progress(user)


async def report(user, token=None):
    require_access(user)
    groups_cursor = await db.learning_path_feature_events.aggregate([
        {"$match": {"tourVersion": TOUR_VERSION}},
        {"$group": {
            "_id": "$userId",
            "openedCount": {"$sum": {"$cond": [{"$eq": ["$event", "opened"]}, 1, 0]}},
            "tourStarts": {"$sum": {"$cond": [{"$eq": ["$event", "started"]}, 1, 0]}},
            "completedItems": {"$addToSet": {"$cond": [{"$eq": ["$event", "completed"]}, "$itemId", None]}},
            "skippedItems": {"$addToSet": {"$cond": [{"$eq": ["$event", "skipped"]}, "$itemId", None]}},
            "lastEventAt": {"$max": "$at"},
        }},
        {"$sort": {"lastEventAt": -1, "_id": 1}},
    ])
    groups = [row async for row in groups_cursor]
    opened_cursor = await db.learning_path_feature_events.aggregate([
        {"$match": {"tourVersion": TOUR_VERSION, "event": "opened"}},
        {"$group": {"_id": "$userId", "firstOpenedAt": {"$min": "$at"}}},
    ])
    opened = {
        row["_id"]: row["firstOpenedAt"]
        async for row in opened_cursor
    }
    names = await resolve_names((row["_id"] for row in groups), user, token)
    participants = [{
        "userId": row["_id"],
        "userName": names.get(row["_id"], row["_id"]),
        "openedCount": row["openedCount"],
        "tourStarts": row["tourStarts"],
        "firstOpenedAt": opened.get(row["_id"]),
        "completedItems": sorted(item for item in row["completedItems"] if item in TOUR_ITEMS),
        "skippedItems": sorted(item for item in row["skippedItems"] if item in TOUR_ITEMS),
        "lastEventAt": row["lastEventAt"],
    } for row in groups]
    return {
        "openedUsers": sum(row["openedCount"] > 0 for row in participants),
        "openedEvents": sum(row["openedCount"] for row in participants),
        "tourStarts": sum(row["tourStarts"] for row in participants),
        "participants": participants,
    }
