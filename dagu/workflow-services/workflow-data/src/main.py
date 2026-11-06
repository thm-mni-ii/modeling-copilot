#!/usr/bin/env python3
"""Validate and publish the complete frozen evaluation input exactly once."""
import base64
import gzip
import json
import os
import sys
from typing import Literal, TypedDict

from workflow_io import INPUT_SCHEMA, VERSION, Workspace, identifier, workspace, write_output


class EvaluationInput(TypedDict):
    schemaVersion: Literal[1]
    schema: Literal["evaluation-input/v1"]
    evaluationId: str
    task: dict
    models: list[dict]
    languages: list[dict]


def prepare(store: Workspace, bundle: EvaluationInput) -> dict:
    if bundle.get("schemaVersion") != VERSION or bundle.get("schema") != INPUT_SCHEMA:
        raise ValueError("unsupported evaluation input schema")
    if bundle.get("evaluationId") != store.evaluation_id:
        raise ValueError("input evaluation ID does not match the workspace")
    if not isinstance(bundle.get("task"), dict):
        raise ValueError("complete task snapshot is required")
    models, definitions = bundle.get("models"), bundle.get("languages")
    if not isinstance(models, list) or not models or not isinstance(definitions, list):
        raise ValueError("complete models and language definitions are required")
    languages = set()
    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError("each language definition must be an object")
        key = (definition["languageId"], definition["versionId"])
        if not all(isinstance(value, str) and value for value in key):
            raise ValueError("language and version identifiers must be non-empty strings")
        if key in languages or not isinstance(definition.get("data"), dict):
            raise ValueError("duplicate or incomplete language version")
        languages.add(key)
        if not isinstance(definition.get("includedLanguageVersions"), list):
            raise ValueError("includedLanguageVersions must be an array")
    if any(not isinstance(model, dict) or not isinstance(model.get("source"), dict) or not isinstance(model.get("snapshot"), dict) for model in models):
        raise ValueError("each model needs source and snapshot objects")
    def check_references(references: object) -> None:
        if not isinstance(references, list):
            raise ValueError("language references must be an array")
        for reference in references:
            if not isinstance(reference, dict) or not all(isinstance(reference.get(key), str) for key in ("languageId", "versionId")):
                raise ValueError("language references need languageId and versionId")
            if (reference["languageId"], reference["versionId"]) not in languages:
                raise ValueError("a referenced language version is missing from the frozen input")

    keys = [identifier(model["source"]["key"]) for model in models]
    if len(keys) != len(set(keys)) or keys.count("submission") != 1:
        raise ValueError("model keys must be unique and include one submission")
    for model in models:
        source, snapshot = model["source"], model["snapshot"]
        if not all(isinstance(source.get(key), str) and source[key] for key in ("key", "role", "label", "modelId", "versionId")):
            raise ValueError("complete model source metadata is required")
        if source["role"] != ("submission" if source["key"] == "submission" else "reference"):
            raise ValueError("model role does not match its key")
        data = snapshot.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("xml"), str) or not data["xml"].strip():
            raise ValueError("model snapshot must contain complete XML")
        if not isinstance(snapshot.get("workspaceLanguages"), list):
            raise ValueError("workspaceLanguages must be an array")
        check_references(snapshot["workspaceLanguages"])
    for definition in definitions:
        check_references(definition["includedLanguageVersions"])
    check_references(bundle["task"].get("workspaceLanguages", []))
    # Publish only after all checks pass; no parser-specific requests or indexes.
    reference = store.write("inputs/evaluation-input.json", bundle)
    return {"schemaVersion": VERSION, "schema": "workflow-result/v1", "status": "ok", "mode": "data",
            "capability": "workflow-input", "summary": f"{len(models)} vollständige Modell-Snapshots bereitgestellt",
            "result": {"evaluationId": store.evaluation_id, "inputSnapshot": reference, "modelCount": len(models)}}


def main() -> int:
    try:
        encoded = os.environ["EVALUATION_INPUT_GZIP_BASE64"]
        bundle = json.loads(gzip.decompress(base64.b64decode(encoded, validate=True)).decode("utf-8"))
        if not isinstance(bundle, dict):
            raise ValueError("evaluation input must be a JSON object")
        result = prepare(workspace(), bundle)
        write_output(result)
        return 0
    except (ValueError, TypeError, KeyError, OSError, EOFError) as error:
        print(f"[workflow-data] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
