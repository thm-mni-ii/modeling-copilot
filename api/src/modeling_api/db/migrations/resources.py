"""Read JSON resources owned by a specific migration prefix."""

import json
from pathlib import Path


def resource_path(migration_id: str, filename: str) -> Path:
    return Path(__file__).with_name("versions") / f"v{migration_id}" / filename


def load_data(migration_id: str, filename: str) -> dict:
    return json.loads(resource_path(migration_id, filename).read_text(encoding="utf-8"))
