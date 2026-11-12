"""Shared visibility policy for templates, personal runs and their models."""

from modeling_api.core.errors import not_found
from modeling_api.db.client import db


def can_open_locked_steps(user):
    return user.is_admin or user.global_role == "MODERATOR" or "MODERATOR" in user.roles


def template_visibility(template):
    # Preserve the former archive behavior for existing databases.
    return {"draft": "hidden", "archived": "unlisted"}.get(
        template["status"], template["status"]
    )


def require_template_access(template, user, *, existing_run=False):
    if user.is_admin:
        return
    visibility = template_visibility(template)
    if visibility not in ("published", "unlisted") or (
        visibility == "unlisted" and not existing_run
    ):
        raise not_found()


async def require_run_access(run, user):
    template = await db.learning_path_templates.find_one(
        {"_id": run["templateId"]}, {"status": 1}
    )
    if not template:
        raise not_found()
    require_template_access(template, user, existing_run=True)


async def accessible_task_releases(task_id, user):
    """Private task releases shared through paths accessible to this learner."""
    releases = set()
    async for step in db.learning_path_template_steps.find(
        {"kind": "task", "task.taskId": str(task_id), "archivedAt": None}
    ):
        template = await db.learning_path_templates.find_one(
            {"_id": step["templateId"], "stepIds": step["_id"]}
        )
        if not template:
            continue
        visibility = template_visibility(template)
        if visibility == "published" or (
            visibility == "unlisted"
            and await db.learning_path_runs.find_one(
                {"templateId": step["templateId"], "learnerId": user.id}, {"_id": 1}
            )
        ):
            releases.add(step["task"]["releaseId"])
    return releases


async def require_model_access(model_id, user):
    if user.is_admin:
        return
    state = await db.learning_path_run_steps.find_one(
        {"modelId": str(model_id)}, {"runId": 1}
    )
    if state:
        run = await db.learning_path_runs.find_one(
            {"_id": state["runId"], "learnerId": user.id}, {"templateId": 1}
        )
        if not run:
            raise not_found()
        await require_run_access(run, user)
