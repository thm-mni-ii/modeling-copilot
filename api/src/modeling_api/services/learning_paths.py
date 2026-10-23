"""Learning paths use live templates and persistent, owner-scoped progress."""

from datetime import timedelta
from uuid import UUID, uuid5, NAMESPACE_URL

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import ApiError, conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import insert, list_page, to_api, utcnow
from modeling_api.schemas.learning_paths import SaveTemplate, StepRunContext
from modeling_api.schemas.challenges import ChallengeConfig, StartStep
from modeling_api.schemas.models import CreateModel, CreateModelVersion
from modeling_api.services import models, tasks


def require_admin(user):
    if not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "Administrator access is required.")


async def list_templates(user, skip=0, limit=100):
    filters = {} if user.is_admin else {"published": True, "archived": False}
    return await list_page(db.learning_path_templates, filters, skip, limit)


async def get_template(template_id, user, existing_run=False):
    doc = await db.learning_path_templates.find_one({"_id": str(template_id)})
    if not doc or (
        not user.is_admin
        and not existing_run
        and (not doc["published"] or doc["archived"])
    ):
        raise not_found()
    return to_api(doc)


async def save_template(body: SaveTemplate, user, template_id=None):
    require_admin(user)
    for step in body.steps:
        await tasks.ensure_release_reference(
            step.task_version.task_id, step.task_version.version_id, user
        )
        if body.published:
            task = await db.task.find_one(
                {
                    "_id": str(step.task_version.task_id),
                    "visibility": "published",
                    "archivedAt": None,
                }
            )
            if not task:
                raise conflict("Published paths require accessible, published tasks.")
    fields = body.model_dump(mode="json", by_alias=True, exclude={"updated_at"})
    now = utcnow()
    fields["updatedAt"] = now.replace(microsecond=(now.microsecond // 1000) * 1000)
    if template_id is None:
        return await insert(db.learning_path_templates, {**fields, "ownerId": user.id})
    old = await get_template(template_id, user)
    if body.updated_at is None or body.updated_at != old["updatedAt"]:
        raise conflict()
    fields["updatedAt"] = max(
        fields["updatedAt"], old["updatedAt"] + timedelta(milliseconds=1)
    )
    # Removed steps stay in run records, but cannot be silently reassigned later.
    retired = set(old.get("retiredStepIds", [])) | (
        {s["id"] for s in old["steps"]} - {str(s.id) for s in body.steps}
    )
    if retired & {str(s.id) for s in body.steps}:
        raise conflict("A removed step ID cannot be reused. Add a new step instead.")
    result = await db.learning_path_templates.update_one(
        {"_id": str(template_id), "updatedAt": old["updatedAt"]},
        {"$set": {**fields, "retiredStepIds": sorted(retired)}},
    )
    if not result.matched_count:
        raise conflict()
    return await get_template(template_id, user)


async def start_run(template_id, user):
    template = await get_template(template_id, user)
    if not template["published"] or template["archived"]:
        raise conflict("This template is not available for new runs.")
    run_id = str(uuid5(NAMESPACE_URL, f"learning-path:{user.id}:{template_id}"))
    await db.learning_path_runs.update_one(
        {"_id": run_id},
        {
            "$setOnInsert": {
                "ownerId": user.id,
                "templateId": str(template_id),
                "createdAt": utcnow(),
            }
        },
        upsert=True,
    )
    return await get_run(run_id, user)


async def owned_run(run_id, user):
    run = await db.learning_path_runs.find_one({"_id": str(run_id), "ownerId": user.id})
    if not run:
        raise not_found()
    return run


def evaluate_condition(condition, states, run, now):
    source = states.get(condition.get("stepId"), {})
    kind = condition["type"]
    if kind == "completed":
        ok = bool(source.get("completedAt"))
        return ok, "Complete the prerequisite task first", None
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


async def get_run(run_id, user):
    run = await owned_run(run_id, user)
    template = await get_template(run["templateId"], user, existing_run=True)
    states = {
        s["stepId"]: s
        async for s in db.learning_path_step_runs.find({"runId": str(run_id)})
    }
    now = utcnow()
    titles = {s["id"]: s["title"] for s in template["steps"]}
    steps = []
    for step in template["steps"]:
        state = states.get(step["id"], {})
        results = [
            evaluate_condition(c, states, run, now)
            for c in step["unlock"]["conditions"]
        ]
        unlocked = not results or (
            all(r[0] for r in results)
            if step["unlock"]["mode"] == "all"
            else any(r[0] for r in results)
        )
        if unlocked and not state.get("unlockedAt"):
            await db.learning_path_step_runs.update_one(
                {"runId": str(run_id), "stepId": step["id"]},
                {
                    "$setOnInsert": {
                        "_id": str(uuid5(UUID(str(run_id)), step["id"])),
                        "runId": str(run_id),
                        "stepId": step["id"],
                    },
                    "$set": {"unlockedAt": now},
                },
                upsert=True,
            )
        available = unlocked or bool(state.get("unlockedAt") or state.get("modelId"))
        status = (
            "completed"
            if state.get("completedAt")
            else (
                "in_progress"
                if state.get("modelId")
                else "available" if available else "locked"
            )
        )
        dates = [r[2] for r in results if not r[0] and r[2]]
        steps.append(
            {
                **step,
                # Configuration shown on the board; the editor loads the full step run.
                "challenge": (
                    (state["challenge"]["config"] if state.get("challenge") else None)
                    if state.get("startedAt")
                    else step.get("challenge")
                ),
                "taskVersion": state.get("taskVersion", step["taskVersion"]),
                "status": status,
                "modelId": state.get("modelId"),
                "completedAt": state.get("completedAt"),
                "reasons": (
                    [
                        r[1]
                        + (
                            f" ({titles[c['stepId']]})"
                            if c.get("stepId") in titles
                            else ""
                        )
                        for c, r in zip(step["unlock"]["conditions"], results)
                        if not r[0]
                    ]
                    if not available
                    else []
                ),
                "availableAt": (
                    (max(dates) if step["unlock"]["mode"] == "all" else min(dates))
                    if dates
                    else None
                ),
            }
        )
    completed = sum(s["status"] == "completed" for s in steps)
    return {
        **to_api(run),
        "name": template["name"],
        "description": template["description"],
        "steps": steps,
        "completed": completed,
        "total": len(steps),
        "progress": round(100 * completed / len(steps)) if steps else 0,
    }


async def list_runs(user, skip=0, limit=100):
    page = await list_page(db.learning_path_runs, {"ownerId": user.id}, skip, limit)
    page["items"] = [await get_run(run["id"], user) for run in page["items"]]
    return page


async def start_step(run_id, step_id, user, body: StartStep | None = None):
    run = await get_run(run_id, user)
    step = next((s for s in run["steps"] if s["id"] == str(step_id)), None)
    if not step:
        raise not_found()
    if step["status"] == "locked":
        raise conflict("This step is locked.")
    # Stable model ID and atomic upsert make simultaneous starts idempotent.
    model_id = str(uuid5(UUID(str(run_id)), str(step_id)))
    state_filter = {"runId": str(run_id), "stepId": str(step_id)}
    state = await db.learning_path_step_runs.find_one(state_filter)
    if not state.get("startedAt"):
        configured = (
            ChallengeConfig.model_validate(step["challenge"])
            if step.get("challenge")
            else None
        )
        acknowledged = body.acknowledged_challenge if body else None
        if configured != acknowledged:
            raise conflict(
                "Challenge settings require acknowledgement. Reload the path and review them before starting."
            )
        reference = step["taskVersion"]
        await tasks.ensure_release_reference(
            UUID(reference["taskId"]), UUID(reference["versionId"]), user
        )
        now = utcnow()
        attempt = (
            {
                "config": configured.model_dump(mode="json", by_alias=True),
                "startedAt": now,
                "endsAt": (
                    now + timedelta(seconds=configured.duration_seconds)
                    if configured.duration_seconds is not None
                    else None
                ),
                "stoppedAt": None,
            }
            if configured
            else None
        )
        # Reserve membership before creating the model so it can never leak into model lists.
        await db.learning_path_step_runs.update_one(
            {**state_filter, "startedAt": None},
            {
                "$set": {
                    "modelId": model_id,
                    "title": step["title"],
                    "taskVersion": reference,
                    "startedAt": now,
                    "challenge": attempt,
                }
            },
        )
        state = await db.learning_path_step_runs.find_one(state_filter)
    model_id = state["modelId"]
    fields = models.model_fields(
        CreateModel(name=state["title"], taskVersion=state["taskVersion"]), user
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
    await owned_run(run_id, user)
    result = await db.learning_path_step_runs.update_one(
        {
            "runId": str(run_id),
            "stepId": str(step_id),
            "modelId": {"$ne": None},
            "completedAt": None,
        },
        {"$set": {"completedAt": utcnow()}},
    )
    if not result.matched_count:
        state = await db.learning_path_step_runs.find_one(
            {"runId": str(run_id), "stepId": str(step_id)}
        )
        if not state or not state.get("completedAt"):
            raise conflict("Start the task before completing it.")
    return await get_run(run_id, user)


async def get_step_run_for_model(model_id, user):
    await models.get_model(UUID(str(model_id)), user)
    state = await db.learning_path_step_runs.find_one({"modelId": str(model_id)})
    if state is None:
        return None
    await owned_run(state["runId"], user)
    return StepRunContext.model_validate(to_api(state))


async def stop_time_challenge(run_id, step_id, user):
    await owned_run(run_id, user)
    state = await db.learning_path_step_runs.find_one(
        {"runId": str(run_id), "stepId": str(step_id)}
    )
    if not state or not state.get("modelId"):
        raise not_found()
    attempt = state.get("challenge")
    if not attempt or attempt["config"]["type"] != "time":
        raise conflict("This step has no time challenge.")
    now = utcnow()
    await db.learning_path_step_runs.update_one(
        {
            "_id": state["_id"],
            "challenge.stoppedAt": None,
            "challenge.endsAt": {"$gt": now},
        },
        {"$set": {"challenge.stoppedAt": now}},
    )
    return await get_step_run_for_model(state["modelId"], user)
