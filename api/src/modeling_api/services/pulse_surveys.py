"""Server-controlled pulse offers and append-only reactions."""

from contextlib import asynccontextmanager
from datetime import timedelta
from math import ceil
from random import Random, SystemRandom
from uuid import UUID, uuid5

from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import new_id, utcnow
from modeling_api.schemas.learning_paths import PulseSurveyConfig
from modeling_api.services import learning_paths as paths, survey_sessions
from modeling_api.services.learning_path_store import run_sessions


def session_id(offer):
    return str(
        uuid5(
            UUID(offer["runId"]),
            f"{offer['stepId']}:pulse:{offer['_id']}:{offer['surveyId']}",
        )
    )


@asynccontextmanager
async def run_lock(run_id, user):
    # Serialize across steps and tabs so session/task limits and reactions agree.
    await paths.owned_run(run_id, user)
    now, token = utcnow(), new_id()
    result = await db.learning_path_runs.update_one(
        {
            "_id": str(run_id), "learnerId": user.id,
            "$or": [
                {"pulseLock": {"$exists": False}},
                {"pulseLock.until": {"$lte": now}},
            ],
        },
        {"$set": {"pulseLock": {"token": token, "until": now + timedelta(seconds=60)}}},
    )
    if not result.matched_count:
        raise conflict("Another pulse request is running. Please try again.")
    try:
        yield
    finally:
        await db.learning_path_runs.update_one(
            {"_id": str(run_id), "pulseLock.token": token}, {"$unset": {"pulseLock": ""}}
        )


async def reaction(offer):
    return await db.learning_path_pulse_events.find_one(
        {"offerId": offer["_id"], "reaction": True}
    )


async def record_reaction(offer, event, at=None):
    existing = await reaction(offer)
    if existing:
        return existing
    document = {
        "_id": new_id(), "offerId": offer["_id"], "reaction": True,
        "runId": offer["runId"], "stepId": offer["stepId"],
        "surveyId": offer["surveyId"], "sessionKey": offer["sessionKey"],
        "offerSeq": offer["offerSeq"], "event": event, "at": at or utcnow(),
    }
    if event == "expired":
        document["reason"] = "not_clicked"
    try:
        await db.learning_path_pulse_events.insert_one(document)
    except DuplicateKeyError:
        return await reaction(offer)
    return document


async def reconcile(run_id):
    # A request can stop after saving a submission but before appending its event.
    # Reconcile before evaluating limits; deterministic session IDs make this safe.
    # Only the latest offer of each step can still be outstanding.
    cursor = await db.learning_path_pulse_events.aggregate([
        {"$match": {"runId": str(run_id), "event": "offered"}},
        {"$sort": {"offerSeq": -1}},
        {"$group": {"_id": "$stepId", "offer": {"$first": "$$ROOT"}}},
    ])
    async for item in cursor:
        offer = item["offer"]
        if await reaction(offer):
            continue
        session = await db.survey_sessions.find_one(
            {"_id": session_id(offer), "status": "submitted"}
        )
        if session:
            await record_reaction(offer, "answered", session["completedAt"])


async def eligible(run_id, step_id, user):
    run, template, step, state = await paths.step_context(run_id, step_id, user)
    config = PulseSurveyConfig.model_validate(template.get("pulseSurveys", {}))
    allowed = (
        config.enabled and step["kind"] == "task"
        and state.get("openedAt") and state.get("modelId")
        and not state.get("completedAt") and not state.get("workSubmittedAt")
        and not step.get("archivedAt")
        and str(step_id) not in map(str, config.exclude_step_ids)
    )
    return run, step, state, config, bool(allowed)


async def questionnaires_clear(run, step, state):
    sessions = await run_sessions(run)
    return paths.survey_done(
        state, paths.survey_reference(step, "before", state), sessions, "before"
    ) and not state.get("workSubmittedAt")


def offer_view(offer):
    return {"offer": {"id": offer["_id"], "surveyId": offer["surveyId"]}}


