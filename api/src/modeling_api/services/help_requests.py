"""Learner-initiated help requests referencing immutable model versions."""

from uuid import UUID, uuid5

from pymongo.errors import DuplicateKeyError
from lxml import etree

from modeling_api.core.errors import conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.db.help_questionnaires import HELP_SURVEY_IDS
from modeling_api.schemas.learning_paths import CreateHelpRequest, HelpRequest, HelpRequestConfig
from modeling_api.services.help_configuration import validate_phase
from modeling_api.services import learning_paths as paths, models, survey_sessions, surveys, help_questionnaire

OPEN_STAGES = ("topic", "marking", "reflection", "action")


async def create(run_id, step_id, body: CreateHelpRequest, user):
    run, template, step, state = await paths.step_context(run_id, step_id, user)
    request_id = str(uuid5(UUID(str(run_id)), f"help:{step_id}:{body.request_id}"))
    existing = await db.learning_path_help_requests.find_one({"_id": request_id})
    if existing:
        if existing["modelVersionId"] != str(body.model_version_id):
            raise conflict("This help request already references a different version.")
        if existing.get("surveySessionId"):
            await ensure_session(existing)
        return view(await recover_cancellation(existing))
    if (
        not template.get("helpRequests", {}).get("enabled")
        or step["kind"] != "task"
        or step.get("archivedAt")
        or not state.get("modelId")
        or state.get("completedAt")
        or state.get("workSubmittedAt")
    ):
        raise conflict("Help requests are not available for this task.")
    model_id = state["modelId"]
    await models.get_model(UUID(model_id), user)
    await models.ensure_task_questionnaire_completed(model_id)
    version = await db.model_versions.find_one(
        {"_id": str(body.model_version_id), "modelId": model_id}
    )
    if not version:
        raise not_found()
    config = HelpRequestConfig.model_validate(template.get("helpRequests", {}))
    questionnaire = await help_questionnaire.publish(
        template["_id"], template["title"], template["revision"], config, user.id
    )
    document = {
        "_id": request_id,
        "runId": run["_id"],
        "stepId": str(step_id),
        "templateId": template["_id"],
        "templateRevision": template["revision"],
        "ownerId": user.id,
        "modelId": model_id,
        "modelVersionId": str(body.model_version_id),
        "createdAt": utcnow(),
        "stage": "topic",
        "surveyIds": {phase: questionnaire["surveyId"] for phase in HELP_SURVEY_IDS},
        "surveyReleaseId": questionnaire["_id"],
        "surveySessionId": str(uuid5(UUID(request_id), "survey-session")),
        "helpConfig": {**config.model_dump(mode="json", by_alias=True),
                       "topicQuestion": "problem_area", "markingAnswer": "Aufgabenstellung/Modell", "actionQuestion": "next_action"},
    }
    # Retrying a request after a lost response must not create another event.
    try:
        await db.learning_path_help_requests.update_one(
            {"_id": request_id}, {"$setOnInsert": document}, upsert=True
        )
    except DuplicateKeyError:
        pass
    saved = await db.learning_path_help_requests.find_one({"_id": request_id})
    if saved["modelVersionId"] != str(body.model_version_id):
        raise conflict("This help request already references a different version.")
    await ensure_session(saved)
    return view(saved)


def view(document):
    return HelpRequest.model_validate(
        {"id": document["_id"], **{
            key: document[key] for key in (
                "runId", "stepId", "modelId", "modelVersionId", "createdAt"
            )
        }, "stage": document.get("stage", "completed"),
         "surveyIds": document.get("surveyIds", HELP_SURVEY_IDS),
         "markings": document.get("markings"), "nextAction": document.get("nextAction"),
         "nextActionId": document.get("nextActionId"), "surveySessionId": document.get("surveySessionId"),
         "markingRequired": document.get("helpConfig", {}).get("markingRequired", True)}
    )


async def owned_request(run_id, step_id, request_id, user):
    await paths.owned_run(run_id, user)
    document = await db.learning_path_help_requests.find_one({
        "_id": str(request_id), "runId": str(run_id), "stepId": str(step_id), "ownerId": user.id,
    })
    if not document:
        raise not_found()
    return await recover_cancellation(document)


async def get(run_id, step_id, request_id, user):
    return view(await owned_request(run_id, step_id, request_id, user))


async def active(run_id, step_id, user):
    _, _, _, state = await paths.step_context(run_id, step_id, user)
    document = await db.learning_path_help_requests.find_one({
        "runId": str(run_id), "stepId": str(step_id), "ownerId": user.id,
        "modelId": state.get("modelId"), "stage": {"$in": list(OPEN_STAGES)},
    }, sort=[("createdAt", -1)])
    document = await recover_cancellation(document) if document else None
    return view(document) if document and document["stage"] != "cancelled" else None


