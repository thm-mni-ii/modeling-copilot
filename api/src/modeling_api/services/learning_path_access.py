"""Shared visibility policy for templates, personal runs and their models."""

from modeling_api.core.errors import not_found
from modeling_api.db.client import db


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