async def poll(run_id, step_id, body, user):
    async with run_lock(run_id, user):
        run, step, state, config, allowed = await eligible(run_id, step_id, user)
        if not allowed:
            return {"offer": None}
        now = utcnow()
        previous_poll = state.get("pulseLastPollAt", state["openedAt"])
        elapsed = max(0, int((now - previous_poll).total_seconds()))
        delta = min(body.active_seconds_delta, 30, elapsed)
        await db.learning_path_run_steps.update_one(
            {"_id": state["_id"]},
            {"$inc": {"activeSeconds": delta}, "$set": {"pulseLastPollAt": now}},
        )
        if state.get("activeSeconds", 0) + delta < config.min_active_seconds:
            remaining = config.min_active_seconds - state.get("activeSeconds", 0) - delta
            return {"offer": None, "nextPollSeconds": min(30, max(1, remaining))}
        if not await questionnaires_clear(run, step, state):
            return {"offer": None}
        await reconcile(run_id)
        query = {"runId": str(run_id), "stepId": str(step_id)}
        last_offer = await db.learning_path_pulse_events.find_one(
            {**query, "event": "offered"}, sort=[("offerSeq", -1)]
        )
        if last_offer and not await reaction(last_offer):
            # An outstanding offer survives sessions, tab switches and quota changes.
            return offer_view(last_offer)
        seq = last_offer["offerSeq"] + 1 if last_offer else 1
        last_event = await db.learning_path_pulse_events.find_one(query, sort=[("at", -1)])
        if last_event:
            seed = f"{run_id}:{step_id}:{seq}:{last_event['_id']}"
            gap = Random(seed).randint(
                config.min_gap_seconds, config.max_gap_seconds or config.min_gap_seconds
            )
            remaining = (last_event["at"] + timedelta(seconds=gap) - now).total_seconds()
            if remaining > 0:
                return {"offer": None, "nextPollSeconds": min(30, max(1, ceil(remaining)))}
        answered = {"runId": str(run_id), "event": "answered"}
        if config.max_per_task is not None:
            task_answers = await db.learning_path_pulse_events.count_documents(
                {**answered, "stepId": str(step_id)}
            )
            if task_answers >= config.max_per_task:
                return {"offer": None}
        if await db.learning_path_pulse_events.count_documents(
            {**answered, "sessionKey": str(body.session_key)}
        ) >= config.max_per_session:
            return {"offer": None}
        offer = {
            "_id": new_id(), **query, "event": "offered", "at": now,
            "offerSeq": seq, "sessionKey": str(body.session_key),
            "surveyId": str(SystemRandom().choice(config.survey_ids)),
        }
        try:
            await db.learning_path_pulse_events.insert_one(offer)
        except DuplicateKeyError:
            offer = await db.learning_path_pulse_events.find_one(
                {**query, "event": "offered", "offerSeq": seq}
            )
        return offer_view(offer)


async def get_offer(run_id, offer_id):
    offer = await db.learning_path_pulse_events.find_one(
        {"_id": str(offer_id), "runId": str(run_id), "event": "offered"}
    )
    if not offer:
        raise not_found()
    return offer


async def open_offer(run_id, offer_id, user):
    async with run_lock(run_id, user):
        offer = await get_offer(run_id, offer_id)
        run, step, state, config, allowed = await eligible(run_id, offer["stepId"], user)
        if not allowed or not await questionnaires_clear(run, step, state):
            raise conflict("This pulse questionnaire is no longer available.")
        await reconcile(run_id)
        closed = await reaction(offer)
        if closed and closed["event"] in ("dismissed", "expired"):
            raise conflict("This pulse is already closed.")
        session, changed = await survey_sessions.open_path_session(
            run_id, offer["stepId"], offer["surveyId"], f"pulse:{offer_id}", True, user
        )
        version = survey_sessions.version_for_session(
            await survey_sessions.release(session["releaseId"]), session
        )
        return {
            "version": {
                "id": version["_id"],
                **{k: v for k, v in version.items() if k != "_id"},
            },
            "answers": session["answers"], "revision": session["revision"],
            "sessionId": session["_id"], "releaseChanged": changed,
            "status": session["status"],
        }


async def dismiss(run_id, offer_id, user):
    async with run_lock(run_id, user):
        offer = await get_offer(run_id, offer_id)
        await reconcile(run_id)
        closed = await record_reaction(offer, "dismissed")
        return {"event": closed["event"]}


async def expire(run_id, offer_id, user):
    async with run_lock(run_id, user):
        offer = await get_offer(run_id, offer_id)
        await reconcile(run_id)
        closed = await reaction(offer)
        if closed:
            return {"event": closed["event"]}
        # Opening and expiry share the run lock: a clicked offer cannot expire.
        session = await db.survey_sessions.find_one({"_id": session_id(offer)})
        if session:
            return {"event": "opened"}
        if utcnow() < offer["at"] + timedelta(seconds=40):
            raise conflict("This pulse has not expired yet.")
        closed = await record_reaction(offer, "expired")
        return {"event": closed["event"]}


async def save(run_id, step_id, offer_id, body, user, action):
    async with run_lock(run_id, user):
        offer = await get_offer(run_id, offer_id)
        if offer["stepId"] != str(step_id) or str(body.session_id) != session_id(offer):
            raise not_found()
        await reconcile(run_id)
        closed = await reaction(offer)
        if closed and closed["event"] in ("dismissed", "expired"):
            raise conflict("This pulse is already closed.")
        session = await db.survey_sessions.find_one(
            {"_id": session_id(offer), "userId": user.id}
        )
        if not session:
            raise not_found()
        if not closed:
            run, step, state, config, allowed = await eligible(run_id, step_id, user)
            if not allowed or not await questionnaires_clear(run, step, state):
                raise conflict("This pulse questionnaire is no longer available.")
        session = await survey_sessions.save(session, body, action, True)
        if action == "submit":
            await record_reaction(offer, "answered", session["completedAt"])
            version = await survey_sessions.release(session["releaseId"])
            run = await paths.get_run(run_id, user)
            return {
                **survey_sessions.response_view(session, version),
                "rewardCoins": 1,
                "coinBalance": run["coins"],
            }
        return {"revision": session["revision"]}
