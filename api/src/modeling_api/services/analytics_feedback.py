"""Staff analytics over attempts, help requests and pulse offers of one learning path.

An attempt is an evaluation of the model of a task step: evaluations.modelId equals the run step's
modelId, which is derived once from (run, step) when the task starts and never changes afterwards.
Failed and cancelled evaluations are no attempts. Scores come from the learner feedback stored with
the evaluation (best overall recognition across sample solutions); an evaluation whose feedback was
never loaded by the learner has no score yet.
"""

from collections import Counter, defaultdict
from statistics import mean

from modeling_api.core.errors import not_found
from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.services import analytics_paths
from modeling_api.services.evaluations import _feedback_projection, learner_score
from modeling_api.services.help_configuration import runtime_config
from modeling_api.services.learning_path_progress import require_access
from modeling_api.services.learning_path_store import template_document
from modeling_api.services.learning_paths import meets_completion_gate
from modeling_api.services.pulse_surveys import session_id as pulse_session_id

HELP_KINDS = ("help.check", "help.clarify", "help.next_step", "help.example", "help.solution", "recognition")
LIMITED_KINDS = ("help.example", "help.solution")
ATTEMPT_BINS = [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5"), (6, "6-10"), (11, "11+")]
SCORE_BANDS = ["0-25%", "25-50%", "50-75%", "75-100%"]
MAX_CURVE_ATTEMPT = 10
# (question name, help phase that submits it); answers of unsubmitted phases are drafts and ignored.
HELP_ANSWERS = (("support_need", "reflection"), ("next_action", "action"), ("stuck_duration", "reflection"))
NO_ATTEMPT = ("failed", "cancelled")
# Delivered and counted feedback consumes the quota; mirrors help_requests.usage.
DELIVERED = {"$and": [{"$ne": ["$feedbackCounted", False]}, {"$or": [
    {"$eq": ["$feedbackSucceeded", True]},
    {"$and": [
        {"$eq": [{"$type": "$feedbackSucceeded"}, "missing"]},
        {"$not": [{"$in": [{"$type": "$feedbackDelivered"}, ["missing", "null"]]}]},
    ]},
]}]}


def mean_or_none(values, digits=1):
    return round(mean(values), digits) if values else None


def percent(part, total):
    return round(part / total * 100, 1) if total else None


def attempt_bin(count):
    return [label for bound, label in ATTEMPT_BINS if count >= bound][-1]


def score_band(score):
    return SCORE_BANDS[min(int(score // 25), 3)]


def evaluation_result(evaluation, task):
    """(state, score, passed) of one evaluation; `passed` is None for steps without a completion gate."""
    feedback = evaluation.get("studentFeedback") or {}
    recognitions = [item.get("recognition") or {} for item in feedback.get("recognitions", [])]
    state = feedback.get("state") or evaluation.get("state", "unknown")
    passed = None
    if task.get("minimumScorePercent") is not None:
        passed = state == "succeeded" and any(meets_completion_gate(task, item) for item in recognitions)
    return state, learner_score(feedback), passed


async def started_models(template, run_ids=None):
    """Task steps, run ids and {modelId: (runId, stepId)} of the task steps the participants started."""
    tasks = {step["id"]: step for step in template["steps"] if step["kind"] == "task" and not step.get("archivedAt")}
    if run_ids is None:
        run_ids = [run["_id"] async for run in db.learning_path_runs.find({"templateId": template["_id"]}, {"_id": 1})]
    started = {}
    async for state in db.learning_path_run_steps.find(
        {"runId": {"$in": run_ids}, "modelId": {"$ne": None}}, {"runId": 1, "stepId": 1, "modelId": 1}
    ):
        if state["stepId"] in tasks:
            started[state["modelId"]] = (state["runId"], state["stepId"])
    return tasks, run_ids, started


async def collect(template, run_ids=None):
    """Task steps, per-run started steps, evaluations (as attempt rows) and help requests of a template."""
    tasks, run_ids, started = await started_models(template, run_ids)
    attempts = []
    async for evaluation in db.evaluations.find(
        {"modelId": {"$in": list(started)}},
        {"modelId": 1, "startedAt": 1, "state": 1, "helpRequestId": 1, "studentFeedback.state": 1,
         "studentFeedback.scorePercent": 1, "studentFeedback.recognitions": 1},
    ):
        run_id, step_id = started[evaluation["modelId"]]
        state, score, passed = evaluation_result(evaluation, tasks[step_id]["task"])
        attempts.append({
            "id": evaluation["_id"], "runId": run_id, "stepId": step_id, "at": evaluation["startedAt"],
            "state": state, "score": score, "passed": passed, "helpRequestId": evaluation.get("helpRequestId"),
            "counted": state not in NO_ATTEMPT,
        })
    attempts.sort(key=lambda row: row["at"])
    requests = await (await db.learning_path_help_requests.aggregate([
        {"$match": {"runId": {"$in": run_ids}}},
        {"$project": {
            "runId": 1, "stepId": 1, "stage": 1, "flowVersion": 1, "supportKind": 1, "createdAt": 1,
            "surveySessionId": 1, "delivered": DELIVERED,
        }},
        {"$sort": {"createdAt": 1}},
    ])).to_list(None)
    requests = [request for request in requests if request["stepId"] in tasks]
    return tasks, run_ids, list(started.values()), attempts, requests


def help_funnel(requests):
    """Reach per help-flow stage. Cancelling is only possible at the first question."""
    total = len(requests)
    cancelled = sum(request.get("stage") == "cancelled" for request in requests)
    completed = sum(request.get("stage", "completed") == "completed" for request in requests)
    return {
        "requests": total,
        "topicDone": sum(request.get("stage", "completed") not in ("topic", "cancelled") for request in requests),
        # Flow 2 asks for the marking after the reflection questions; flow 1 before them.
        "reflectionDone": sum(
            request.get("stage", "completed") in ("action", "completed")
            or (request.get("stage") == "marking" and request.get("flowVersion", 1) >= 2)
            for request in requests
        ),
        "completed": completed, "cancelled": cancelled, "open": total - completed - cancelled,
        "abortRate": percent(cancelled, total),
    }


def step_feedback(step, started, attempts, requests, config):
    persons = len({run_id for run_id, step_id in started if step_id == step["id"]})
    by_person = defaultdict(list)
    for row in attempts:
        if row["stepId"] == step["id"] and row["counted"]:
            by_person[row["runId"]].append(row)
    scored = {run_id: [row["score"] for row in rows if row["score"] is not None] for run_id, rows in by_person.items()}
    scored = {run_id: scores for run_id, scores in scored.items() if scores}
    distribution = Counter(attempt_bin(len(rows)) for rows in by_person.values())
    bands = Counter(score_band(max(scores)) for scores in scored.values())
    curve = defaultdict(list)
    for rows in by_person.values():
        for number, row in enumerate(rows[:MAX_CURVE_ATTEMPT], 1):
            if row["score"] is not None:
                curve[number].append(row["score"])
    gated = step["task"].get("minimumScorePercent") is not None
    passed = sum(any(row["passed"] for row in rows) for rows in by_person.values()) if gated else None
    own = [request for request in requests if request["stepId"] == step["id"]]
    delivered = Counter((request["runId"], request.get("supportKind")) for request in own if request["delivered"])
    limits = []
    for kind in LIMITED_KINDS:
        limit = getattr(config, f"{kind.removeprefix('help.')}_limit")
        # None means unlimited, so nobody can exhaust it.
        exhausted = None if limit is None else sum(
            1 for (_, delivered_kind), count in delivered.items() if delivered_kind == kind and count >= max(limit, 1)
        )
        limits.append({"kind": kind, "limit": limit, "exhausted": exhausted, "share": None if limit is None else percent(exhausted, persons)})
    return {
        "stepId": step["id"], "title": step["title"], "persons": persons,
        "attemptPersons": len(by_person), "attempts": sum(len(rows) for rows in by_person.values()),
        "avgAttempts": mean_or_none([len(rows) for rows in by_person.values()], 2),
        "attemptDistribution": [{"label": label, "users": distribution[label]} for _, label in ATTEMPT_BINS],
        "minimumScorePercent": step["task"].get("minimumScorePercent"),
        "passedPersons": passed, "passedShare": percent(passed, len(by_person)) if gated else None,
        "scoredPersons": len(scored),
        "avgFirstScore": mean_or_none([scores[0] for scores in scored.values()]),
        "avgBestScore": mean_or_none([max(scores) for scores in scored.values()]),
        "scoreBands": [{"label": label, "users": bands[label]} for label in SCORE_BANDS],
        "scoreCurve": [{"attempt": number, "avgScore": mean_or_none(curve[number]), "scored": len(curve[number])} for number in sorted(curve)],
        "support": [{
            "kind": kind,
            "persons": len({request["runId"] for request in own if request.get("supportKind") == kind}),
            "requests": sum(request.get("supportKind") == kind for request in own),
        } for kind in HELP_KINDS],
        "limits": limits,
        "help": help_funnel(own),
    }


async def pulse_stats(run_ids):
    offers = await db.learning_path_pulse_events.find({"runId": {"$in": run_ids}, "event": "offered"}).to_list(None)
    reactions = {
        row["offerId"]: row["event"]
        async for row in db.learning_path_pulse_events.find({"runId": {"$in": run_ids}, "reaction": True}, {"offerId": 1, "event": 1})
    }
    sessions = {
        row["_id"]: row["status"]
        async for row in db.survey_sessions.find({"_id": {"$in": [pulse_session_id(offer) for offer in offers]}}, {"status": 1})
    }
    outcomes = Counter()
    opened = 0
    answered_by_survey = Counter()
    for offer in offers:
        session = sessions.get(pulse_session_id(offer))
        outcome = reactions.get(offer["_id"]) or ("answered" if session == "submitted" else "pending")
        outcomes[outcome] += 1
        opened += session is not None or outcome == "answered"
        answered_by_survey[offer["surveyId"]] += outcome == "answered"
    offered_by_survey = Counter(offer["surveyId"] for offer in offers)
    names = {row["_id"]: row["title"] async for row in db.surveys.find({"_id": {"$in": list(offered_by_survey)}}, {"title": 1})}
    total, sessions_seen = len(offers), len({offer["sessionKey"] for offer in offers})
    return {
        "offers": total, "opened": opened, "answered": outcomes["answered"], "dismissed": outcomes["dismissed"],
        "expired": outcomes["expired"], "pending": outcomes["pending"],
        "openRate": percent(opened, total), "answerRate": percent(outcomes["answered"], total),
        "dismissRate": percent(outcomes["dismissed"], total), "expiredRate": percent(outcomes["expired"], total),
        "sessions": sessions_seen, "offersPerSession": round(total / sessions_seen, 2) if sessions_seen else None,
        "surveys": [{
            "surveyId": survey_id, "name": names.get(survey_id, survey_id), "offered": count,
            "answered": answered_by_survey[survey_id], "answerRate": percent(answered_by_survey[survey_id], count),
        } for survey_id, count in offered_by_survey.most_common()],
    }


async def help_answers(requests):
    """Choice distribution of the help-flow questions, read from the combined help survey sessions."""
    ids = [request["surveySessionId"] for request in requests if request.get("surveySessionId")]
    sessions = await db.survey_sessions.find(
        {"_id": {"$in": ids}}, {"answers": 1, "helpCompletedPhases": 1, "releaseId": 1}
    ).to_list(None)
    releases = {
        row["_id"]: {element["name"]: element for element in row["definition"]["elements"]}
        async for row in db.survey_versions.find({"_id": {"$in": list({s["releaseId"] for s in sessions})}}, {"definition": 1})
    }
    result = []
    for name, phase in HELP_ANSWERS:
        counts, labels, title = Counter(), {}, name
        for session in sessions:
            question = releases.get(session["releaseId"], {}).get(name, {})
            title = question.get("title", title)
            # Choice ids are stable across releases, so labels of the newest release seen win.
            labels.update({choice: question.get("choiceLabels", {}).get(choice, choice) for choice in question.get("choices", [])})
            answer = session.get("answers", {}).get(name)
            if answer is not None and phase in session.get("helpCompletedPhases", {}):
                counts[answer] += 1
        result.append({
            "name": name, "title": title, "responses": sum(counts.values()),
            "options": [{"key": labels.get(choice, choice), "count": counts[choice]} for choice in dict.fromkeys([*labels, *counts])],
        })
    return result


async def path_feedback(template_id, include_staff, user):
    require_access(user)
    template = await template_document(template_id)
    tasks, run_ids, started, attempts, requests = await collect(template, await analytics_paths.run_ids(template["_id"], include_staff))
    steps = [step_feedback(step, started, attempts, requests, runtime_config(template, step)) for step in tasks.values()]
    return {
        "steps": steps, "help": help_funnel(requests),
        "pulse": await pulse_stats(run_ids), "helpAnswers": await help_answers(requests),
    }


async def participant_attempts(template_id, run_id, user):
    require_access(user)
    template = await template_document(template_id)
    if not await db.learning_path_runs.find_one({"_id": str(run_id), "templateId": template["_id"]}, {"_id": 1}):
        raise not_found()
    tasks, _, _, attempts, requests = await collect(template, [str(run_id)])
    by_id = {request["_id"]: request for request in requests}
    linked = {row["helpRequestId"] for row in attempts if row["helpRequestId"]}
    result = []
    for step_id, step in tasks.items():
        events = [{
            "at": row["at"], "type": "evaluation", "evaluationId": row["id"], "state": row["state"], "scorePercent": row["score"], "passed": row["passed"],
            "supportKind": by_id.get(row["helpRequestId"], {}).get("supportKind"),
            "helpStage": by_id.get(row["helpRequestId"], {}).get("stage"),
        } for row in attempts if row["stepId"] == step_id]
        events += [{
            "at": request["createdAt"], "type": "help_request", "state": None, "scorePercent": None, "passed": None,
            "supportKind": request.get("supportKind"), "helpStage": request.get("stage", "completed"),
        } for request in requests if request["stepId"] == step_id and request["_id"] not in linked]
        if events:
            result.append({"stepId": step_id, "title": step["title"], "events": sorted(events, key=lambda event: event["at"])})
    return result


async def attempt_model(template_id, run_id, evaluation_id, user):
    """The model submitted with one attempt next to the feedback the learner got; every call is logged.

    Staff only. The evaluation must belong to the model of a run step of this run, which in turn must
    belong to the template; anything else is a 404 so ids of other runs cannot be probed.
    """
    require_access(user)
    template = await template_document(template_id)
    run = await db.learning_path_runs.find_one({"_id": str(run_id), "templateId": template["_id"]}, {"learnerId": 1})
    evaluation = await db.evaluations.find_one({"_id": str(evaluation_id)}, {
        "modelId": 1, "startedAt": 1, "submission": 1, "workflow.name": 1, "studentFeedback": 1,
        "submissionSnapshot.versionId": 1, "submissionSnapshot.data.xml": 1,
    })
    state = evaluation and await db.learning_path_run_steps.find_one(
        {"runId": str(run_id), "modelId": evaluation["modelId"]}, {"stepId": 1}
    )
    xml = ((evaluation or {}).get("submissionSnapshot", {}).get("data") or {}).get("xml")
    if not run or not state or not isinstance(xml, str):
        raise not_found()
    step = next((item for item in template["steps"] if item["id"] == state["stepId"]), None)
    version_id = evaluation["submissionSnapshot"].get("versionId") or evaluation["submission"].get("versionId")
    await db.analytics_access_log.insert_one({
        "userId": user.id, "learnerId": run.get("learnerId"), "runId": str(run_id), "stepId": state["stepId"],
        "evaluationId": evaluation["_id"], "modelVersionId": version_id, "at": utcnow(),
    })
    stored = evaluation.get("studentFeedback")
    return {
        "evaluationId": evaluation["_id"], "stepId": state["stepId"], "stepTitle": step["title"] if step else state["stepId"],
        "startedAt": evaluation["startedAt"], "modelVersionId": version_id, "xml": xml,
        "feedback": _feedback_projection(evaluation, stored) if stored is not None else None,
    }
