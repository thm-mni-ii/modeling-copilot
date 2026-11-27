"""Publish EPK as a global language with its case studies; existing content stays untouched."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration
from modeling_api.db.migrations.resources import load_data
from modeling_api.db.migrations.versions.v00_initial_data.definitions import SYSTEM_OWNER_ID
from modeling_api.db.store import utcnow
from modeling_api.schemas.languages import CreateLanguageVersion
from modeling_api.schemas.models import Model, ModelVersion
from modeling_api.schemas.tasks import Task, TaskVersion

MIGRATION_ID = "23_epk"
PREREQUISITE = "22_help_choice_labels"
LANGUAGE_ID = "2a611b6a-bd2a-4b08-a503-154920b428d9"
VERSION_ID = "e90bc975-7d92-46b5-b81f-6e4b03e27fec"
CASES = (
    "urlaubsantrag.json",
    "bestellabwicklung.json",
    "kfz_schadensmeldung.json",
    "reklamation.json",
)


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await publish(apply=False)
    return await run_migration(MIGRATION_ID, lambda: publish(apply=True))


async def publish(*, apply):
    now = utcnow()
    # Alle Seed-Daten prüfen, bevor etwas geschrieben wird; ungültige sollen hier auffallen und nicht erst im Editor
    language = load_data(MIGRATION_ID, "epk.json")
    CreateLanguageVersion.model_validate({"baseVersionId": None, "kind": "release", "data": language})
    cases = [(case, prepare_case(case, now)) for case in (load_data(MIGRATION_ID, name) for name in CASES)]

    new_language = not await db.languages.find_one({"_id": LANGUAGE_ID})
    if new_language:
        print(f'{"Publish" if apply else "Would publish"}: EPK release 1.0')
        if apply:
            await publish_language(language, now)
    else:
        print("EPK already exists; keeping the language.")

    count = int(new_language)
    for case, documents in cases:
        name = case["task"]["name"]
        # Task und Musterlösung gehören zusammen: Ist eine von beiden schon anderweitig angelegt, bleibt das Paar
        if await exists_independently(case):
            print(f"{name} already exists; keeping task and sample solution.")
            continue
        for reference in case["task"]["version"]["workspaceLanguages"]:
            # In der Vorschau gibt es das geplante Sprach-Release noch nicht
            planned = new_language and reference["versionId"] == VERSION_ID
            if not planned and not await db.language_versions.find_one({
                "_id": reference["versionId"], "languageId": reference["languageId"], "kind": "release",
            }):
                raise RuntimeError("The required EPK language release is missing.")
        print(f'{"Publish" if apply else "Would publish"}: {name} with sample solution')
        count += 1
        if apply:
            for collection, identifier, fields, timestamps in documents:
                await collection.update_one(
                    {"_id": identifier},
                    {"$setOnInsert": {**fields, "createdAt": now, **timestamps}}, upsert=True,
                )
    return count


async def publish_language(data, created_at):
    await db.language_versions.update_one(
        {"_id": VERSION_ID},
        {"$setOnInsert": {
            "languageId": LANGUAGE_ID, "versionNumber": "1.0",
            "createdBy": SYSTEM_OWNER_ID, "createdAt": created_at,
            "kind": "release", "releaseName": "Initial release", "description": None,
            "includedLanguageVersions": [], "data": data,
        }},
        upsert=True,
    )
    await db.languages.update_one(
        {"_id": LANGUAGE_ID},
        {"$setOnInsert": {
            "createdAt": created_at, "name": "EPK", "parent": None,
            "ownerId": SYSTEM_OWNER_ID, "latestVersionId": VERSION_ID, "archivedAt": None,
        }},
        upsert=True,
    )


def prepare_case(case, now):
    """Validate one case and return its documents, referenced content first."""
    task, model = case["task"], case["model"]
    task_version, model_version = task["version"], model["version"]
    task_fields = {key: value for key, value in task.items() if key not in {"id", "version"}}
    model_fields = {key: value for key, value in model.items() if key not in {"id", "version"}}
    task_version_fields = {key: value for key, value in task_version.items() if key != "id"}
    model_version_fields = {key: value for key, value in model_version.items() if key != "id"}
    Task.model_validate({"id": task["id"], "createdAt": now, **task_fields})
    TaskVersion.model_validate({"id": task_version["id"], "createdAt": now, **task_version_fields})
    Model.model_validate({"id": model["id"], "createdAt": now, "updatedAt": now, **model_fields})
    ModelVersion.model_validate({"id": model_version["id"], "createdAt": now, **model_version_fields})
    task_reference = {"taskId": task["id"], "versionId": task_version["id"]}
    if ({"modelId": model["id"], "versionId": model_version["id"]} not in task_version["data"]["sampleSolutions"]
            or model["taskVersion"] != task_reference
            or model_version["taskVersion"] != task_reference):
        raise RuntimeError(f"Invalid sample solution references: {task['name']}.")
    return [
        (db.model_versions, model_version["id"], model_version_fields, {}),
        (db.models, model["id"], model_fields, {"updatedAt": now}),
        (db.task_version, task_version["id"], task_version_fields, {}),
        (db.task, task["id"], task_fields, {}),
    ]


async def exists_independently(case):
    """True if the task or model exists without the release of this migration (not a resumed run)."""
    for identities, versions, key in ((db.task, db.task_version, "task"), (db.models, db.model_versions, "model")):
        entry = case[key]
        if (await identities.find_one({"_id": entry["id"]})
                and not await versions.find_one({"_id": entry["version"]["id"]})):
            return True
    return False