async def open_survey(run_id, step_id, request_id, phase, user):
    request = await owned_request(run_id, step_id, request_id, user)
    if request.get("surveySessionId"):
        return await open_combined(request, phase)
    if phase not in HELP_SURVEY_IDS or request.get("stage") == "cancelled":
        raise conflict("This help questionnaire is not available.")
    existing = request.get("surveySessions", {}).get(phase)
    if request["stage"] != phase and not existing:
        raise conflict("Complete the previous help step first.")
    # The request ID gives each help attempt its own stable survey-session slots.
    session, changed = await survey_sessions.open_path_session(
        request_id, step_id, request.get("surveyIds", HELP_SURVEY_IDS)[phase], phase, True, user
    )
    version = await survey_sessions.release(session["releaseId"])
    validate_phase(phase, version, HelpRequestConfig.model_validate(request.get("helpConfig", {})))
    await db.learning_path_help_requests.update_one(
        {"_id": request["_id"]}, {"$set": {f"surveySessions.{phase}": session["_id"]}}
    )
    if session["status"] == "submitted" and request["stage"] == phase:
        # Recover a process interruption between saving the answers and moving
        # the help request forward. The submitted session is the durable truth.
        await advance(request, phase, session)
    return {
        "sessionId": session["_id"], "revision": session["revision"],
        "answers": session["answers"], "status": session["status"], "releaseChanged": changed,
        "version": {"id": version["_id"], **{k: v for k, v in version.items() if k != "_id"}},
    }


async def save_survey(run_id, step_id, request_id, phase, body, user, action):
    request = await owned_request(run_id, step_id, request_id, user)
    if request.get("surveySessionId"):
        return await save_combined(request, phase, body, action)
    if phase not in HELP_SURVEY_IDS or request.get("stage") == "cancelled":
        raise conflict("This help questionnaire is not available.")
    if request.get("surveySessions", {}).get(phase) != str(body.session_id):
        raise conflict("Reopen the help questionnaire before continuing.")
    session = await db.survey_sessions.find_one({"_id": str(body.session_id), "userId": user.id})
    if not session:
        raise not_found()
    version = await survey_sessions.release(session["releaseId"])
    if version["surveyId"] != request.get("surveyIds", HELP_SURVEY_IDS)[phase]:
        raise conflict("This questionnaire does not belong to this help step.")
    session = await survey_sessions.save(session, body, action, True)
    if action == "draft":
        return {"revision": session["revision"]}
    await advance(request, phase, session)
    return survey_sessions.response_view(session, version)


async def advance(request, phase, session):
    config = HelpRequestConfig.model_validate(request.get("helpConfig", {}))
    if phase == "topic":
        marking = config.marking_enabled and session["answers"].get(config.topic_question) == config.marking_answer
        next_stage = "marking" if marking else "reflection"
    else:
        next_stage = "action" if phase == "reflection" else "completed"
    fields = {"stage": next_stage}
    if next_stage == "completed":
        fields.update(completedAt=session["completedAt"], nextAction=session["answers"][config.action_question])
        if request.get("surveySessionId"):
            version = await survey_sessions.release(session["releaseId"])
            question = next(q for q in version["definition"]["elements"] if q["name"] == "next_action")
            value = session["answers"]["next_action"]
            fields.update(nextActionId=value, nextAction=question["choiceLabels"][value])
    await db.learning_path_help_requests.update_one(
        {"_id": request["_id"], "stage": phase}, {"$set": fields}
    )


async def save_markings(run_id, step_id, request_id, body, user):
    request = await owned_request(run_id, step_id, request_id, user)
    markings = body.model_dump(mode="json", by_alias=True)
    if request.get("stage") != "marking":
        if request.get("markings") == markings and request.get("stage") in ("reflection", "action", "completed"):
            return view(request)
        raise conflict("Markings can only be submitted after choosing task/model help.")
    if request.get("helpConfig", {}).get("markingRequired", True) and not body.cell_ids and not body.task_text_ranges:
        raise conflict("Markiere mindestens ein Modellelement oder eine Textstelle.")
    version = await models.get_version(UUID(request["modelId"]), UUID(request["modelVersionId"]), user)
    xml = etree.fromstring(version["data"]["xml"].encode(), etree.XMLParser(resolve_entities=False, no_network=True))
    ids = set()
    for node in xml.iter():
        if node.get("vertex") in ("1", "true") or node.get("edge") in ("1", "true"):
            cell_id = node.get("id")
            if not cell_id and node.getparent() is not None:
                cell_id = node.getparent().get("id")
            if cell_id:
                ids.add(cell_id)
    if not set(body.cell_ids) <= ids:
        raise conflict("A selected element is not part of the saved model checkpoint.")
    result = await db.learning_path_help_requests.update_one(
        {"_id": request["_id"], "stage": "marking"},
        {"$set": {"markings": markings, "markingsSubmittedAt": utcnow(), "stage": "reflection"}},
    )
    if not result.matched_count:
        current = await owned_request(run_id, step_id, request_id, user)
        if current.get("markings") != markings:
            raise conflict()
    return await get(run_id, step_id, request_id, user)


