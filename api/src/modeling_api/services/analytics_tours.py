"""Staff analytics over guided-tour events, aggregated per tour and per person."""

from datetime import timedelta

from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.services.analytics_platform import week_start
from modeling_api.services.fbs_users import resolve_names
from modeling_api.services.learning_path_progress import require_access
from modeling_api.services.tours import TOURS, get_tour

WEEKS = 12


async def tour_events(tour, **filters):
    return [
        event async for event in db.tour_events.find(
            {"tourId": tour.id, "tourVersion": tour.version, **filters}
        ).sort("at", 1)
    ]


def participant_rows(tour, events):
    """One row per user from events sorted by time; completed once means completed."""
    position = {step_id: index for index, (step_id, _) in enumerate(tour.steps)}
    rows = {}
    for event in events:
        row = rows.setdefault(event["userId"], {
            "userId": event["userId"], "opens": 0, "starts": 0, "completed": False, "outcome": None,
            "furthest": -1, "firstEventAt": event["at"], "lastEventAt": event["at"],
        })
        row["lastEventAt"] = event["at"]
        kind = event["event"]
        if kind == "opened":
            row["opens"] += 1
        elif kind == "started":
            row["starts"] += 1
            row["outcome"] = "in_progress"
        elif kind == "completed":
            row["completed"] = True
            row["furthest"] = len(tour.steps) - 1
        elif kind == "skipped":
            row["outcome"] = "skipped"
        if event.get("stepId") in position:
            row["furthest"] = max(row["furthest"], position[event["stepId"]])
        if kind == "step" and row["outcome"] is None:
            row["outcome"] = "in_progress"
    for row in rows.values():
        completed, outcome = row.pop("completed"), row.pop("outcome")
        row["status"] = "completed" if completed else outcome or "opened"
    return list(rows.values())


def funnel(tour, rows):
    left = [
        sum(row["furthest"] == index and row["status"] != "completed" for row in rows)
        for index in range(len(tour.steps))
    ]
    biggest = left.index(max(left)) if any(left) else None
    return [{
        "id": step_id, "title": title,
        "reached": sum(row["furthest"] >= index for row in rows),
        "leftHere": left[index], "biggestDropOff": index == biggest,
    } for index, (step_id, title) in enumerate(tour.steps)]


def entry(tour, rows):
    started = sum(row["starts"] > 0 for row in rows)
    completed = sum(row["status"] == "completed" for row in rows)
    return {
        "id": tour.id, "title": tour.title, "version": tour.version,
        "openedUsers": sum(row["opens"] > 0 for row in rows), "startedUsers": started,
        "completedUsers": completed, "skippedUsers": sum(row["status"] == "skipped" for row in rows),
        "completionRate": min(100, round(completed / started * 100, 1)) if started else 0,
        "lastActivityAt": max((row["lastEventAt"] for row in rows), default=None),
    }


def weekly_series(events_by_tour):
    """Last 12 calendar weeks (Monday-Sunday UTC): distinct users who started / completed any tour."""
    first = week_start(utcnow()) - timedelta(weeks=WEEKS - 1)
    users = {first + timedelta(weeks=index): {"started": set(), "completed": set()} for index in range(WEEKS)}
    for events in events_by_tour:
        for event in events:
            if event["event"] in ("started", "completed") and (week := users.get(week_start(event["at"]))):
                week[event["event"]].add(event["userId"])
    return [{"weekStart": start, "starts": len(week["started"]), "completions": len(week["completed"])}
            for start, week in users.items()]


async def tour_overview(include_staff, user):
    """Summary over all tours (distinct users), the last 12 weeks and one row per tour."""
    require_access(user)
    # Users without the flag count as non-staff; staff are few, so a $nin list stays small.
    excluded = [] if include_staff else await db.submission_users.distinct("_id", {"isStaff": True})
    filters = {"userId": {"$nin": excluded}} if excluded else {}
    events_by_tour = [await tour_events(tour, **filters) for tour in TOURS.values()]
    rows_by_tour = [participant_rows(tour, events) for tour, events in zip(TOURS.values(), events_by_tour, strict=True)]
    rows = [row for tour_rows in rows_by_tour for row in tour_rows]

    def users(condition):
        return {row["userId"] for row in rows if condition(row)}

    started, completed = users(lambda row: row["starts"] > 0), users(lambda row: row["status"] == "completed")
    known = await db.submission_users.count_documents({} if include_staff else {"isStaff": {"$ne": True}})
    summary = {
        "tours": len(TOURS), "openedUsers": len(users(lambda row: row["opens"] > 0)), "startedUsers": len(started),
        "completedUsers": len(completed), "skippedUsers": len(users(lambda row: row["status"] == "skipped")),
        "completionRate": min(100, round(len(completed) / len(started) * 100, 1)) if started else 0,
        "knownUsers": known, "coverage": min(100, round(len(started) / known * 100, 1)) if known else 0,
    }
    return {
        "summary": summary, "weekly": weekly_series(events_by_tour),
        "tours": [entry(tour, tour_rows) for tour, tour_rows in zip(TOURS.values(), rows_by_tour, strict=True)],
    }


async def tour_detail(tour_id, user, token=None):
    require_access(user)
    tour = get_tour(tour_id)
    rows = participant_rows(tour, await tour_events(tour))
    names = await resolve_names((row["userId"] for row in rows), user, token)
    participants = sorted(
        ({**{key: value for key, value in row.items() if key != "furthest"},
          "userName": names.get(row["userId"], row["userId"]),
          "furthestStepId": tour.steps[row["furthest"]][0] if row["furthest"] >= 0 else None}
         for row in rows),
        key=lambda row: row["lastEventAt"], reverse=True,
    )
    return {**entry(tour, rows), "steps": funnel(tour, rows), "participants": participants}


async def tour_timeline(tour_id, user_id, user):
    require_access(user)
    tour = get_tour(tour_id)
    titles = dict(tour.steps)
    return [
        {"event": event["event"], "stepId": event.get("stepId"), "stepTitle": titles.get(event.get("stepId")), "at": event["at"]}
        for event in await tour_events(tour, userId=user_id)
    ]
