"""Read-only staff views of learning-path participation and progress."""

import csv
import io
import json
from datetime import datetime

from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import list_page
from modeling_api.services.fbs_users import resolve_names
from modeling_api.services.learning_path_store import attach_steps, attach_states, template_document
from modeling_api.services.learning_paths import run_view


def can_view_progress(user):
    return user.is_admin or user.global_role == "MODERATOR" or "MODERATOR" in user.roles


def require_access(user):
    if not can_view_progress(user):
        raise ApiError(403, "FORBIDDEN", "Moderator or administrator access is required.")


async def progress_view(run, template, names, *, detail=False):
    view = await run_view(run, template, readonly=True)
    definitions = {step["id"]: step for step in template["steps"]}
    states = {state["stepId"]: state for state in run["stepStates"]}
    active = [step for step in view["steps"] if not definitions[step["id"]].get("archivedAt")]
    tasks = [step for step in active if step["type"] == "task"]
    timestamps = [run["createdAt"]] + [
        state[field] for state in run["stepStates"]
        for field in ("openedAt", "completedAt", "workSubmittedAt", "pulseLastPollAt", "challengeStoppedAt")
        if state.get(field)
    ]
    result = {
        "id": run["_id"], "templateId": run["templateId"],
        "learnerId": run["learnerId"], "learnerName": names.get(run["learnerId"], run["learnerId"]),
        "name": view["name"],
        "status": "completed" if view["finished"] else "in_progress" if states else "not_started",
        "completed": view["completed"], "skipped": view["skipped"], "total": view["total"],
        "completedTasks": sum(step["status"] == "completed" for step in tasks), "totalTasks": len(tasks),
        "progress": view["progress"], "createdAt": run["createdAt"],
        "lastActivityAt": max(timestamps), "firstFinishedAt": run.get("firstFinishedAt"),
        "stepProgress": [{"id": step["id"], "title": step["title"], "status": step["status"]} for step in active],
    }
    if detail:
        result.update(description=view["description"], templateRevision=view["templateRevision"], steps=[
            {"id": step["id"], "title": step["title"], "type": step["type"], "status": step["status"],
             "archived": bool(definitions[step["id"]].get("archivedAt")),
             "openedAt": states.get(step["id"], {}).get("openedAt"), "completedAt": step["completedAt"],
             "availableAt": step["availableAt"], "reasons": step["reasons"]}
            for step in view["steps"]
        ])
    return result


async def list_progress(user, skip=0, limit=100, *, token=None, detail=False, run_ids=None):
    require_access(user)
    filters = {"_id": {"$in": [str(identifier) for identifier in run_ids]}} if run_ids is not None else {}
    page = await list_page(db.learning_path_runs, filters, skip, limit)
    if not page["items"]:
        return page
    runs = [{**item, "_id": item["id"], "stepStates": []} for item in page["items"]]
    templates = await attach_steps([
        template async for template in db.learning_path_templates.find(
            {"_id": {"$in": list({run["templateId"] for run in runs})}}
        )
    ])
    by_template = {template["_id"]: template for template in templates}
    by_run = {run["_id"]: run for run in runs}
    async for state in db.learning_path_run_steps.find({"runId": {"$in": list(by_run)}}):
        by_run[state["runId"]]["stepStates"].append(state)
    names = await resolve_names((run["learnerId"] for run in runs), user, token)
    page["items"] = [await progress_view(run, by_template[run["templateId"]], names, detail=detail) for run in runs]
    return page


async def export_progress_csv(user, run_ids, *, token=None):
    require_access(user)
    summary_fields = (
        ("Learner ID", "learnerId"), ("Learner name", "learnerName"),
        ("Run ID", "id"), ("Path ID", "templateId"), ("Path", "name"),
        ("Description", "description"), ("Template revision", "templateRevision"),
        ("Run status", "status"), ("Completed tasks", "completedTasks"), ("Total tasks", "totalTasks"),
        ("Completed steps", "completed"), ("Skipped steps", "skipped"), ("Total steps", "total"),
        ("Progress (%)", "progress"), ("Created at", "createdAt"),
        ("Last recorded activity at", "lastActivityAt"), ("First finished at", "firstFinishedAt"),
    )
    step_fields = (
        ("Step ID", "id"), ("Step", "title"), ("Step type", "type"), ("Step status", "status"),
        ("Archived step", "archived"), ("Opened at", "openedAt"),
        ("Completed at", "completedAt"), ("Available at", "availableAt"),
    )

    def csv_value(value):
        if value is None:
            return ""
        value = value.isoformat() if isinstance(value, datetime) else str(value)
        # Match the submissions export's protection against spreadsheet formulas.
        if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    output = io.StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow([label for label, _ in (*summary_fields, *step_fields)] + ["Unlock reasons (JSON)"])
    skip = 0
    while True:
        page = await list_progress(user, skip, 100, token=token, detail=True, run_ids=run_ids)
        for run in page["items"]:
            # Keep participants whose current path has no visible steps in the export.
            for step in run["steps"] or [{}]:
                writer.writerow([
                    csv_value(value) for value in (
                        *(run.get(key) for _, key in summary_fields),
                        *(step.get(key) for _, key in step_fields),
                        json.dumps(step.get("reasons", []), ensure_ascii=False),
                    )
                ])
        skip += len(page["items"])
        if not page["items"] or skip >= page["total"]:
            break
    return output.getvalue()


async def get_progress(run_id, user, *, token=None):
    require_access(user)
    run = await db.learning_path_runs.find_one({"_id": str(run_id)})
    if not run:
        raise not_found()
    template = await template_document(run["templateId"])
    names = await resolve_names([run["learnerId"]], user, token)
    return await progress_view(await attach_states(run), template, names, detail=True)
