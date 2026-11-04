"""Initialize an empty database or upgrade a validated main/branch baseline.

Run with PYTHONPATH=api/src, before migration 01 and before starting the API:
  python -m modeling_api.db.migrations.versions.v00_initial_data
  python -m modeling_api.db.migrations.versions.v00_initial_data --apply
The preview is read-only. Existing releases and admin metadata are preserved.
"""

from modeling_api.db.migrations.versions.v00_initial_data import initial_data as seed
from modeling_api.db.migrations.versions.v00_initial_data import definitions
from modeling_api.db.client import create_indexes, db
from modeling_api.db.help_questionnaires import HELP_SURVEY_IDS
from modeling_api.db.migrations import BASELINE_ID, run_migration

MIGRATION_ID = BASELINE_ID


async def validate_baseline(*, legacy=False):
    """Check fixed releases and references while allowing mutable admin metadata."""
    async def require(collection, identifier, **fields):
        document = await db[collection].find_one({"_id": str(identifier)})
        if document is None or any(document.get(key) != value for key, value in fields.items()):
            raise RuntimeError(f"Baseline missing or incompatible: {collection}/{identifier}; existing data was not reseeded.")
        return document

    languages = definitions.SEED_LANGUAGES[:1] if legacy else definitions.SEED_LANGUAGES
    for language_id, version_id, _, filename in languages:
        language = await require("languages", language_id)
        await require("language_versions", version_id, languageId=language_id,
                      kind="release", data=definitions.load_data(filename))
        await require("language_versions", language.get("latestVersionId"), languageId=language_id)

    for name in (("order_management",) if legacy else definitions.SEED_EXAMPLES):
        for task in definitions.load_tasks(name):
            current = await require("task", task["id"])
            version = task["version"]
            await require("task_version", version["id"], taskId=task["id"],
                          kind="release", data=version["data"],
                          workspaceLanguages=version["workspaceLanguages"])
            await require("task_version", current.get("latestVersionId"), taskId=task["id"])
        model = definitions.load_sample_solution(name)
        if model:
            current = await require("models", model["id"])
            await require("model_versions", model["version"]["id"], modelId=model["id"],
                          kind="release", data=model["version"]["data"])
            await require("model_versions", current.get("latestVersionId"), modelId=model["id"])

    if legacy:
        return

    entry = definitions.MANIFEST["entryCourse"]
    surveys = list(HELP_SURVEY_IDS.values()) + [
        entry[key]["id"] for key in ("questionnaire", "completion", "attitudes")
    ] + [
        survey["id"]
        for filename in ("entry_pulse_surveys.json", "example_surveys.json")
        for survey in definitions.load_data(filename)["surveys"]
    ]
    for survey_id in surveys:
        survey = await require("surveys", survey_id)
        for key in ("latestVersionId", "activeReleaseId"):
            if survey.get(key):
                await require("survey_versions", survey[key], surveyId=survey_id)
        if not survey.get("latestVersionId"):
            raise RuntimeError(f"Baseline survey {survey_id} has no current version.")

    for template_data in definitions.load_data("learning_paths.json")["templates"]:
        template_id = template_data["id"]
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
    # Main only contains UML and the Order Management example. Validate that
    # baseline before adding the branch's new seeds, never require them upfront.
    await validate_baseline(legacy=True)
    print("Adopt main baseline and add missing seed data; preserve existing records."
          if apply else "Would adopt main baseline and add missing seed data.")
    if apply:
        await db.schema_migrations.update_one(
            {"_id": MIGRATION_ID}, {"$set": {"mode": "adopt"}},
        )
        await create_indexes()
        await seed.seed_initial_data()
        await validate_baseline()
    return 0


async def migrate(*, apply=False):
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await prepare_baseline(apply=False)
    return await run_migration(MIGRATION_ID, lambda: prepare_baseline(apply=True))

