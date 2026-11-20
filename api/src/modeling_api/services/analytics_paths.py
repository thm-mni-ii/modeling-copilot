"""Staff analytics over learning-path participation, aggregated per template."""

from collections import Counter
from datetime import timedelta
from statistics import median

from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.services.learning_path_access import template_visibility
from modeling_api.services.learning_path_progress import progress_view, require_access
from modeling_api.services.learning_path_store import attach_steps, template_document

STALLED_AFTER = timedelta(days=7)


async def run_filter(template_id, include_staff):
    """Run query of one template; staff runs (users flagged isStaff, unflagged users are no staff) are left out unless included."""
    query = {"templateId": str(template_id)}
    if not include_staff:
        query["learnerId"] = {"$nin": await db.submission_users.distinct("_id", {"isStaff": True})}
    return query


async def run_ids(template_id, include_staff):
    return [run["_id"] async for run in db.learning_path_runs.find(await run_filter(template_id, include_staff), {"_id": 1})]


async def template_rows(template, include_staff=True):
    """Progress rows of all runs of one template, using the same semantics as the progress list."""
    runs = {
        run["_id"]: {**run, "stepStates": []}
        async for run in db.learning_path_runs.find(await run_filter(template["_id"], include_staff))
    }
    async for state in db.learning_path_run_steps.find({"runId": {"$in": list(runs)}}):
        runs[state["runId"]]["stepStates"].append(state)
    # Learner names are not needed for aggregates, so none are resolved.
    return [await progress_view(run, template, {}) for run in runs.values()]


def entry(template, rows):
    now = utcnow()
    total = len(rows)
    counts = Counter(row["status"] for row in rows)
    seconds = [
        (row["firstFinishedAt"] - row["createdAt"]).total_seconds() for row in rows if row["firstFinishedAt"]
    ]
    return {
        "id": template["_id"], "name": template["title"],
        "visibility": template_visibility(template), "revision": template["revision"],
        "participants": total, "notStarted": counts["not_started"],
        "inProgress": counts["in_progress"], "completed": counts["completed"],
        "stalled": sum(
            row["status"] == "in_progress" and now - row["lastActivityAt"] > STALLED_AFTER for row in rows
        ),
        "avgProgress": round(sum(row["progress"] for row in rows) / total, 1) if total else 0,
        "completionRate": round(counts["completed"] / total * 100, 1) if total else 0,
        "medianSecondsToFinish": median(seconds) if seconds else None,
        "lastActivityAt": max((row["lastActivityAt"] for row in rows), default=None),
    }


async def path_overview(user):
    require_access(user)
    # shortcut: loads every template and run in memory, move to a Mongo pipeline when runs reach tens of thousands.
    templates = await attach_steps([doc async for doc in db.learning_path_templates.find().sort("createdAt", -1)])
    return [entry(template, await template_rows(template)) for template in templates]


async def path_detail(template_id, include_staff, user):
    require_access(user)
    template = await template_document(template_id)
    hidden = 0 if include_staff else await db.learning_path_runs.count_documents(
        {"templateId": template["_id"], "learnerId": {"$in": await db.submission_users.distinct("_id", {"isStaff": True})}}
    )
    return {
        **entry(template, await template_rows(template, include_staff)),
        "description": template["description"], "hiddenStaffRuns": hidden,
    }
