"""Full survey snapshots, explicit releases and immutable response references."""

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import ApiError, conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import list_page, new_id, to_api, utcnow
from modeling_api.schemas.surveys import ActivateRelease, SaveSurvey, SubmitResponse, visibility_condition


def require_admin(user):
    if not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "Administrator access is required.")


def require_editable(doc):
    if doc.get("managedBy") == "learning-path-help":
        raise ApiError(409, "PATH_MANAGED_SURVEY", "Bearbeite diesen Hilfe-Fragebogen direkt im zugehörigen Lernpfad.")


async def _insert_once(collection, document):
    try:
        await collection.update_one(
            {"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True
        )
    except DuplicateKeyError:
        if not await collection.find_one({"_id": document["_id"]}):
            raise


async def _finish_pending(doc):
    """Finish a committed operation idempotently, including after a process crash.

    The parent CAS commits the pointer and a bounded operation record atomically.
    Every reader/writer flushes it before using the parent. A new mutation cannot
    replace this record until its snapshot/release is durable.
    This also works with standalone MongoDB without multi-document transactions.
    """
    pending = doc.get("pending")
    if pending is None:
        return
    if "version" in pending:
        await _insert_once(db.survey_versions, pending["version"])
    if "release" in pending:
        release = pending["release"]
        await db.survey_versions.update_one(
            {"_id": release["id"], "surveyId": doc["_id"], "kind": "checkpoint"},
            {
                "$set": {
                    "kind": "release",
                    "releasedAt": release["at"],
                    "releasedBy": release["by"],
                }
            },
        )
    await db.surveys.update_one(
        {"_id": doc["_id"], "revision": doc["revision"]}, {"$unset": {"pending": ""}}
    )


async def survey_document(survey_id, *, include_deleted=False):
    query = {"_id": str(survey_id)}
    if not include_deleted:
        query["deletedAt"] = None
    doc = await db.surveys.find_one(query)
    if not doc:
        raise not_found()
    await _finish_pending(doc)
    return doc


def public_survey(doc):
    return {
        k: v
        for k, v in to_api(doc).items()
        if k not in ("deletedAt", "pending", "schemaVersion", "pathRevision")
    }


async def list_surveys(user, skip, limit):
    require_admin(user)
    page = await list_page(db.surveys, {"deletedAt": None}, skip, limit)
    for item in page["items"]:
        await _finish_pending({"_id": item["id"], **item})
    page["items"] = [
        public_survey({"_id": item["id"], **item}) for item in page["items"]
    ]
    return page


async def get_survey(survey_id, user):
    require_admin(user)
    return public_survey(await survey_document(survey_id))


async def _version(doc, version_id):
    version = await db.survey_versions.find_one(
        {"_id": str(version_id), "surveyId": doc["_id"]}
    )
    if not version:
        raise not_found()
    return version


async def get_version(survey_id, version_id, user):
    require_admin(user)
    return to_api(
        await _version(
            await survey_document(survey_id, include_deleted=True), version_id
        )
    )


async def list_versions(survey_id, user, skip, limit):
    require_admin(user)
    await survey_document(survey_id, include_deleted=True)
    return await list_page(
        db.survey_versions,
        {"surveyId": str(survey_id)},
        skip,
        limit,
        sort_field="version",
        omit=("definition",),
    )


async def responses(survey_id, user, skip, limit):
    require_admin(user)
    await survey_document(survey_id, include_deleted=True)
    from modeling_api.services.survey_sessions import response_view

    releases = {
        v["_id"]: v
        async for v in db.survey_versions.find(
            {"surveyId": str(survey_id)}, {"surveyId": 1, "version": 1}
        )
    }
    page = await list_page(
        db.survey_sessions,
        {"releaseId": {"$in": list(releases)}, "status": "submitted"},
        skip,
        limit,
        sort_field="completedAt",
    )
    page["items"] = [
        response_view(
            {"_id": session["id"], **{k: v for k, v in session.items() if k != "id"}},
            releases[session["releaseId"]],
        )
        for session in page["items"]
    ]
    return page


async def render(survey_id, user, mode, version_id=None, *, embedded=False):
    if mode != "use" or not embedded:
        require_admin(user)
    doc = await survey_document(survey_id)
    if mode == "use":
        if version_id is not None:
            raise ApiError(
                422, "INVALID_VERSION", "New responses must load the active release."
            )
        version_id = doc["activeReleaseId"]
        if version_id is None:
            raise ApiError(
                409,
                "NO_ACTIVE_RELEASE",
                "This questionnaire has no active release yet.",
            )
    else:
        version_id = version_id or doc["latestVersionId"]
    return to_api(await _version(doc, version_id))


async def _commit(doc, fields, pending):
    updated = {**doc, **fields, "revision": doc["revision"] + 1, "pending": pending}
    result = await db.surveys.update_one(
        {
            "_id": doc["_id"],
            "revision": doc["revision"],
            "deletedAt": None,
            "pending": {"$exists": False},
        },
        {"$set": {**fields, "pending": pending}, "$inc": {"revision": 1}},
    )
    if not result.matched_count:
        raise conflict()
    await _finish_pending(updated)
    return public_survey(updated)


async def save_survey(body: SaveSurvey, user, survey_id=None):
    require_admin(user)
    now = utcnow()
    definition = body.definition.model_dump(exclude_none=True)
    if survey_id is None:
        survey_id = new_id()
        number = 1
        old = None
    else:
        old = await survey_document(survey_id)
        require_editable(old)
        if (
            body.expected_revision != old["revision"]
            or str(body.base_version_id) != old["latestVersionId"]
        ):
            raise conflict()
        if body.title == old["title"] and definition == old["definition"]:
            return public_survey(old)
        number = old["version"] + 1
    version = {
        "_id": new_id(),
        "surveyId": str(survey_id),
        "version": number,
        "title": body.title,
        "definition": definition,
        "kind": "checkpoint",
        "createdAt": now,
        "createdBy": user.id,
        "releasedAt": None,
        "releasedBy": None,
    }
    fields = {
        "title": body.title,
        "definition": definition,
        "latestVersionId": version["_id"],
        "latestKind": "checkpoint",
        "version": number,
        "updatedAt": now,
        "updatedBy": user.id,
    }
    if old is None:
        doc = {
            "_id": str(survey_id),
            **fields,
            "revision": 1,
            "schemaVersion": 2,
            "createdAt": now,
            "createdBy": user.id,
            "deletedAt": None,
            "activeReleaseId": None,
            "activeReleaseVersion": None,
            "pending": {"version": version},
        }
        await db.surveys.insert_one(doc)
        await _finish_pending(doc)
        return public_survey(doc)
    return await _commit(old, fields, {"version": version})


async def activate(survey_id, body: ActivateRelease, user):
    require_admin(user)
    doc = await survey_document(survey_id)
    require_editable(doc)
    if body.expected_revision != doc["revision"]:
        raise conflict()
    version = await _version(doc, body.version_id)
    if doc["activeReleaseId"] == version["_id"]:
        return public_survey(doc)
    now = utcnow()
    fields = {
        "activeReleaseId": version["_id"],
        "activeReleaseVersion": version["version"],
        "updatedAt": now,
        "updatedBy": user.id,
    }
    if doc["latestVersionId"] == version["_id"]:
        fields["latestKind"] = "release"
    return await _commit(
        doc,
        fields,
        {
            "release": {"id": version["_id"], "at": now, "by": user.id},
        },
    )


async def delete_survey(survey_id, user):
    require_admin(user)
    doc = await survey_document(survey_id)
    require_editable(doc)
    now = utcnow()
    await _commit(doc, {"deletedAt": now, "updatedAt": now, "updatedBy": user.id}, {})


async def submit(survey_id, body: SubmitResponse, user):
    # Learners submit through owned path sessions, never the standalone endpoint.
    require_admin(user)
    doc = await survey_document(survey_id)
    if doc.get("managedBy") == "learning-path-help" and body.mode != "preview":
        raise ApiError(409, "PATH_MANAGED_SURVEY", "Dieser Fragebogen wird über den Hilfe-Ablauf im Lernpfad ausgefüllt.")
    version = await _version(doc, body.version_id)
    # Previously loaded releases remain valid after an activation/rollback.
    if body.mode == "use" and version["kind"] != "release":
        raise ApiError(
            422,
            "NOT_A_RELEASE",
            "Only released questionnaires accept regular responses.",
        )
    validate_answers(version["definition"], body.answers)
    from modeling_api.services.survey_sessions import submit_standalone

    return await submit_standalone(version, body, user)


def validate_answers(definition, answers):
    questions = {q["name"]: q for q in definition["elements"]}
    if answers.keys() - questions.keys():
        raise ApiError(422, "INVALID_ANSWERS", "Unknown question in answers.")
    for name, q in questions.items():
        if q.get("visibleIf"):
            source, expected = visibility_condition(q["visibleIf"])
            selected = answers.get(source)
            matches = expected in selected if q["visibleIf"].partition("} ")[2].startswith("contains ") and isinstance(selected, list) else selected == expected
            if q["visibleIf"].partition("} ")[2].startswith("!= "):
                matches = selected is not None and selected != "" and selected != expected
            if not matches:
                continue
        value = answers.get(name)
        empty = value is None or value == "" or value == [] or value == {}
        invalid = False
        if value is not None and empty:
            expected = {
                "comment": str,
                "radiogroup": str,
                "checkbox": list,
                "matrix": dict,
                "rating": int,
            }
            invalid = type(value) is not expected[q["type"]]
        if not empty:
            kind = q["type"]
            if kind == "comment":
                invalid = not isinstance(value, str) or len(value) > 20_000
            elif kind == "radiogroup":
                invalid = not isinstance(value, str) or value not in q["choices"]
            elif kind == "checkbox":
                invalid = not isinstance(value, list) or any(
                    not isinstance(v, str) or v not in q["choices"] for v in value
                )
                if not invalid:
                    invalid = len(set(value)) != len(value)
                if not invalid and len(value) > 1:
                    invalid = any(v in (q.get("exclusiveChoices") or []) for v in value)
            elif kind == "rating":
                invalid = (
                    type(value) is not int or not q["rateMin"] <= value <= q["rateMax"]
                )
            elif kind == "matrix":
                invalid = not isinstance(value, dict) or any(
                    row not in q["rows"]
                    or not isinstance(v, str)
                    or v not in q["columns"]
                    for row, v in value.items()
                )
                if not invalid and (q["isRequired"] or q.get("isAllRowRequired")):
                    invalid = set(value) != set(q["rows"])
        if invalid or (q["isRequired"] and empty):
            raise ApiError(422, "INVALID_ANSWERS", f"Invalid or missing answer: {name}")
