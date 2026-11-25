"""Staff analytics over editor activity (sessions, work time, window switches) of one learning path.

An activity session belongs to a model; the model belongs to a run step (run_steps.modelId, written
once per step), so every session maps to exactly one participant and task step. Only aggregated
values leave this module, never the raw interactions.

Definitions (all approximations of what the browser reports):
- gross time: session end minus start; an open session (no end received) counts to its last interaction.
- idle time: from an `idle` event to the next `active` event (or the session end). The client emits
  `idle` after 5 minutes without input, so idleness really began about 5 minutes earlier; this is not
  subtracted. Sessions without idle events have no idle time.
- active time: gross minus idle time.
- window switch: a `tab_hidden` or `focus_lost` event that changes the state from visible/focused.
  The first event of each kind in a session is the start snapshot and never counts as a switch.
- outside window: time while the tab is hidden or the window has lost focus.
"""

from collections import Counter, defaultdict
from statistics import median

from modeling_api.db.client import db
from modeling_api.services import analytics_paths
from modeling_api.services.analytics_feedback import ATTEMPT_BINS, attempt_bin, mean_or_none, percent, started_models
from modeling_api.services.learning_path_progress import require_access
from modeling_api.services.learning_path_store import template_document

# interaction type -> (state flag, new value)
TRANSITIONS = {
    "tab_hidden": ("hidden", True), "tab_visible": ("hidden", False),
    "focus_lost": ("unfocused", True), "focus_gained": ("unfocused", False),
    "idle": ("idle", True), "active": ("idle", False),
}
SWITCH_FLAGS = {"hidden": "tabHidden", "unfocused": "focusLost"}
FIELDS = ("sessions", "gross", "active", "outside", "tabHidden", "focusLost", "open")


def session_metrics(session, interactions):
    """Gross/idle/outside seconds and window switches of one session."""
    start = session["createdAt"]
    ordered = sorted(interactions, key=lambda item: item["createdAt"])
    open_session = session.get("endedAt") is None
    end = max([start, *(item["createdAt"] for item in ordered)]) if open_session else session["endedAt"]
    state = {"hidden": False, "unfocused": False, "idle": False}
    seen, switches = set(), Counter()
    idle = outside = 0.0
    since = start
    for item in ordered:
        at = min(max(item["createdAt"], start), end)
        gap = (at - since).total_seconds()
        idle += gap * state["idle"]
        outside += gap * (state["hidden"] or state["unfocused"])
        since = at
        flag, value = TRANSITIONS[item["type"]]
        if flag in seen and value and not state[flag] and flag in SWITCH_FLAGS:
            switches[SWITCH_FLAGS[flag]] += 1
        seen.add(flag)
        state[flag] = value
    gap = (end - since).total_seconds()
    idle += gap * state["idle"]
    outside += gap * (state["hidden"] or state["unfocused"])
    gross = (end - start).total_seconds()
    return {
        "sessions": 1, "gross": gross, "active": gross - idle, "outside": outside,
        "tabHidden": switches["tabHidden"], "focusLost": switches["focusLost"], "open": int(open_session),
    }


def total_of(rows):
    total = dict.fromkeys(FIELDS, 0)
    for row in rows:
        for field in FIELDS:
            total[field] += row[field]
    return total


def stats(persons):
    """Distribution statistics over per-person totals (persons with at least one session)."""
    sessions = sum(row["sessions"] for row in persons)
    gross = [row["gross"] for row in persons]
    active = [row["active"] for row in persons]
    distribution = Counter(attempt_bin(row["sessions"]) for row in persons)
    return {
        "persons": len(persons), "sessions": sessions, "openSessions": sum(row["open"] for row in persons),
        "avgSessionsPerPerson": mean_or_none([row["sessions"] for row in persons], 2),
        "sessionDistribution": [{"label": label, "users": distribution[label]} for _, label in ATTEMPT_BINS],
        "avgGrossSeconds": mean_or_none(gross, 0), "medianGrossSeconds": round(median(gross)) if gross else None,
        "avgActiveSeconds": mean_or_none(active, 0), "medianActiveSeconds": round(median(active)) if active else None,
        "avgSessionSeconds": round(sum(gross) / sessions) if sessions else None,
        **{f"{key}PerPerson": mean_or_none([row[key] for row in persons], 2) for key in ("tabHidden", "focusLost")},
        **{f"{key}PerSession": round(sum(row[key] for row in persons) / sessions, 2) if sessions else None
           for key in ("tabHidden", "focusLost")},
        "outsideShare": percent(sum(row["outside"] for row in persons), sum(gross)),
    }


def summary(row):
    return {"sessions": row["sessions"], "grossSeconds": round(row["gross"]), "activeSeconds": round(row["active"]),
            "tabHidden": row["tabHidden"], "focusLost": row["focusLost"]}


async def path_activity(template_id, include_staff, user):
    require_access(user)
    template = await template_document(template_id)
    tasks, _, started = await started_models(template, await analytics_paths.run_ids(template["_id"], include_staff))
    sessions = await db.model_activity_sessions.find(
        {"modelId": {"$in": list(started)}}, {"modelId": 1, "createdAt": 1, "endedAt": 1}
    ).to_list(None)
    # shortcut: all interactions of the template are read at once; page by session batches for very large cohorts.
    interactions = defaultdict(list)
    async for item in db.model_activity_interactions.find(
        {"sessionId": {"$in": [session["_id"] for session in sessions]}}, {"sessionId": 1, "createdAt": 1, "type": 1}
    ):
        interactions[item["sessionId"]].append(item)
    pieces = defaultdict(lambda: defaultdict(list))  # runId -> stepId -> session rows
    for session in sessions:
        run_id, step_id = started[session["modelId"]]
        pieces[run_id][step_id].append(session_metrics(session, interactions[session["_id"]]))
    by_person = {run_id: {step_id: total_of(rows) for step_id, rows in steps.items()} for run_id, steps in pieces.items()}
    totals = {run_id: total_of(steps.values()) for run_id, steps in by_person.items()}
    runs = [
        {**summary(totals[run_id]), "runId": run_id, "steps": [{**summary(row), "stepId": step_id} for step_id, row in steps.items()]}
        for run_id, steps in by_person.items()
    ]
    return {
        "path": stats(list(totals.values())),
        "steps": [
            {**stats([steps[step_id] for steps in by_person.values() if step_id in steps]),
             "stepId": step_id, "title": step["title"]}
            for step_id, step in tasks.items()
        ],
        "runs": runs,
    }

