"""A session stores answers once. Its owner links it; no reverse path context."""

from uuid import UUID, uuid5

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import new_id, utcnow
from modeling_api.schemas.survey_sessions import SurveySessionFields


async def release(release_id):
    version = await db.survey_versions.find_one({"_id": str(release_id)})
    if not version:
        raise not_found()
    if version["kind"] != "release":
        raise conflict("Choose a published questionnaire release.")
    return version


def response_view(session, version):
    return {
        "id": session["_id"],
        "surveyId": version["surveyId"],
        "versionId": session["releaseId"],
        "version": version["version"],
        "userId": session["userId"],
        "answers": session["answers"],
        "isTest": session["isTest"],
        "createdAt": session["completedAt"],
    }


async def open_path_session(run_id, step_id, survey_id, phase, required, user):
    from modeling_api.services import surveys

    # A stable ID makes simultaneous opens idempotent without duplicating ownership data.
    slot = phase or "step"
    session_id = str(uuid5(UUID(str(run_id)), f"{step_id}:{slot}:{survey_id}"))
    session = await db.survey_sessions.find_one({"_id": session_id, "userId": user.id})
    previous_release = session["releaseId"] if session else None
    current_release = None
    if session is None:
        version = await surveys.render(survey_id, user, "use")
        current_release = version
        fields = SurveySessionFields(
            userId=user.id,
            releaseId=version["id"],
            status="draft",
            createdAt=utcnow(),
        ).model_dump(by_alias=True, exclude_none=True)
        try:
            await db.survey_sessions.update_one(
                {"_id": session_id}, {"$setOnInsert": fields}, upsert=True
            )
        except DuplicateKeyError:
            pass
        session = await db.survey_sessions.find_one(
            {"_id": session_id, "userId": user.id}
        )
    if session["status"] == "skipped" and required:
        await db.survey_sessions.update_one(
            {"_id": session_id, "status": "skipped", "revision": session["revision"]},
            {
                "$set": {"status": "draft"},
                "$unset": {"completedAt": ""},
                "$inc": {"revision": 1},
            },
        )
        session = await db.survey_sessions.find_one({"_id": session_id})
    if session["status"] == "draft":
        version = current_release or await surveys.render(survey_id, user, "use")
        if version["id"] != session["releaseId"]:
            await db.survey_sessions.update_one(
                {"_id": session_id, "status": "draft", "revision": session["revision"]},
                {
                    "$set": {"releaseId": version["id"], "answers": {}},
                    "$inc": {"revision": 1},
                },
            )
    session = await db.survey_sessions.find_one({"_id": session_id})
    return session, bool(previous_release and previous_release != session["releaseId"])


async def save(session, body, action, required):
    from modeling_api.services import surveys

    if action == "skip" and required:
        raise conflict("Required questionnaires cannot be skipped.")
    if session["status"] != "draft":
        if (action, session["status"]) in (
            ("submit", "submitted"),
            ("skip", "skipped"),
        ):
            return session
        raise conflict("This questionnaire is already closed.")
    fields = {}
    if action == "skip":
        fields.update(status="skipped", completedAt=utcnow(), answers={})
    else:
        if action == "submit":
            version = await release(session["releaseId"])
            surveys.validate_answers(version["definition"], body.answers)
            fields.update(status="submitted", completedAt=utcnow())
        fields["answers"] = body.answers
    result = await db.survey_sessions.update_one(
        {
            "_id": session["_id"],
            "userId": session["userId"],
            "status": "draft",
            "revision": body.revision,
        },
        {"$set": fields, "$inc": {"revision": 1}},
    )
    latest = await db.survey_sessions.find_one({"_id": session["_id"]})
    if not result.matched_count and (action, latest["status"]) not in (
        ("submit", "submitted"),
        ("skip", "skipped"),
    ):
        raise conflict(
            "The questionnaire changed in another window. Reopen it before continuing."
        )
    return latest


async def submit_standalone(version, body, user):
    fields = SurveySessionFields(
        userId=user.id,
        releaseId=version["_id"],
        status="submitted",
        answers=body.answers,
        isTest=body.mode == "test",
        createdAt=utcnow(),
        completedAt=utcnow(),
    ).model_dump(by_alias=True, exclude_none=True)
    session = {"_id": new_id(), **fields}
    if body.mode != "preview":
        await db.survey_sessions.insert_one(session)
    return response_view(session, version)
