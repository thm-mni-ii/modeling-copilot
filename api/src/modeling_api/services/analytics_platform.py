"""Staff analytics over platform usage; counts only, never model content.

Event counts (models, versions, evaluations, editor sessions)
refer to records created within the selected period. User totals, the 7/30 day activity windows,
task stock and the "last 7 days" evaluation count do not depend on the period.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean

from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.services.evaluations import learner_score
from modeling_api.services.fbs_users import resolve_names
from modeling_api.services.learning_path_progress import require_access

# A semester is defined as the last 180 days.
PERIOD_DAYS = {"7d": 7, "30d": 30, "semester": 180, "all": None}
MIN_SERIES_DAYS = 28
ALL_SERIES_DAYS = 52 * 7
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# Lower bounds of the models-per-user histogram bins; the last bin is open-ended.
HISTOGRAM_BOUNDS = [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5"), (6, "6-10"), (11, "11-20"), (21, "21+")]


async def run(collection, pipeline):
    return await (await collection.aggregate(pipeline)).to_list(None)


async def scope(period, include_staff):
    """Return (since, match builder) for the selected period and staff flag."""
    days = PERIOD_DAYS[period]
    since = utcnow() - timedelta(days=days) if days else None
    # Users without the flag count as non-staff; staff are few, so a $nin list stays small.
    excluded = [] if include_staff else await db.submission_users.distinct("_id", {"isStaff": True})

    def match(time_field, owner_field, extra=None, floor=since):
        conditions = dict(extra or {})
        if floor:
            conditions[time_field] = {"$gte": floor}
        if excluded:
            conditions[owner_field] = {"$nin": excluded}
        return {"$match": conditions}

    return since, match


def week_start(value):
    value = value.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return value - timedelta(days=value.weekday())


def week_expression(field):
    return {"$dateTrunc": {"date": field, "unit": "week", "startOfWeek": "monday"}}


def fill_weeks(rows, since):
    """One point per calendar week from `since` to now; weeks without records count 0."""
    counts = {row["_id"]: row["count"] for row in rows}
    week, last = week_start(since), week_start(utcnow())
    points = []
    while week <= last:
        points.append({"weekStart": week, "count": counts.get(week, 0)})
        week += timedelta(days=7)
    return points


def histogram(rows):
    """Map $bucket output (lower bound -> users) to labelled bins including empty ones."""
    users = {row["_id"]: row["users"] for row in rows}
    return [{"label": label, "users": users.get(bound, 0)} for bound, label in HISTOGRAM_BOUNDS]


def counted(rows):
    return [{"key": row["_id"], "count": row["count"]} for row in sorted(rows, key=lambda row: -row["count"])]


# Median of the pushed per-user counts, computed in the database.
MEDIAN = {"$let": {
    "vars": {"sorted": {"$sortArray": {"input": "$counts", "sortBy": 1}}, "size": {"$size": "$counts"}},
    "in": {"$avg": [
        {"$arrayElemAt": ["$$sorted", {"$floor": {"$divide": [{"$subtract": ["$$size", 1]}, 2]}}]},
        {"$arrayElemAt": ["$$sorted", {"$floor": {"$divide": ["$$size", 2]}}]},
    ]},
}}
BY_COUNT = {"$group": {"_id": None, "count": {"$sum": 1}}}


async def weekly_series(match, collection, time_field, owner_field, since, *, distinct_owners):
    """Weekly record counts, or distinct owners per week when `distinct_owners` is set."""
    days = series_days(since)
    floor = utcnow() - timedelta(days=days)
    week = week_expression(f"${time_field}")
    if distinct_owners:
        stages = [{"$group": {"_id": {"week": week, "owner": f"${owner_field}"}}},
                  {"$group": {"_id": "$_id.week", "count": {"$sum": 1}}}]
    else:
        stages = [{"$group": {"_id": week, "count": {"$sum": 1}}}]
    return fill_weeks(await run(collection, [match(time_field, owner_field, floor=floor), *stages]), floor)


def series_days(since):
    """Series window: the period, but at least four weeks; all-time shows the last 52 weeks."""
    if since is None:
        return ALL_SERIES_DAYS
    return max(MIN_SERIES_DAYS, (utcnow() - since).days + 1)


async def user_kpis(since, include_staff):
    now = utcnow()
    floor = since or EPOCH
    rows = await run(db.submission_users, [
        {"$match": {} if include_staff else {"isStaff": {"$ne": True}}},
        {"$group": {
            "_id": None, "known": {"$sum": 1},
            # Users without firstSeenAt/lastSeenAt compare as null and never count.
            "new": {"$sum": {"$cond": [{"$gte": ["$firstSeenAt", floor]}, 1, 0]}},
            "active7": {"$sum": {"$cond": [{"$gte": ["$lastSeenAt", now - timedelta(days=7)]}, 1, 0]}},
            "active30": {"$sum": {"$cond": [{"$gte": ["$lastSeenAt", now - timedelta(days=30)]}, 1, 0]}},
        }},
    ])
    row = rows[0] if rows else {"known": 0, "new": 0, "active7": 0, "active30": 0}
    return {"knownUsers": row["known"], "newUsers": row["new"],
            "activeUsersWeek": row["active7"], "activeUsersMonth": row["active30"]}


async def model_kpis(match):
    totals = await run(db.models, [
        match("createdAt", "ownerId"),
        {"$group": {"_id": None, "total": {"$sum": 1},
                    "archived": {"$sum": {"$cond": [{"$ne": [{"$ifNull": ["$archivedAt", None]}, None]}, 1, 0]}}}},
    ])
    per_user = (await run(db.models, [
        match("createdAt", "ownerId"),
        {"$group": {"_id": "$ownerId", "n": {"$sum": 1}}},
        {"$facet": {
            "summary": [
                {"$group": {"_id": None, "users": {"$sum": 1}, "avg": {"$avg": "$n"}, "counts": {"$push": "$n"}}},
                {"$project": {"users": 1, "avg": 1, "median": MEDIAN}},
            ],
            "histogram": [
                {"$bucket": {
                    "groupBy": "$n", "boundaries": [bound for bound, _ in HISTOGRAM_BOUNDS] + [1_000_000_000],
                    "output": {"users": {"$sum": 1}},
                }},
            ],
        }},
    ]))[0]
    summary = per_user["summary"][0] if per_user["summary"] else None
    total = totals[0] if totals else {"total": 0, "archived": 0}
    return {
        "models": total["total"], "modelsArchived": total["archived"],
        "usersWithModels": summary["users"] if summary else 0,
        "avgModelsPerUser": round(summary["avg"], 2) if summary else None,
        "medianModelsPerUser": summary["median"] if summary else None,
    }, histogram(per_user["histogram"])


async def version_kpis(match):
    rows = {row["_id"]: row["count"] for row in await run(db.model_versions, [
        match("createdAt", "createdBy"), {"$group": {"_id": "$kind", "count": {"$sum": 1}}},
    ])}
    return {"checkpoints": rows.get("checkpoint", 0), "releases": rows.get("release", 0)}


async def task_kpis():
    rows = {row["_id"]: row["count"] for row in await run(db.task, [
        {"$group": {
            "_id": {"$cond": [
                {"$ne": [{"$ifNull": ["$archivedAt", None]}, None]}, "archived",
                {"$cond": [{"$eq": ["$visibility", "published"]}, "published", "hidden"]},
            ]},
            "count": {"$sum": 1},
        }},
    ])}
    return {"tasksPublished": rows.get("published", 0), "tasksHidden": rows.get("hidden", 0),
            "tasksArchived": rows.get("archived", 0)}


async def evaluation_kpis(match):
    by_state = await run(db.evaluations, [
        match("createdAt", "ownerId"),
        {"$group": {"_id": {"$ifNull": ["$state", "unknown"]}, "count": {"$sum": 1}}},
    ])
    last_week = await run(db.evaluations, [
        match("createdAt", "ownerId", floor=utcnow() - timedelta(days=7)), BY_COUNT,
    ])
    return {
        "evaluations": sum(row["count"] for row in by_state), "evaluationsByState": counted(by_state),
        "evaluationsLastWeek": last_week[0]["count"] if last_week else 0,
    }


async def task_rows(match):
    """Per task: model owners, models and evaluations of the period; names from the task collection."""
    models = {row["_id"]: row for row in await run(db.models, [
        match("createdAt", "ownerId", {"taskVersion.taskId": {"$ne": None}}),
        {"$group": {"_id": "$taskVersion.taskId", "models": {"$sum": 1}, "owners": {"$addToSet": "$ownerId"}}},
        {"$project": {"models": 1, "persons": {"$size": "$owners"}}},
    ])}
    # Evaluations carry no score field; it is derived from the stored learner feedback.
    evaluations = defaultdict(lambda: {"evaluations": 0, "scores": []})
    async for evaluation in db.evaluations.find(
        match("createdAt", "ownerId")["$match"], {"taskId": 1, "studentFeedback.recognitions": 1, "studentFeedback.scorePercent": 1}
    ):
        row = evaluations[evaluation["taskId"]]
        row["evaluations"] += 1
        if (score := learner_score(evaluation.get("studentFeedback") or {})) is not None:
            row["scores"].append(score)
    ids = models.keys() | evaluations.keys()
    # Published tasks without activity stay visible as zero rows.
    tasks = {task["_id"]: task async for task in db.task.find(
        {"$or": [{"_id": {"$in": list(ids)}}, {"visibility": "published", "archivedAt": None}]}, {"name": 1}
    )}
    return sorted(({
        "taskId": task_id, "taskName": task.get("name") or task_id,
        "persons": models.get(task_id, {}).get("persons", 0), "models": models.get(task_id, {}).get("models", 0),
        "evaluations": evaluations[task_id]["evaluations"],
        "avgScore": round(mean(scores), 1) if (scores := evaluations[task_id]["scores"]) else None,
    } for task_id, task in tasks.items()), key=lambda row: (-row["models"], row["taskName"]))


async def platform_overview(period, include_staff, user):
    """People and models only; catalog and evaluation figures live in `platform_tasks`."""
    require_access(user)
    since, match = await scope(period, include_staff)
    model_stats, models_per_user = await model_kpis(match)
    kpis = {**await user_kpis(since, include_staff), **model_stats, **await version_kpis(match)}
    return {
        "period": period, "since": since, "kpis": kpis, "modelsPerUser": models_per_user,
        "weeklyActiveUsers": await weekly_series(match, db.model_activity_sessions, "createdAt", "createdBy", since, distinct_owners=True),
        "weeklyNewModels": await weekly_series(match, db.models, "createdAt", "ownerId", since, distinct_owners=False),
    }


async def platform_tasks(period, include_staff, user):
    require_access(user)
    since, match = await scope(period, include_staff)
    kpis = {**await task_kpis(), **await evaluation_kpis(match)}
    return {"period": period, "since": since, "kpis": kpis, "tasks": await task_rows(match)}


async def person_rows(match, include_staff):
    """One row per known user; the per-user aggregates are computed in the database."""
    models = {row["_id"]: row for row in await run(db.models, [
        match("createdAt", "ownerId"),
        {"$group": {"_id": "$ownerId", "models": {"$sum": 1}, "tasks": {"$addToSet": "$taskVersion.taskId"}}},
        {"$project": {"models": 1, "tasks": {"$size": {"$setDifference": ["$tasks", [None]]}}}},
    ])}
    counts = {}
    for key, collection, owner_field in (("evaluations", db.evaluations, "ownerId"),
                                         ("helpRequests", db.learning_path_help_requests, "ownerId")):
        counts[key] = {row["_id"]: row["count"] for row in await run(collection, [
            match("createdAt", owner_field), {"$group": {"_id": f"${owner_field}", "count": {"$sum": 1}}},
        ])}
    # Only finished sessions have a duration; idle time is not subtracted.
    sessions = {row["_id"]: row["seconds"] for row in await run(db.model_activity_sessions, [
        match("createdAt", "createdBy", {"endedAt": {"$ne": None}}),
        {"$group": {"_id": "$createdBy", "seconds": {"$sum": {"$divide": [{"$subtract": ["$endedAt", "$createdAt"]}, 1000]}}}},
    ])}
    users = db.submission_users.find(
        {} if include_staff else {"isStaff": {"$ne": True}}, {"name": 1, "fbsName": 1, "lastSeenAt": 1}
    )
    return [{
        "userId": user["_id"], "userName": user.get("fbsName") or user.get("name") or user["_id"],
        "lastSeenAt": user.get("lastSeenAt"),
        "models": models.get(user["_id"], {}).get("models", 0), "tasks": models.get(user["_id"], {}).get("tasks", 0),
        "evaluations": counts["evaluations"].get(user["_id"], 0),
        "helpRequests": counts["helpRequests"].get(user["_id"], 0),
        "sessionSeconds": sessions.get(user["_id"], 0),
    } async for user in users]


async def platform_persons(period, include_staff, sort_by, sort_desc, skip, limit, user, token=None):
    require_access(user)
    _, match = await scope(period, include_staff)
    rows = await person_rows(match, include_staff)
    field = "userName" if sort_by == "name" else sort_by

    def key(row):
        value = row[field]
        # Names sort case-insensitively; users never seen sort as the oldest.
        if field == "userName":
            value = value.lower()
        elif field == "lastSeenAt":
            value = value or EPOCH
        return (value, row["userId"])

    rows.sort(key=key, reverse=sort_desc)
    page = rows[skip:skip + limit]
    # Fresh names are resolved for the visible page only.
    names = await resolve_names((row["userId"] for row in page), user, token)
    return {"items": [{**row, "userName": names.get(row["userId"], row["userName"])} for row in page], "total": len(rows)}
