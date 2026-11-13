"""Stable content hashes and the resources actually used by this service."""

import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import unicodedata

import workflow_io

SERVICE = "synonym-matching"
SERVICE_ROOT = Path(__file__).resolve().parents[2]


def content_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def producer_metadata():
    files = {"src/workflow_io.py": Path(workflow_io.__file__)}
    files.update({path.relative_to(SERVICE_ROOT).as_posix(): path for path in (SERVICE_ROOT / "src").rglob("*.py")})
    files.update({path.relative_to(SERVICE_ROOT).as_posix(): path for path in (SERVICE_ROOT / "schemas").glob("*.json")})
    return {
        "service": SERVICE, "version": "1.0.0",
        "resourceHash": content_hash({name: path.read_text(encoding="utf-8") for name, path in files.items()}),
        "runtime": {"python": platform.python_version(), "unicode": unicodedata.unidata_version},
        "packages": {name: version(name) for name in (
            "numpy", "rapidfuzz", "sentence-transformers", "transformers", "torch",
            "tokenizers", "huggingface-hub", "sentencepiece", "safetensors", "jsonschema",
        )},
    }
