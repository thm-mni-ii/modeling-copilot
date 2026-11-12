"""JSON files in an evaluation workspace; no service or pipeline execution logic."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

VERSION = 1
INPUT_SCHEMA = "evaluation-input/v1"


def input_hash(bundle: dict) -> str:
    """Hash frozen input; sort identity sets while preserving ordered content."""
    content = deepcopy(bundle)
    content.pop("inputHash", None)
    content["models"].sort(key=lambda model: model["source"]["key"])
    content["languages"].sort(key=lambda language: (language["languageId"], language["versionId"]))
    language_owners = [content["task"], *[model["snapshot"] for model in content["models"]]]
    for owner in language_owners:
        if "workspaceLanguages" in owner:
            owner["workspaceLanguages"].sort(key=lambda reference: (reference["languageId"], reference["versionId"]))
    for language in content["languages"]:
        language["includedLanguageVersions"].sort(key=lambda reference: (reference["languageId"], reference["versionId"]))
    solutions = content["task"]["data"].get("sampleSolutions")
    if isinstance(solutions, list):
        solutions.sort(key=lambda reference: (reference["modelId"], reference["versionId"]))
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("identifier must contain 1-100 letters, digits, underscores or hyphens")
    return value


class Workspace:
    def __init__(self, evaluation_id: str, root: str | Path | None = None):
        self.evaluation_id = identifier(evaluation_id)
        self.root = (Path(root or os.environ.get("WORKFLOW_DATA_ROOT", "/work/evaluations")) / self.evaluation_id).resolve()

    def path(self, relative: str) -> Path:
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError("artifact path must be a non-empty relative path")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("artifact path leaves the evaluation workspace")
        return path

    def read(self, relative: str) -> dict:
        value = json.loads(self.path(relative).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"artifact must be a JSON object: {relative}")
        return value

    def write(self, relative: str, value: dict) -> str:
        """Atomic, immutable publication; identical retries are idempotent."""
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        try:
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                if path.read_bytes() != encoded:
                    raise ValueError(f"artifact already exists with different content: {relative}")
        finally:
            temporary_path.unlink(missing_ok=True)
        return relative

    def snapshot(self) -> dict:
        value = self.read("inputs/evaluation-input.json")
        if value.get("schemaVersion") != VERSION or value.get("schema") != INPUT_SCHEMA:
            raise ValueError("unsupported evaluation input schema")
        if value.get("evaluationId") != self.evaluation_id:
            raise ValueError("input evaluation ID does not match the workspace")
        if not isinstance(value.get("comparisonConfig"), dict):
            raise ValueError("comparisonConfig must be a JSON object")
        if value.get("inputHash") != input_hash(value):
            raise ValueError("input hash does not match the frozen snapshot")
        return value


def workspace() -> Workspace:
    evaluation_id = os.environ.get("WORKFLOW_EVALUATION_ID")
    if not evaluation_id:
        raise ValueError("WORKFLOW_EVALUATION_ID is required for workspace access")
    return Workspace(evaluation_id)


def read_input(path: Path | None = None) -> dict:
    """Read a JSON object from a file, the environment, or stdin."""
    relative = os.environ.get("WORKFLOW_INPUT_PATH")
    if path is not None:
        raw = path.read_text(encoding="utf-8-sig")
    elif relative is not None:
        if "TEMPLATE_INPUT" in os.environ:
            raise ValueError("provide either WORKFLOW_INPUT_PATH or TEMPLATE_INPUT")
        store = workspace()
        store.snapshot()
        return store.read(relative)
    else:
        raw = os.environ.get("TEMPLATE_INPUT")
        if raw is None:
            raw = "{}" if os.environ.get("WORKFLOW_EVALUATION_ID") else sys.stdin.read()
    if not raw.strip():
        raise ValueError("provide JSON via TEMPLATE_INPUT, stdin or --input, or set WORKFLOW_EVALUATION_ID")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("a JSON object is required")
    return value


def write_output(value: dict, path: Path | None = None) -> None:
    """Publish JSON at the explicitly requested path and emit it for Dagu."""
    relative = os.environ.get("WORKFLOW_OUTPUT_PATH")
    if relative is not None:
        store = workspace()
        store.snapshot()
        store.write(relative, value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if path is not None:
        path.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
