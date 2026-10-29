"""A session stores answers once. Its owner links it; no reverse path context."""

from uuid import UUID, uuid5

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import new_id, utcnow
from modeling_api.schemas.survey_sessions import SurveySessionFields
from modeling_api.schemas.surveys import visibility_condition


def version_for_session(version, session):
    """Apply trusted usage conditions without changing an immutable release."""
    flags = session.get("contextFlags", {})
    elements = []
    visible_names = set()
    for question in version["definition"]["elements"]:
        if question.get("visibleWhen") and not flags.get(question["visibleWhen"], False):
            continue
        if question.get("visibleIf"):
            source, _choice = visibility_condition(question["visibleIf"])
            if source not in visible_names:
                continue
        elements.append(question)
        visible_names.add(question["name"])
    return {**version, "definition": {**version["definition"], "elements": elements}}


async def usage_context(run_id, user):
    """Capture actual usage in this learner's run, not self-reported answers."""
    from modeling_api.services.pulse_surveys import reconcile

    await reconcile(run_id)
    help_request = await db.learning_path_help_requests.find_one(
        {"runId": str(run_id), "ownerId": user.id}, {"_id": 1}
    )
    pulse_answer = await db.learning_path_pulse_events.find_one(
        {"runId": str(run_id), "event": "answered"}, {"_id": 1}
    )
    return {"help_requested": help_request is not None, "pulse_answered": pulse_answer is not None}


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
        version = await surveys.render(survey_id, user, "use", embedded=True)
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
        version = current_release or await surveys.render(survey_id, user, "use", embedded=True)
        if version["id"] != session["releaseId"]:
            await db.survey_sessions.update_one(
                {"_id": session_id, "status": "draft", "revision": session["revision"]},
                {
                    "$set": {"releaseId": version["id"], "answers": {}},
                    "$inc": {"revision": 1},
                },
            )
    session = await db.survey_sessions.find_one({"_id": session_id})
    if phase == "after" and session["status"] == "draft" and not session.get("contextFlags"):
        flags = await usage_context(run_id, user)
        await db.survey_sessions.update_one(
            {"_id": session_id, "userId": user.id, "$or": [
                {"contextFlags": {"$exists": False}}, {"contextFlags": {}},
            ]},
            {"$set": {"contextFlags": flags}},
        )
        session = await db.survey_sessions.find_one({"_id": session_id, "userId": user.id})
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
            surveys.validate_answers(version_for_session(version, session)["definition"], body.answers)
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
