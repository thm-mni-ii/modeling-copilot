"""Initialize an empty database or adopt a validated existing dev baseline.

Run with PYTHONPATH=api/src, before migration 01 and before starting the API:
  python api/scripts/00_initial_data.py
  python api/scripts/00_initial_data.py --apply
The preview is read-only. Existing application data is never seeded again.
"""

import argparse
import asyncio
from uuid import UUID, uuid5

from modeling_api.db import initial_data as seed
from modeling_api.db.client import client, create_indexes, db
from modeling_api.db.migrations import BASELINE_ID, run_migration

MIGRATION_ID = BASELINE_ID


async def validate_baseline():
    """Check fixed releases and references while allowing mutable admin metadata."""
    async def require(collection, identifier, **fields):
        document = await db[collection].find_one({"_id": str(identifier)})
        if document is None or any(document.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Baseline missing or incompatible: {collection}/{identifier}; existing data was not reseeded.")
        return document

    for language_id, version_id, _, filename in seed._SEED_LANGUAGES:
        language = await require("languages", language_id)
        await require("language_versions", version_id, languageId=language_id,
                      kind="release", data=seed._load_initial_data(filename))
        await require("language_versions", language.get("latestVersionId"), languageId=language_id)

    for name in seed._SEED_EXAMPLES:
        for task in seed._tasks(name):
            current = await require("task", task["id"])
            version = task["version"]
            await require("task_version", version["id"], taskId=task["id"],
                          kind="release", data=version["data"],
                          workspaceLanguages=version["workspaceLanguages"])
            await require("task_version", current.get("latestVersionId"), taskId=task["id"])
        model = seed._sample_solution(name)
        if model:
            current = await require("models", model["id"])
            await require("model_versions", model["version"]["id"], modelId=model["id"],
                          kind="release", data=model["version"]["data"])
            await require("model_versions", current.get("latestVersionId"), modelId=model["id"])

    order = UUID(seed.ORDER_MANAGEMENT_LEARNING_PATH_ID)
    entry = UUID(seed.ENTRY_LEARNING_PATH_ID)
    survey_example = uuid5(order, "survey-example")
    surveys = list(seed.HELP_SURVEY_IDS.values()) + [
        str(uuid5(entry, name)) for name in (
            "entry-questionnaire", "task-completion-questionnaire", "help-attitudes-questionnaire",
            "pulse:understanding", "pulse:support_need",
        )
    ] + [str(uuid5(survey_example, f"survey:{index}")) for index in range(3)] + [
        str(uuid5(order, f"pulse:{name}")) for name in ("random_understand", "random_need")
    ]
    for survey_id in surveys:
        survey = await require("surveys", survey_id)
        for key in ("latestVersionId", "activeReleaseId"):
            if survey.get(key):
                await require("survey_versions", survey[key], surveyId=survey_id)
        if not survey.get("latestVersionId"):
            raise RuntimeError(f"Baseline survey {survey_id} has no current version.")

    for template_id in (order, entry, survey_example, uuid5(order, "pulse-example")):
        template = await require("learning_path_templates", template_id)
        for step_id in template.get("stepIds", []):
            await require("learning_path_template_steps", step_id, templateId=str(template_id))


async def prepare_baseline(*, apply):
    record = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    initialize = record is not None and record.get("mode") == "initialize"
    if not initialize:
        initialize = True
        for name in await db.list_collection_names():
            if name != "schema_migrations" and await db[name].find_one({}, {"_id": 1}):
                initialize = False
                break
    if initialize:
        print("Initialize empty database." if apply else "Would initialize empty database.")
        if apply:
            # Remember this before the first seed write so interrupted initialization can resume.
            await db.schema_migrations.update_one(
                {"_id": MIGRATION_ID}, {"$set": {"mode": "initialize"}},
            )
            await create_indexes()
            await seed.seed_initial_data()
            await validate_baseline()
        return 1
    await validate_baseline()
    print("Adopt validated existing baseline; application data stays unchanged.")
    if apply:
        await db.schema_migrations.update_one(
            {"_id": MIGRATION_ID}, {"$set": {"mode": "adopt"}},
        )
        await create_indexes()
    return 0


async def migrate(*, apply=False):
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await prepare_baseline(apply=False)
    return await run_migration(MIGRATION_ID, lambda: prepare_baseline(apply=True))


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Initialize or adopt; otherwise only preview.")
    args = parser.parse_args()
    try:
        await migrate(apply=args.apply)
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
