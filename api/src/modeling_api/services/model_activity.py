"""Independent model sessions with immutable, related browser interactions."""

from uuid import UUID

from pymongo import UpdateOne
from pymongo.errors import BulkWriteError, DuplicateKeyError

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import list_page, to_api
from modeling_api.schemas.model_activity import SaveActivitySession
from modeling_api.services.learning_path_access import require_model_access


def mongo_time(value):
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


async def save_session(model_id: UUID, session_id: UUID, body: SaveActivitySession, user: User):
    if not await db.models.find_one({"_id": str(model_id), "ownerId": user.id}, {"_id": 1}):
        raise not_found()
    await require_model_access(model_id, user)
    session = {"_id": str(session_id), "modelId": str(model_id),
               "createdBy": user.id, "createdAt": mongo_time(body.created_at)}
    query = dict(session)
    if body.ended_at is not None:
        ended_at = mongo_time(body.ended_at)
        query["$or"] = [{"endedAt": None}, {"endedAt": ended_at}]
        update = {"$set": {"endedAt": ended_at}}
    else:
        # A delayed open-session batch must never reopen a closed session.
        update = {"$setOnInsert": {"endedAt": None}}
    try:
        await db.model_activity_sessions.update_one(query, update, upsert=True)
    except DuplicateKeyError:
        raise conflict("The activity session ID was reused with different details.") from None

    stored = await db.model_activity_sessions.find_one({"_id": str(session_id)}, {"endedAt": 1})
    if stored["endedAt"] is not None and any(
        mongo_time(item.created_at) > stored["endedAt"] for item in body.interactions
    ):
        raise conflict("An interaction cannot follow the session end.")
    if not body.interactions:
        return
    operations = []
    for item in body.interactions:
        fields = {"_id": str(item.id), "sessionId": str(session_id),
                  "createdAt": mongo_time(item.created_at), "type": item.type}
        operations.append(UpdateOne(fields, {"$setOnInsert": fields}, upsert=True))
    try:
        await db.model_activity_interactions.bulk_write(operations, ordered=False)
    except BulkWriteError as exc:
        if exc.details.get("writeErrors") and all(
            error["code"] == 11000 for error in exc.details["writeErrors"]
        ) and not exc.details.get("writeConcernErrors"):
            raise conflict("An interaction ID was reused with different content.") from None
        raise


def require_admin(user):
    if not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "Activity data requires administrator access.")


async def list_sessions(model_id, skip, limit, user):
    require_admin(user)
    return await list_page(db.model_activity_sessions, {"modelId": str(model_id)}, skip, limit)


async def get_session(model_id, session_id, user):
    require_admin(user)
    session = await db.model_activity_sessions.find_one(
        {"_id": str(session_id), "modelId": str(model_id)}
    )
    if session is None:
        raise not_found()
    return to_api(session)


async def list_interactions(model_id, session_id, skip, limit, user):
    await get_session(model_id, session_id, user)
    return await list_page(
        db.model_activity_interactions, {"sessionId": str(session_id)},
        skip, limit, sort_desc=False,
    )
