"""Apply the new order and wording of the help answers to existing learning paths."""

from uuid import UUID, uuid5

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.registry import BASELINE_ID
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.store import utcnow
from modeling_api.schemas.learning_paths import HelpRequestConfig
from modeling_api.services import help_questionnaire

MIGRATION_ID = "22_help_choice_labels"
PREREQUISITE = "21_task_help_feedback"


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await update_paths(apply=False)
    return await run_migration(MIGRATION_ID, lambda: update_paths(apply=True))


def update_edit(choices):
    """Reorder customized answers; rename only texts still equal to the previous default."""
    elements = load_data(BASELINE_ID, "help_questionnaires.json")["reflection"]["definition"]["elements"]
    previous = next(q for q in elements if q["name"] == "support_need")["choices"]
    defaults = {f"support_need_{index}": text for index, text in enumerate(previous, 1)}
    return help_questionnaire.order_support_choices(
        {**choice, "text": help_questionnaire.SUPPORT_CHOICES.get(choice["id"], choice["text"])}
        if choice["text"] == defaults.get(choice["id"]) else choice
        for choice in choices
    )


async def update_paths(*, apply):
    changed = 0
    async for template in db.learning_path_templates.find({"$or": [
        {"helpRequests.enabled": True},
        {"helpRequests.questionEdits.support_need": {"$exists": True}},
    ]}):
        stored = template["helpRequests"]
        edit = (stored.get("questionEdits") or {}).get("support_need")
        choices = update_edit(edit["choices"]) if edit else None
        edit_changed = bool(edit) and choices != edit["choices"]
        config_data = dict(stored)
        if edit_changed:
            config_data["questionEdits"] = {**stored["questionEdits"], "support_need": {**edit, "choices": choices}}
        config = HelpRequestConfig.model_validate(config_data)
        enabled = bool(stored.get("enabled"))
        if not edit_changed:
            if not enabled:
                continue
            survey = await db.surveys.find_one({"_id": str(uuid5(UUID(template["_id"]), "help-questionnaire"))})
            if survey and survey["definition"] == help_questionnaire.definition(config):
                continue
        changed += 1
        print(f"{'Update' if apply else 'Would update'} help answers for learning path {template['_id']}.")
        if not apply:
            continue
        # Releases are unique per path revision, so changed answers require a new one.
        revision = template["revision"] + 1
        fields = {"updatedAt": utcnow()}
        if edit_changed:
            fields["helpRequests.questionEdits.support_need.choices"] = choices
        result = await db.learning_path_templates.update_one(
            {"_id": template["_id"], "revision": template["revision"]},
            {"$inc": {"revision": 1}, "$set": fields},
        )
        if not result.matched_count:
            raise RuntimeError("The learning path changed during migration. Retry with path writes stopped.")
        if enabled:
            await help_questionnaire.publish(
                template["_id"], template["title"], revision, config, template.get("createdBy", ""))
    return changed
