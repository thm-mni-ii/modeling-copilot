"""Live learning-path views and commands; configuration belongs to templates."""

from datetime import timedelta
from uuid import UUID, uuid5, NAMESPACE_URL

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import ApiError, conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import list_page, new_id, utcnow
from modeling_api.schemas.learning_paths import SaveTemplate, PathModelContext
from modeling_api.schemas.challenges import ChallengeConfig, StartStep
from modeling_api.schemas.models import CreateModel, CreateModelVersion
from modeling_api.schemas.learning_path_documents import LearningPathRunFields
from modeling_api.services import models, tasks, surveys, survey_sessions
from modeling_api.services.learning_path_store import (
    step_document,
    template_meta,
    template_view,
    template_document,
    attach_steps,
    attach_states,
    run_by_model,
    step_view,
    step_state,
    ensure_step_state,
    update_step_state,
    link_survey_session,
    run_sessions,
    linked_session,
    session_reference_field,
)


def require_admin(user):
    if not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "Administrator access is required.")


async def list_templates(user, skip=0, limit=100):
    filters = {} if user.is_admin else {"status": "published"}
    page = await list_page(db.learning_path_templates, filters, skip, limit)
    docs = [
        {"_id": item["id"], **{k: v for k, v in item.items() if k != "id"}}
        for item in page["items"]
    ]
    page["items"] = [template_view(doc) for doc in await attach_steps(docs)]
    return page


async def get_template(template_id, user, existing_run=False):
    doc = await template_document(template_id)
    if not user.is_admin and not existing_run and doc["status"] != "published":
        raise not_found()
    return template_view(doc)