async def cancel(run_id, step_id, request_id, user):
    request = await owned_request(run_id, step_id, request_id, user)
    if request.get("surveySessionId"):
        if request["stage"] == "cancelled":
            return view(request)
        if request["stage"] != "topic":
            raise conflict("The help flow can only be cancelled at the beginning.")
        result = await db.survey_sessions.update_one(
            {"_id": request["surveySessionId"], "status": "draft", "helpCompletedPhases.topic": {"$exists": False}},
            {"$set": {"cancelledAt": utcnow()}},
        )
        if not result.matched_count:
            raise conflict("The first help question has already been completed.")
    await db.learning_path_help_requests.update_one(
        {"_id": request["_id"], "stage": {"$in": list(OPEN_STAGES)}},
        {"$set": {"stage": "cancelled", "cancelledAt": utcnow()}},
    )
    return await get(run_id, step_id, request_id, user)


async def ensure_session(request):
    await surveys._insert_once(db.survey_sessions, {
        "_id": request["surveySessionId"], "userId": request["ownerId"],
        "releaseId": request["surveyReleaseId"], "status": "draft", "answers": {},
        "revision": 0, "isTest": False, "createdAt": request["createdAt"], "helpCompletedPhases": {},
    })
    return await db.survey_sessions.find_one({"_id": request["surveySessionId"], "userId": request["ownerId"]})


async def recover_cancellation(request):
    if request.get("surveySessionId") and request["stage"] == "topic":
        session = await db.survey_sessions.find_one({"_id": request["surveySessionId"]})
        if session and session.get("cancelledAt"):
            await db.learning_path_help_requests.update_one(
                {"_id": request["_id"], "stage": "topic"},
                {"$set": {"stage": "cancelled", "cancelledAt": session["cancelledAt"]}},
            )
            return {**request, "stage": "cancelled"}
    return request


async def open_combined(request, phase):
    if phase not in HELP_SURVEY_IDS or request["stage"] == "cancelled":
        raise conflict("This help questionnaire is not available.")
    session = await ensure_session(request)
    done = phase in session.get("helpCompletedPhases", {})
    if request["stage"] != phase and not done:
        raise conflict("Complete the previous help step first.")
    if done and request["stage"] == phase:
        await advance(request, phase, session)
    version = await survey_sessions.release(request["surveyReleaseId"])
    return {
        "sessionId": session["_id"], "revision": session["revision"],
        "answers": {k: v for k, v in session["answers"].items() if k in help_questionnaire.PHASE_QUESTIONS[phase]},
        "status": "submitted" if done else "draft", "releaseChanged": False,
        "version": {"id": version["_id"], **{k: v for k, v in version.items() if k != "_id"},
                    "definition": help_questionnaire.phase_definition(version, phase)},
    }


async def save_combined(request, phase, body, action):
    if phase not in HELP_SURVEY_IDS or request["stage"] == "cancelled" or str(body.session_id) != request["surveySessionId"]:
        raise conflict("This help questionnaire is not available.")
    session = await ensure_session(request)
    version = await survey_sessions.release(request["surveyReleaseId"])
    done = session.get("helpCompletedPhases", {})
    if action == "submit" and phase in done:
        await advance(request, phase, session)
        return survey_sessions.response_view({**session, "completedAt": done[phase]}, version)
    if request["stage"] != phase or session["status"] != "draft" or phase in done:
        raise conflict("Complete the current help step first.")
    content = help_questionnaire.phase_definition(version, phase)
    surveys.validate_answers(content if action == "submit" else {
        "elements": [{**q, "isRequired": False} for q in content["elements"]]
    }, body.answers)
    # Only the active phase is writable. Earlier answers cannot be overwritten.
    answers = {**session["answers"], **body.answers}
    now = utcnow()
    fields = {"answers": answers}
    if action == "submit":
        fields[f"helpCompletedPhases.{phase}"] = now
        if phase == "action":
            surveys.validate_answers(version["definition"], answers)
            fields.update(status="submitted", completedAt=now)
    result = await db.survey_sessions.update_one(
        {"_id": session["_id"], "userId": request["ownerId"], "releaseId": request["surveyReleaseId"],
         "status": "draft", "revision": body.revision, "cancelledAt": {"$exists": False}},
        {"$set": fields, "$inc": {"revision": 1}},
    )
    latest = await db.survey_sessions.find_one({"_id": session["_id"]})
    if not result.matched_count:
        if action != "submit" or phase not in latest.get("helpCompletedPhases", {}):
            raise conflict("The questionnaire changed in another window. Reopen it before continuing.")
    if action == "draft":
        return {"revision": latest["revision"]}
    await advance(request, phase, latest)
    return survey_sessions.response_view({**latest, "completedAt": latest["helpCompletedPhases"][phase]}, version)
