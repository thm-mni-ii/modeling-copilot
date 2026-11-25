"""Staff analytics over survey responses, aggregated per question; never individual answers or users.

Only non-test sessions count. Question statistics use submitted sessions; skipped sessions carry no
answers and drafts only partial ones. Sessions store no usage context, so it is derived:
- help: the survey is managed by a learning path's help flow (managedBy "learning-path-help");
- pulse: the session id equals the deterministic id of a pulse offer of this survey;
- path: the session is linked from a run step (surveySessionId / beforeSurvey / afterSurvey);
- other: remaining sessions (standalone responses); they appear only under "all".
`contextFlags` (help_requested, pulse_answered) record what the learner used before a path survey
and do not identify the context. Every statistic is aggregated and carries its response count n; the
caller decides how to flag small samples.
"""

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean, median

from modeling_api.core.errors import not_found
from modeling_api.db.client import db
from modeling_api.services import surveys
from modeling_api.services.analytics_platform import run, week_start
from modeling_api.services.learning_path_progress import require_access
from modeling_api.services.pulse_surveys import session_id as pulse_session_id

RECENT_DAYS = 7
CONTEXTS = ("path", "pulse", "help")
CHOICE_TYPES = ("radiogroup", "dropdown", "checkbox", "boolean")
SESSION_LINKS = ("surveySessionId", "beforeSurvey", "afterSurvey")
STATUSES = ("submitted", "skipped", "draft")


def percent(count, total):
    return round(count / total * 100, 1) if total else None


def status_counts(statuses):
    counts = Counter(statuses)
    total = sum(counts[status] for status in STATUSES)
    return {"responses": total, **{status: counts[status] for status in STATUSES}}


async def survey_overview(user):
    require_access(user)
    documents = [doc async for doc in db.surveys.find({"deletedAt": None}, {"title": 1, "activeReleaseVersion": 1, "managedBy": 1})]
    owner = {
        version["_id"]: version["surveyId"]
        async for version in db.survey_versions.find({"surveyId": {"$in": [doc["_id"] for doc in documents]}}, {"surveyId": 1})
    }
    rows = await run(db.survey_sessions, [
        {"$match": {"releaseId": {"$in": list(owner)}, "isTest": {"$ne": True}}},
        {"$group": {"_id": {"release": "$releaseId", "status": "$status"}, "count": {"$sum": 1}, "last": {"$max": "$completedAt"}}},
    ])
    counts, last = defaultdict(Counter), {}
    for row in rows:
        survey_id = owner[row["_id"]["release"]]
        counts[survey_id][row["_id"]["status"]] += row["count"]
        if row["last"] and (survey_id not in last or row["last"] > last[survey_id]):
            last[survey_id] = row["last"]
    result = []
    for doc in documents:
        own = status_counts(counts[doc["_id"]].elements())
        result.append({
            "id": doc["_id"], "title": doc["title"],
            "kind": "help" if doc.get("managedBy") == "learning-path-help" else "standard",
            "activeReleaseVersion": doc.get("activeReleaseVersion"), **own,
            **{f"{status}Share": percent(own[status], own["responses"]) for status in STATUSES},
            "lastResponseAt": last.get(doc["_id"]),
        })
    return sorted(result, key=lambda row: row["title"].casefold())


async def session_contexts(survey, sessions):
    """Map session id -> path|pulse|help|other (see module docstring)."""
    if survey.get("managedBy") == "learning-path-help":
        return {session["_id"]: "help" for session in sessions}
    offers = db.learning_path_pulse_events.find({"surveyId": survey["_id"], "event": "offered"}, {"runId": 1, "stepId": 1, "surveyId": 1})
    pulse = {pulse_session_id(offer) async for offer in offers}
    pending = [session["_id"] for session in sessions if session["_id"] not in pulse]
    linked = set()
    if pending:
        # shortcut: unindexed scan of linked run steps, bounded by the learner count; index the link fields if it gets slow.
        steps = db.learning_path_run_steps.find({"$or": [{field: {"$in": pending}} for field in SESSION_LINKS]}, dict.fromkeys(SESSION_LINKS, 1))
        async for step in steps:
            linked.update(step[field] for field in SESSION_LINKS if step.get(field))
    return {
        session["_id"]: "pulse" if session["_id"] in pulse else "path" if session["_id"] in linked else "other"
        for session in sessions
    }


def blank(value):
    return value is None or value == "" or value == [] or value == {}


def parse(kind, question, value):
    """Reduce a stored answer to what the question kind aggregates; None means not usable."""
    if kind == "choice":
        values = value if isinstance(value, list) else [value]
        keys = ["true" if v is True else "false" if v is False else str(v) for v in values if not blank(v)]
        return keys or None
    if kind == "rating":
        low, high = question.get("rateMin", 1), question.get("rateMax", 5)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high else None
    if kind == "text":
        return len(value) if isinstance(value, str) else None
    return True


def choice_options(question):
    if question["type"] == "boolean":
        return [("true", "Yes"), ("false", "No")]
    labels = question.get("choiceLabels") or {}
    return [(choice, labels.get(choice, choice)) for choice in question.get("choices") or []]