async def save_template(body: SaveTemplate, user, template_id=None):
    require_admin(user)
    is_new = template_id is None
    for survey_id in body.pulse_surveys.survey_ids:
        await surveys.render(survey_id, user, "use")
    for step in body.steps:
        for survey_id in (step.survey_id, step.before_survey_id, step.after_survey_id):
            if survey_id:
                await surveys.render(survey_id, user, "use")
        if step.type == "survey":
            continue
        await tasks.ensure_release_reference(
            step.task_version.task_id, step.task_version.version_id, user
        )
        if body.published and not body.archived:
            task = await db.task.find_one(
                {
                    "_id": str(step.task_version.task_id),
                    "visibility": "published",
                    "archivedAt": None,
                }
            )
            if not task:
                raise conflict("Published paths require accessible, published tasks.")
    now = utcnow()
    template_id = str(template_id) if template_id else new_id()
    old = None
    if not is_new:
        old = await template_document(template_id)
        if body.revision != old["revision"]:
            raise conflict("The template changed. Reload it before saving.")
    existing = {s["id"]: s for s in old["steps"]} if old else {}
    new_ids = [str(s.id) for s in body.steps]
    foreign = await db.learning_path_template_steps.find_one(
        {"_id": {"$in": new_ids}, "templateId": {"$ne": template_id}}, {"_id": 1}
    )
    if foreign:
        raise conflict("A step ID already belongs to another template.")
    for step in body.steps:
        previous = existing.get(str(step.id))
        if previous and (
            previous["kind"] != step.type
            or (
                step.type == "task"
                and previous["task"]["taskId"] != str(step.task_version.task_id)
            )
            or (
                step.type == "survey"
                and previous["survey"]["surveyId"] != str(step.survey_id)
            )
        ):
            raise conflict(
                "Changing a station's activity requires a new step ID. Add a new station instead."
            )
    # Steps missing from the body are archived, never deleted; they keep their ID.
    removed = [i for i, s in existing.items() if i not in new_ids and not s.get("archivedAt")]
    archived = [i for i, s in existing.items() if i not in new_ids and s.get("archivedAt")]
    meta = template_meta(body, new_ids + removed + archived)
    if is_new:
        await db.learning_path_templates.insert_one(
            {
                "_id": template_id,
                **meta,
                "revision": 1,
                "createdBy": user.id,
                "createdAt": now,
                "updatedAt": now,
            }
        )
    else:
        # The revision guard comes first so a stale editor writes no steps.
        result = await db.learning_path_templates.update_one(
            {"_id": template_id, "revision": body.revision},
            {"$set": {**meta, "updatedAt": now}, "$inc": {"revision": 1}},
        )
        if not result.matched_count:
            raise conflict()
    for step in body.steps:
        await db.learning_path_template_steps.update_one(
            {"_id": str(step.id)},
            {
                "$set": {
                    **step_document(step, template_id),
                    "archivedAt": None,
                    "updatedAt": now,
                },
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )
    if removed:
        await db.learning_path_template_steps.update_many(
            {"_id": {"$in": removed}},
            {"$set": {"archivedAt": now, "updatedAt": now}},
        )
    if body.help_requests.enabled:
        from modeling_api.services.help_questionnaire import publish

        await publish(template_id, body.name, 1 if is_new else body.revision + 1, body.help_requests, user.id)
    return await get_template(template_id, user)


async def start_run(template_id, user):
    template = await template_document(template_id)
    if template["status"] != "published":
        raise conflict("This template is not available for new runs.")
    run_id = str(uuid5(NAMESPACE_URL, f"learning-path:{user.id}:{template_id}"))
    try:
        await db.learning_path_runs.update_one(
            {"_id": run_id},
            {
                "$setOnInsert": LearningPathRunFields(
                    learnerId=user.id,
                    templateId=str(template_id),
                    createdAt=utcnow(),
                ).model_dump(by_alias=True)
            },
            upsert=True,
        )
    except DuplicateKeyError:
        pass
    return await get_run(run_id, user)


async def owned_run(run_id, user):
    run = await db.learning_path_runs.find_one(
        {"_id": str(run_id), "learnerId": user.id}
    )
    if not run:
        raise not_found()
    return await attach_states(run)


async def step_context(run_id, step_id, user, require_available=False):
    run = await owned_run(run_id, user)
    template = await template_document(run["templateId"])
    step = next((s for s in template["steps"] if s["id"] == str(step_id)), None)
    state = step_state(run, step_id)
    # Archived steps stay reachable only for learners who already opened them.
    if not step or (step.get("archivedAt") and not state.get("openedAt")):
        raise not_found()
    if require_available and not state.get("openedAt"):
        states = {s["stepId"]: s for s in run["stepStates"]}
        if not unlock_status(step, template, states, run, utcnow())[0]:
            raise conflict("This station is locked.")
    return run, template, step, state


def survey_reference(step, phase=None, state=None):
    if phase is None:
        return step.get("survey")
    survey_id = step.get("task", {}).get(f"{phase}SurveyId")
    return {"surveyId": survey_id} if survey_id else None


def survey_done(state, reference, sessions, phase=None):
    session = linked_session(state, reference, sessions, phase)
    return not reference or bool(session and session["status"] == "submitted")


async def mark_survey_step_completed(run_id, step_id, session):
    await update_step_state(
        run_id,
        step_id,
        {"completedAt": session["completedAt"]},
        {"completedAt": None},
    )


def is_optional(step):
    return step["kind"] == "survey" and not step["survey"]["required"]


def challenge_view(step, state):
    config = step.get("task", {}).get("challenge")
    started = state.get("challengeStartedAt")
    if not config or not started:
        return None
    duration = config.get("durationSeconds")
    return {
        "config": config,
        "startedAt": started,
        "endsAt": (
            started + timedelta(seconds=duration) if duration is not None else None
        ),
        "stoppedAt": state.get("challengeStoppedAt"),
    }


def unlock_status(step, template, states, run, now):
    """Returns (unlocked, reasons, available_at) for a step nobody opened yet."""
    unlock = step["unlock"]
    if unlock["mode"] == "sequence":
        for earlier in template["steps"]:
            if earlier["id"] == step["id"]:
                break
            if earlier.get("archivedAt") or is_optional(earlier):
                continue
            if not states.get(earlier["id"], {}).get("completedAt"):
                return False, [f"Complete {earlier['title']} first"], None
        return True, [], None
    titles = {s["id"]: s["title"] for s in template["steps"]}
    # Archived steps never block, unless the learner already completed them.
    ignored = {
        s["id"]
        for s in template["steps"]
        if s.get("archivedAt") and not states.get(s["id"], {}).get("completedAt")
    }
    conditions = [c for c in unlock["conditions"] if c.get("stepId") not in ignored]
    results = [evaluate_condition(c, states, run, now) for c in conditions]
    unlocked = not results or (
        all(r[0] for r in results)
        if unlock["mode"] == "all"
        else any(r[0] for r in results)
    )
    if unlocked:
        return True, [], None
    reasons = [
        r[1] + (f" ({titles[c['stepId']]})" if c.get("stepId") in titles else "")
        for c, r in zip(conditions, results)
        if not r[0]
    ]
    dates = [r[2] for r in results if not r[0] and r[2]]
    available_at = (
        (max(dates) if unlock["mode"] == "all" else min(dates)) if dates else None
    )
    return False, reasons, available_at


def evaluate_condition(condition, states, run, now):
    source = states.get(condition.get("stepId"), {})
    kind = condition["type"]
    if kind == "completed":
        ok = bool(source.get("completedAt"))
        return ok, "Complete the prerequisite activity first", None
    if kind == "score":
        # Intentionally unconnected: only a future trusted scoring adapter may satisfy this.
        return (
            False,
            f"A score of at least {condition['value']:g}% is required (scoring is not connected yet)",
            None,
        )
    if kind == "at":
        from datetime import datetime

        target = datetime.fromisoformat(condition["at"].replace("Z", "+00:00"))
    else:
        base = (
            source.get("completedAt") if condition.get("stepId") else run["createdAt"]
        )
        if not base:
            return (
                False,
                "The delay starts after the prerequisite task is completed",
                None,
            )
        target = base + timedelta(seconds=condition["seconds"])
    return now >= target, f"Available from {target.isoformat()}", target


async def run_coin_balance(run, template):
    active_steps = {step["id"] for step in template["steps"] if not step.get("archivedAt")}
    completed = sum(
        1 for state in run["stepStates"]
        if state["stepId"] in active_steps and state.get("completedAt")
    )
    # One unique answered reaction per offer makes rewards durable and idempotent.
    pulse_coins = await db.learning_path_pulse_events.count_documents(
        {"runId": run["_id"], "event": "answered"}
    )
    return completed + pulse_coins


async def get_run(run_id, user):
    run = await owned_run(run_id, user)
    template = await template_document(run["templateId"])
    sessions = await run_sessions(run)
    states = {s["stepId"]: s for s in run["stepStates"]}
    now = utcnow()
    steps = []
    counted = []
    for step in template["steps"]:
        state = states.get(step["id"], {})
        archived = bool(step.get("archivedAt"))
        if archived and not state.get("openedAt"):
            continue
        unlocked, reasons, available_at = unlock_status(
            step, template, states, run, now
        )
        available = unlocked or bool(state.get("openedAt"))
        session = linked_session(state, survey_reference(step), sessions)
        skipped = (
            session
            and session["status"] == "skipped"
            and not step["survey"]["required"]
        )
        status = (
            "completed"
            if state.get("completedAt")
            else (
                "skipped"
                if skipped
                else (
                    "in_progress"
                    if state.get("openedAt")
                    else "available" if available else "locked"
                )
            )
        )
        steps.append(
            {
                **step_view(step),
                "status": status,
                "modelId": state.get("modelId"),
                "completedAt": state.get("completedAt"),
                "reasons": [] if available else reasons,
                "availableAt": None if available else available_at,
            }
        )
        # Archived steps stay visible when begun but never count towards progress.
        if not archived:
            counted.append(status)
    completed = counted.count("completed")
    skipped = counted.count("skipped")
    finished = bool(counted) and completed + skipped == len(counted)
    first_finished_at = run.get("firstFinishedAt")
    if finished and not first_finished_at:
        first_finished_at = now
        await db.learning_path_runs.update_one(
            {"_id": run["_id"], "firstFinishedAt": None},
            {"$set": {"firstFinishedAt": now}},
        )
    return {
        "id": run["_id"],
        "ownerId": run["learnerId"],
        "templateId": run["templateId"],
        "createdAt": run["createdAt"],
        "firstFinishedAt": first_finished_at,
        "templateRevision": template["revision"],
        "name": template["title"],
        "description": template["description"],
        "steps": steps,
        "completed": completed,
        "coins": await run_coin_balance(run, template),
        "total": len(counted),
        "skipped": skipped,
        "progress": (
            round(100 * (completed + skipped) / len(counted)) if counted else 0
        ),
        "finished": finished,
    }


async def list_runs(user, skip=0, limit=100):
    page = await list_page(db.learning_path_runs, {"learnerId": user.id}, skip, limit)
    page["items"] = [await get_run(run["id"], user) for run in page["items"]]
    return page


async def start_step(run_id, step_id, user, body: StartStep | None = None):
    run, template, step, state = await step_context(
        run_id, step_id, user, require_available=True
    )
    if step["kind"] != "task":
        raise conflict("Use the questionnaire endpoint.")
    if not state.get("modelId"):
        configured = (
            ChallengeConfig.model_validate(step["task"]["challenge"])
            if step["task"].get("challenge")
            else None
        )
        if configured != (body.acknowledged_challenge if body else None):
            raise conflict(
                "Challenge settings require acknowledgement. Reload the path and review them before starting."
            )
        await tasks.ensure_release_reference(
            UUID(step["task"]["taskId"]), UUID(step["task"]["releaseId"]), user
        )
        now = utcnow()
        await ensure_step_state(run_id, step_id, now)
        await update_step_state(
            run_id,
            step_id,
            {
                "modelId": str(uuid5(UUID(str(run_id)), str(step_id))),
                "challengeStartedAt": (
                    now if not survey_reference(step, "before") else None
                ),
            },
            {"modelId": None},
        )
    run = await owned_run(run_id, user)
    state = step_state(run, step_id)
    model_id = state["modelId"]
    fields = models.model_fields(
        CreateModel(
            name=step["title"],
            taskVersion={
                "taskId": step["task"]["taskId"],
                "versionId": step["task"]["releaseId"],
            },
        ),
        user,
    )
    try:
        await db.models.update_one(
            {"_id": model_id},
            {"$setOnInsert": {**fields, "createdAt": utcnow()}},
            upsert=True,
        )
    except DuplicateKeyError:
        pass
    model = await models.get_model(UUID(model_id), user)
    if not model["latestVersionId"]:
        ref = model["taskVersion"]
        release = await tasks.ensure_release_reference(
            UUID(ref["taskId"]), UUID(ref["versionId"]), user
        )
        xml = '<GraphDataModel><root><Cell id="0"><Object as="style"/></Cell><Cell id="1" parent="0"><Object as="style"/></Cell><Cell id="2" parent="0"><Object as="style"/></Cell></root></GraphDataModel>'
        try:
            await models.create_version(
                UUID(model_id),
                CreateModelVersion(
                    baseVersionId=None,
                    taskVersion=ref,
                    workspaceLanguages=release.get("workspaceLanguages", []),
                    kind="release",
                    releaseName="Initial",
                    data={
                        "format": "maxgraph-xml",
                        "version": 1,
                        "xml": xml,
                        "name": model["name"],
                    },
                ),
                user,
            )
        except ApiError as exc:
            if (
                exc.status != 409
                or not (await models.get_model(UUID(model_id), user))["latestVersionId"]
            ):
                raise
    return {"modelId": model_id}


async def complete_step(run_id, step_id, user):
    run, template, step, state = await step_context(
        run_id, step_id, user, require_available=True
    )
    if state.get("completedAt"):
        return await get_run(run_id, user)
    sessions = await run_sessions(run)
    if step["kind"] == "task":
        if not state.get("modelId"):
            raise conflict("Start the task before completing it.")
        model = await models.get_model(UUID(state["modelId"]), user)
        if not model.get("latestVersionId"):
            raise conflict("Finish opening the task before completing it.")
        if not survey_done(
            state, survey_reference(step, "before", state), sessions, "before"
        ):
            raise conflict("Complete the questionnaire before working on the task.")
        await update_step_state(
            run_id, step_id, {"workSubmittedAt": utcnow()}, {"workSubmittedAt": None}
        )
        if not survey_done(state, survey_reference(step, "after"), sessions, "after"):
            return await get_run(run_id, user)
    else:
        reference = survey_reference(step)
        if not survey_done(state, reference, sessions):
            raise conflict("Submit the questionnaire before completing this station.")
        await mark_survey_step_completed(
            run_id, step_id, linked_session(state, reference, sessions)
        )
        return await get_run(run_id, user)
    await update_step_state(
        run_id, step_id, {"completedAt": utcnow()}, {"completedAt": None}
    )
    return await get_run(run_id, user)


async def get_model_context(model_id, user):
    model = await models.get_model(UUID(str(model_id)), user)
    found = await run_by_model(model_id, user.id)
    if not found:
        return None
    run, state = found
    template = await template_document(run["templateId"])
    step = next((s for s in template["steps"] if s["id"] == state["stepId"]), None)
    sessions = await run_sessions(run)
    context = {
        "id": str(uuid5(UUID(run["_id"]), state["stepId"])),
        "runId": run["_id"],
        "stepId": state["stepId"],
        "modelId": str(model_id),
        "title": step["title"] if step else model["name"],
        "coins": await run_coin_balance(run, template),
        "taskVersion": model["taskVersion"],
        "startedAt": state["openedAt"],
        "completedAt": state.get("completedAt"),
        "challenge": challenge_view(step, state) if step else None,
        "completionRequested": bool(state.get("workSubmittedAt")),
        "removed": step is None or bool(step.get("archivedAt")),
        "templateRevision": template["revision"],
    }
    for phase in ("before", "after"):
        assigned = survey_reference(step, phase, state) if step else None
        context[f"{phase}Survey"] = (
            {
                "surveyId": assigned["surveyId"],
                "completed": survey_done(state, assigned, sessions, phase),
            }
            if assigned
            else None
        )
    context["helpRequests"] = template.get("helpRequests", {"enabled": False})
    return PathModelContext.model_validate(context)


async def resume_step(run_id, step_id, user):
    run, template, step, state = await step_context(
        run_id, step_id, user, require_available=True
    )
    if step["kind"] != "task" or not state.get("modelId"):
        raise not_found()
    sessions = await run_sessions(run)
    if survey_done(
        state, survey_reference(step, "before", state), sessions, "before"
    ):
        await update_step_state(
            run_id,
            step_id,
            {"challengeStartedAt": utcnow()},
            {"challengeStartedAt": None},
        )
        if state.get("workSubmittedAt"):
            await complete_step(run_id, step_id, user)
    return await get_model_context(state["modelId"], user)


async def stop_time_challenge(run_id, step_id, user):
    run, template, step, state = await step_context(run_id, step_id, user)
    attempt = challenge_view(step, state)
    if not attempt or attempt["config"]["type"] != "time":
        raise conflict("This step has no active time challenge.")
    await models.ensure_task_questionnaire_completed(state["modelId"])
    now = utcnow()
    if attempt["endsAt"] > now:
        await update_step_state(
            run_id, step_id, {"challengeStoppedAt": now}, {"challengeStoppedAt": None}
        )
    return await get_model_context(state["modelId"], user)


async def survey_context(run_id, step_id, user, phase=None):
    run, template, step, state = await step_context(
        run_id, step_id, user, require_available=True
    )
    assignment = survey_reference(step, phase, state)
    if not assignment:
        raise not_found()
    if phase:
        if not state.get("modelId"):
            raise conflict("Start the task before opening its questionnaire.")
        if phase == "after":
            sessions = await run_sessions(run)
            if not survey_done(
                state, survey_reference(step, "before", state), sessions, "before"
            ) or not state.get("workSubmittedAt"):
                raise conflict(
                    "Finish the modeling task before opening its final questionnaire."
                )
    return run, step, state, assignment


async def open_survey(run_id, step_id, user, phase=None):
    run, step, state, reference = await survey_context(run_id, step_id, user, phase)
    await ensure_step_state(run_id, step_id, utcnow())
    required = True if phase else step["survey"]["required"]
    session, changed = await survey_sessions.open_path_session(
        run_id, step_id, reference["surveyId"], phase, required, user
    )
    # Confirm the reference is still current before linking it into the station.
    _, _, _, current = await survey_context(run_id, step_id, user, phase)
    if current["surveyId"] != reference["surveyId"]:
        raise conflict(
            "The questionnaire changed. Reopen the station before continuing."
        )
    await link_survey_session(run_id, step_id, session["_id"], phase)
    if phase and session["status"] == "submitted":
        await resume_step(run_id, step_id, user)
    version = await survey_sessions.release(session["releaseId"])
    return {
        "version": {
            "id": version["_id"],
            **{k: v for k, v in version.items() if k != "_id"},
        },
        "answers": session["answers"],
        "revision": session["revision"],
        "sessionId": session["_id"],
        "releaseChanged": changed,
        "status": session["status"],
    }


async def save_survey_session(run_id, step_id, body, user, action, phase=None):
    if phase and phase.startswith("pulse:"):
        from modeling_api.services import pulse_surveys

        try:
            offer_id = UUID(phase.removeprefix("pulse:"))
        except ValueError:
            raise not_found()
        return await pulse_surveys.save(run_id, step_id, offer_id, body, user, action)
    if phase not in (None, "before", "after"):
        raise not_found()
    run, step, state, reference = await survey_context(run_id, step_id, user, phase)
    if state.get(session_reference_field(phase)) != str(body.session_id):
        raise conflict(
            "The questionnaire changed. Reopen the station before continuing."
        )
    session = await db.survey_sessions.find_one(
        {"_id": str(body.session_id), "userId": user.id}
    )
    if not session:
        raise not_found()
    version = await survey_sessions.release(session["releaseId"])
    if version["surveyId"] != reference["surveyId"]:
        raise conflict(
            "The questionnaire changed. Reopen the station before continuing."
        )
    required = True if phase else step["survey"]["required"]
    session = await survey_sessions.save(session, body, action, required)
    if action == "submit":
        if phase:
            await resume_step(run_id, step_id, user)
        else:
            await mark_survey_step_completed(run_id, step_id, session)
        return survey_sessions.response_view(session, version)
    return {"revision": session["revision"]}
