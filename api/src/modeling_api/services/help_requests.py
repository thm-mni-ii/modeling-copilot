"""Learner-initiated help requests referencing immutable model versions."""

from uuid import UUID, uuid5

from pymongo.errors import DuplicateKeyError
from lxml import etree

from modeling_api.core.errors import conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.db.help_questionnaires import HELP_SURVEY_IDS
from modeling_api.schemas.learning_paths import CreateHelpRequest, HelpRequest
from modeling_api.services import learning_paths as paths, models, survey_sessions

OPEN_STAGES = ("topic", "marking", "reflection", "action")


async def create(run_id, step_id, body: CreateHelpRequest, user):
    run, template, step, state = await paths.step_context(run_id, step_id, user)
    request_id = str(uuid5(UUID(str(run_id)), f"help:{step_id}:{body.request_id}"))
    existing = await db.learning_path_help_requests.find_one({"_id": request_id})
    if existing:
        if existing["modelVersionId"] != str(body.model_version_id):
            raise conflict("This help request already references a different version.")
        return view(existing)
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
        "surveyIds": HELP_SURVEY_IDS,
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
    return view(saved)


def view(document):
    return HelpRequest.model_validate(
        {"id": document["_id"], **{
            key: document[key] for key in (
                "runId", "stepId", "modelId", "modelVersionId", "createdAt"
            )
        }, "stage": document.get("stage", "completed"),
         "surveyIds": document.get("surveyIds", HELP_SURVEY_IDS),
         "markings": document.get("markings"), "nextAction": document.get("nextAction")}
    )


async def owned_request(run_id, step_id, request_id, user):
    await paths.owned_run(run_id, user)
    document = await db.learning_path_help_requests.find_one({
        "_id": str(request_id), "runId": str(run_id), "stepId": str(step_id), "ownerId": user.id,
    })
    if not document:
        raise not_found()
    return document


async def get(run_id, step_id, request_id, user):
    return view(await owned_request(run_id, step_id, request_id, user))


async def active(run_id, step_id, user):
    _, _, _, state = await paths.step_context(run_id, step_id, user)
    document = await db.learning_path_help_requests.find_one({
        "runId": str(run_id), "stepId": str(step_id), "ownerId": user.id,
        "modelId": state.get("modelId"), "stage": {"$in": list(OPEN_STAGES)},
    }, sort=[("createdAt", -1)])
    return view(document) if document else None


async def open_survey(run_id, step_id, request_id, phase, user):
    request = await owned_request(run_id, step_id, request_id, user)
    if phase not in HELP_SURVEY_IDS or request.get("stage") == "cancelled":
        raise conflict("This help questionnaire is not available.")
    existing = request.get("surveySessions", {}).get(phase)
    if request["stage"] != phase and not existing:
        raise conflict("Complete the previous help step first.")
    # The request ID gives each help attempt its own stable survey-session slots.
    session, changed = await survey_sessions.open_path_session(
        request_id, step_id, request.get("surveyIds", HELP_SURVEY_IDS)[phase], phase, True, user
    )
    await db.learning_path_help_requests.update_one(
        {"_id": request["_id"]}, {"$set": {f"surveySessions.{phase}": session["_id"]}}
    )
    if session["status"] == "submitted" and request["stage"] == phase:
        # Recover a process interruption between saving the answers and moving
        # the help request forward. The submitted session is the durable truth.
        await advance(request, phase, session)
    version = await survey_sessions.release(session["releaseId"])
    return {
        "sessionId": session["_id"], "revision": session["revision"],
        "answers": session["answers"], "status": session["status"], "releaseChanged": changed,
        "version": {"id": version["_id"], **{k: v for k, v in version.items() if k != "_id"}},
    }


async def save_survey(run_id, step_id, request_id, phase, body, user, action):
    request = await owned_request(run_id, step_id, request_id, user)
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
    if phase == "topic":
        next_stage = "marking" if session["answers"]["problem_area"] == "Aufgabenstellung/Modell" else "reflection"
    else:
        next_stage = "action" if phase == "reflection" else "completed"
    fields = {"stage": next_stage}
    if next_stage == "completed":
        fields.update(completedAt=session["completedAt"], nextAction=session["answers"]["next_action"])
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
    await db.learning_path_help_requests.update_one(
        {"_id": request["_id"], "stage": {"$in": list(OPEN_STAGES)}},
        {"$set": {"stage": "cancelled", "cancelledAt": utcnow()}},
    )
    return await get(run_id, step_id, request_id, user)