def question_stats(question, entries, weeks):
    """entries: (week, stored answer) of every submitted response that answered the question."""
    kind = "choice" if question["type"] in CHOICE_TYPES else {"rating": "rating", "comment": "text"}.get(question["type"], "other")
    parsed = [(week, value) for week, raw in entries if (value := parse(kind, question, raw)) is not None]
    rating = kind == "rating"
    values = [value for _, value in parsed]
    stats = {
        "name": question["name"], "title": question["title"], "type": question["type"], "kind": kind,
        "responses": len(parsed), "mean": None, "median": None, "avgLength": None,
        "scaleMin": question.get("rateMin", 1) if rating else None, "scaleMax": question.get("rateMax", 5) if rating else None,
        "minLabel": question.get("minRateDescription") if rating else None, "maxLabel": question.get("maxRateDescription") if rating else None,
        "options": [], "trend": [],
    }
    if kind == "choice":
        options = choice_options(question)
        known = {key for key, _ in options}
        options += [(key, key) for key in sorted({key for value in values for key in value} - known)]
    elif rating:
        options = [(str(number), str(number)) for number in range(stats["scaleMin"], stats["scaleMax"] + 1)]
    else:
        options = []
    if values and rating:
        stats["mean"], stats["median"] = round(mean(values), 2), median(values)
    elif values and kind == "text":
        stats["avgLength"] = round(mean(values), 1)
    counts = Counter(key for value in values for key in (value if kind == "choice" else [str(value)]))
    stats["options"] = [{"key": key, "label": label, "count": counts[key]} for key, label in options]
    for week in weeks:
        group = [value for point, value in parsed if point == week]
        stats["trend"].append({"weekStart": week, "responses": len(group), "mean": round(mean(group), 2) if rating and group else None})
    return stats


def session_summary(sessions):
    """Header numbers of a session list: status counts, submitted in the last 7 days, completion share, last response."""
    submitted = [session for session in sessions if session["status"] == "submitted"]
    since = datetime.now(UTC) - timedelta(days=RECENT_DAYS)
    dates = [session["completedAt"] for session in submitted if session.get("completedAt")]
    counts = status_counts(session["status"] for session in sessions)
    return {
        **counts, "submittedLastWeek": sum(1 for date in dates if date.astimezone(UTC) >= since),
        "completionShare": percent(counts["submitted"], counts["responses"]), "lastResponseAt": max(dates, default=None),
    }


def survey_questions(definition, sessions, session_ids=None):
    """Per-question statistics of the submitted sessions; session_ids (optional) restricts them to those sessions."""
    answered = [
        session for session in sessions
        if session["status"] == "submitted" and session.get("completedAt") and (session_ids is None or session["_id"] in session_ids)
    ]
    weeks = []
    if answered:
        first, last = (week_start(f(session["completedAt"] for session in answered)) for f in (min, max))
        weeks = [first + timedelta(days=7 * index) for index in range((last - first).days // 7 + 1)]
    return [
        question_stats(question, [
            (week_start(session["completedAt"]), session["answers"][question["name"]])
            for session in answered if not blank((session.get("answers") or {}).get(question["name"]))
        ], weeks)
        for question in definition["elements"]
    ]


async def survey_detail(survey_id, release_id, context, user):
    require_access(user)
    survey = await surveys.survey_document(survey_id)
    releases = await db.survey_versions.find({"surveyId": survey["_id"], "kind": "release"}, {"definition": 0}).sort("version", -1).to_list(None)
    if release_id is not None:
        selected = next((release for release in releases if release["_id"] == str(release_id)), None)
        if selected is None:
            raise not_found()
    else:
        selected = next((release for release in releases if release["_id"] == survey.get("activeReleaseId")), releases[0] if releases else None)
    submitted = {
        row["_id"]: row["count"] for row in await run(db.survey_sessions, [
            {"$match": {"releaseId": {"$in": [release["_id"] for release in releases]}, "isTest": {"$ne": True}, "status": "submitted"}},
            {"$group": {"_id": "$releaseId", "count": {"$sum": 1}}},
        ])
    }
    result = {
        "id": survey["_id"], "title": survey["title"],
        "kind": "help" if survey.get("managedBy") == "learning-path-help" else "standard",
        "release": None, "releases": [{
            "id": release["_id"], "version": release["version"], "releasedAt": release.get("releasedAt"),
            "active": release["_id"] == survey.get("activeReleaseId"), "submitted": submitted.get(release["_id"], 0),
        } for release in releases],
        "context": context, "contextCounts": [{"key": key, "count": 0} for key in CONTEXTS],
        **session_summary([]), "questions": [],
    }
    if selected is None:
        return result
    result["release"] = next(release for release in result["releases"] if release["id"] == selected["_id"])
    definition = (await db.survey_versions.find_one({"_id": selected["_id"]}, {"definition": 1}))["definition"]
    # shortcut: sessions of one release are read into memory (bounded by the learner count); aggregate in Mongo if it grows.
    sessions = await db.survey_sessions.find(
        {"releaseId": selected["_id"], "isTest": {"$ne": True}}, {"status": 1, "answers": 1, "completedAt": 1}
    ).to_list(None)
    contexts = await session_contexts(survey, sessions)
    done = Counter(contexts[session["_id"]] for session in sessions if session["status"] == "submitted")
    result["contextCounts"] = [{"key": key, "count": done[key]} for key in CONTEXTS]
    if context != "all":
        sessions = [session for session in sessions if contexts[session["_id"]] == context]
    result.update(session_summary(sessions))
    result["questions"] = survey_questions(definition, sessions)
    return result
