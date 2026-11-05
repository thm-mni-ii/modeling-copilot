"""Persistence of live path definitions and personal step progress.

Collections: learning_path_templates (metadata + ordered stepIds),
learning_path_template_steps (one document per step, archived never deleted),
learning_path_runs and learning_path_run_steps (personal progress per step).
API views deliberately differ from storage: runs reference template steps and
never copy them.
"""

from uuid import UUID, uuid5

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import not_found
from modeling_api.services.learning_path_access import template_visibility
from modeling_api.db.client import db
from modeling_api.schemas.learning_path_documents import (
    LearningPathTemplateContent,
    LearningPathStepState,
    TaskStepDefinition,
    SurveyStepDefinition,
)


def step_document(step, template_id):
    """Stored step fields without _id and timestamps."""
    common = {
        "templateId": str(template_id),
        "kind": step.type,
        "title": step.title,
        "unlock": step.unlock.model_dump(mode="json", by_alias=True),
    }
    if step.type == "task":
        common["task"] = {
            "taskId": str(step.task_version.task_id),
            "releaseId": str(step.task_version.version_id),
            "beforeSurveyId": (
                str(step.before_survey_id) if step.before_survey_id else None
            ),
            "afterSurveyId": (
                str(step.after_survey_id) if step.after_survey_id else None
            ),
            "challenge": (
                step.challenge.model_dump(mode="json", by_alias=True)
                if step.challenge
                else None
            ),
        }
        model = TaskStepDefinition
    else:
        common["survey"] = {
            "surveyId": str(step.survey_id),
            "required": step.required,
        }
        model = SurveyStepDefinition
    return model.model_validate(common).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def template_meta(body, step_ids):
    return LearningPathTemplateContent.model_validate(
        {
            "title": body.name,
            "description": body.description,
            "status": body.visibility,
            "stepIds": [str(i) for i in step_ids],
            "pulseSurveys": body.pulse_surveys,
            "helpRequests": body.help_requests,
        }
    ).model_dump(mode="json", by_alias=True)


def step_view(step):
    task = step.get("task")
    survey = step.get("survey")
    return {
        "id": step["id"],
        "type": step["kind"],
        "title": step["title"],
        "unlock": step["unlock"],
        "taskVersion": (
            {"taskId": task["taskId"], "versionId": task["releaseId"]} if task else None
        ),
        "challenge": task.get("challenge") if task else None,
        "surveyId": survey["surveyId"] if survey else None,
        "required": survey["required"] if survey else True,
        "beforeSurveyId": task.get("beforeSurveyId") if task else None,
        "afterSurveyId": task.get("afterSurveyId") if task else None,
    }


def template_view(doc):
    # Archived steps are hidden from editors; their IDs stay listed for reference.
    return {
        "id": doc["_id"],
        "name": doc["title"],
        "description": doc["description"],
        "visibility": template_visibility(doc),
        "published": template_visibility(doc) == "published",
        "archived": template_visibility(doc) == "unlisted",
        "revision": doc["revision"],
        "pulseSurveys": doc.get("pulseSurveys", {"enabled": False}),
        "helpRequests": doc.get("helpRequests", {"enabled": False}),
        "updatedAt": doc["updatedAt"],
        "ownerId": doc["createdBy"],
        "createdAt": doc["createdAt"],
        "retiredStepIds": [s["id"] for s in doc["steps"] if s.get("archivedAt")],
        "steps": [step_view(s) for s in doc["steps"] if not s.get("archivedAt")],
    }


async def attach_steps(docs):
    """Adds `steps` in stepIds order; IDs without a step document are ignored."""
    ids = [d["_id"] for d in docs]
    by_template = {i: {} for i in ids}
    async for step in db.learning_path_template_steps.find({"templateId": {"$in": ids}}):
        by_template[step["templateId"]][step["_id"]] = {**step, "id": step["_id"]}
    for doc in docs:
        steps = by_template[doc["_id"]]
        doc["steps"] = [steps[i] for i in doc["stepIds"] if i in steps]
    return docs


async def template_document(template_id):
    doc = await db.learning_path_templates.find_one({"_id": str(template_id)})
    if not doc:
        raise not_found()
    return (await attach_steps([doc]))[0]


def run_step_id(run_id, step_id):
    return str(uuid5(UUID(str(run_id)), f"step:{step_id}"))


async def attach_states(run):
    """Adds `stepStates`: the run's personal progress documents."""
    run["stepStates"] = [
        s async for s in db.learning_path_run_steps.find({"runId": run["_id"]})
    ]
    return run


async def run_by_model(model_id, learner_id=None):
    """Returns (run, state) of the path step bound to a model, or None."""
    state = await db.learning_path_run_steps.find_one({"modelId": str(model_id)})
    if not state:
        return None
    filters = {"_id": state["runId"]}
    if learner_id is not None:
        filters["learnerId"] = learner_id
    run = await db.learning_path_runs.find_one(filters)
    if not run:
        return None
    return await attach_states(run), state


def step_state(run, step_id):
    return next((s for s in run["stepStates"] if s["stepId"] == str(step_id)), {})


async def ensure_step_state(run_id, step_id, now):
    fields = LearningPathStepState(
        runId=str(run_id), stepId=str(step_id), openedAt=now
    ).model_dump(by_alias=True, exclude_none=True)
    try:
        await db.learning_path_run_steps.update_one(
            {"_id": run_step_id(run_id, step_id)},
            {"$setOnInsert": fields},
            upsert=True,
        )
    except DuplicateKeyError:
        pass


async def update_step_state(run_id, step_id, fields, guards=None):
    return await db.learning_path_run_steps.update_one(
        {"_id": run_step_id(run_id, step_id), **(guards or {})},
        {"$set": fields},
    )


def session_reference_field(phase=None):
    return f"{phase}Survey" if phase else "surveySessionId"


async def link_survey_session(run_id, step_id, session_id, phase=None):
    await update_step_state(
        run_id, step_id, {session_reference_field(phase): str(session_id)}
    )


async def run_sessions(run):
    fields = ("surveySessionId", "beforeSurvey", "afterSurvey")
    ids = {
        state[field]
        for state in run["stepStates"]
        for field in fields
        if state.get(field)
    }
    sessions = {
        s["_id"]: s async for s in db.survey_sessions.find({"_id": {"$in": list(ids)}})
    }
    releases = {
        v["_id"]: v["surveyId"]
        async for v in db.survey_versions.find(
            {"_id": {"$in": list({s["releaseId"] for s in sessions.values()})}},
            {"surveyId": 1},
        )
    }
    # surveyId is derived for matching the current template, never stored in a session.
    return {
        sid: {**session, "surveyId": releases.get(session["releaseId"])}
        for sid, session in sessions.items()
    }


def linked_session(state, reference, sessions, phase=None):
    if not reference:
        return None
    session = sessions.get(state.get(session_reference_field(phase)))
    return session if session and session["surveyId"] == reference["surveyId"] else None
