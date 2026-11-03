"""Read migration 00's fixed identities and JSON resources; no database writes."""

from modeling_api.db.migrations.registry import BASELINE_ID
from modeling_api.db.migrations.resources import load_data as load_migration_data, resource_path


def load_data(filename: str) -> dict:
    return load_migration_data(BASELINE_ID, filename)


MANIFEST = load_data("manifest.json")
if MANIFEST.get("schemaVersion") != 1:
    raise ValueError("Unsupported migration 00 manifest format.")

SYSTEM_OWNER_ID = MANIFEST["systemOwnerId"]
ORDER_MANAGEMENT_LEARNING_PATH_ID = MANIFEST["learningPathIds"]["orderManagement"]
ENTRY_LEARNING_PATH_ID = MANIFEST["learningPathIds"]["entry"]
SEED_LANGUAGES = tuple(
    (language["id"], language["versionId"], language["name"], language["filename"])
    for language in MANIFEST["languages"]
)
SEED_EXAMPLES = tuple(MANIFEST["examples"])
_LANGUAGES = {language["filename"]: language for language in MANIFEST["languages"]}
UML_CLASS_DIAGRAM_ID = _LANGUAGES["uml_class_diagram.json"]["id"]
UML_CLASS_DIAGRAM_VERSION_ID = _LANGUAGES["uml_class_diagram.json"]["versionId"]
ERM_ID = _LANGUAGES["erm.json"]["id"]
ERM_VERSION_ID = _LANGUAGES["erm.json"]["versionId"]
SERM_ID = _LANGUAGES["serm.json"]["id"]
SERM_VERSION_ID = _LANGUAGES["serm.json"]["versionId"]


def load_tasks(name: str) -> list[dict]:
    payload = load_data(f"{name}_tasks.json")
    tasks = payload.get("tasks")
    if payload.get("schemaVersion") != 1 or not isinstance(tasks, list):
        raise ValueError(f"Unsupported {name} seed-data format.")
    return tasks


def load_sample_solution(name: str) -> dict | None:
    filename = f"{name}_sample_solution.json"
    if not resource_path(BASELINE_ID, filename).exists():
        return None
    payload = load_data(filename)
    model = payload.get("model")
    if payload.get("schemaVersion") != 1 or not isinstance(model, dict):
        raise ValueError(f"Unsupported {name} sample-solution format.")
    return model
