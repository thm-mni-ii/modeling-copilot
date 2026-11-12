#!/usr/bin/env python3
"""Validate and publish the complete frozen evaluation input exactly once."""
import base64
import gzip
import json
import os
import sys
from typing import Literal, NotRequired, TypedDict

from workflow_io import INPUT_SCHEMA, VERSION, Workspace, identifier, input_hash, workspace, write_output


class EvaluationInput(TypedDict):
    schemaVersion: Literal[1]
    schema: Literal["evaluation-input/v1"]
    evaluationId: str
    task: dict
    models: list[dict]
    languages: list[dict]
    comparisonConfig: dict
    inputHash: NotRequired[str]


def prepare(store: Workspace, bundle: EvaluationInput) -> dict:
    if bundle.get("schemaVersion") != VERSION or bundle.get("schema") != INPUT_SCHEMA:
        raise ValueError("unsupported evaluation input schema")
    if bundle.get("evaluationId") != store.evaluation_id:
        raise ValueError("input evaluation ID does not match the workspace")
    task = bundle.get("task")
    if not isinstance(task, dict) or not isinstance(task.get("data"), dict) or not all(
        isinstance(task.get(key), str) and task[key] for key in ("taskId", "versionId")
    ):
        raise ValueError("complete task snapshot is required")
    bundle = {**bundle, "comparisonConfig": bundle.get("comparisonConfig", {})}
    if not isinstance(bundle["comparisonConfig"], dict):
        raise ValueError("comparisonConfig must be a JSON object")
    models, definitions = bundle.get("models"), bundle.get("languages")
    if not isinstance(models, list) or not models or not isinstance(definitions, list):
        raise ValueError("complete models and language definitions are required")
    languages = set()
    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError("each language definition must be an object")
        key = (definition.get("languageId"), definition.get("versionId"))
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
    expected_keys = {"submission", *(f"reference_{index}" for index in range(1, len(models)))}
    if len(models) < 2 or len(keys) != len(set(keys)) or set(keys) != expected_keys:
        raise ValueError("model keys must include one submission and consecutive reference keys")
    for model in models:
        source, snapshot = model["source"], model["snapshot"]
        if not all(isinstance(source.get(key), str) and source[key] for key in ("key", "role", "label", "modelId", "versionId")):
            raise ValueError("complete model source metadata is required")
        if source["role"] != ("submission" if source["key"] == "submission" else "reference"):
            raise ValueError("model role does not match its key")
        if any(snapshot.get(key) != source[key] for key in ("modelId", "versionId")):
            raise ValueError("model source does not match its snapshot version")
        task_reference = snapshot.get("taskVersion")
        if task_reference is not None and task_reference != {key: task[key] for key in ("taskId", "versionId")}:
            raise ValueError("model task reference does not match the frozen task release")
        data = snapshot.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("xml"), str) or not data["xml"].strip():
            raise ValueError("model snapshot must contain complete XML")
        if not isinstance(snapshot.get("workspaceLanguages"), list):
            raise ValueError("workspaceLanguages must be an array")
        check_references(snapshot["workspaceLanguages"])
    for definition in definitions:
        check_references(definition["includedLanguageVersions"])
    check_references(bundle["task"].get("workspaceLanguages", []))
    expected_references = task["data"].get("sampleSolutions")
    if not isinstance(expected_references, list) or any(
        not isinstance(reference, dict) or not all(isinstance(reference.get(key), str) and reference[key]
                                                 for key in ("modelId", "versionId"))
        for reference in expected_references
    ):
        raise ValueError("the task release must list its reference model versions")
    reference_versions = sorted((model["source"]["modelId"], model["source"]["versionId"])
                                for model in models if model["source"]["role"] == "reference")
    if reference_versions != sorted((reference["modelId"], reference["versionId"]) for reference in expected_references):
        raise ValueError("reference models do not match the complete task release reference list")
    digest = input_hash(bundle)
    if "inputHash" in bundle and bundle["inputHash"] != digest:
        raise ValueError("input hash does not match the frozen snapshot")
    bundle = {**bundle, "inputHash": digest}
    # Publish only after all checks pass; no parser-specific requests or indexes.
    reference = store.write("inputs/evaluation-input.json", bundle)
    return {"schemaVersion": VERSION, "schema": "workflow-result/v1", "status": "ok", "mode": "data",
            "capability": "workflow-input", "summary": f"{len(models)} vollständige Modell-Snapshots bereitgestellt",
            "result": {"evaluationId": store.evaluation_id, "inputHash": digest, "inputSnapshot": reference,
                       "modelKeys": keys, "referenceKeys": [key for key in keys if key != "submission"],
                       "modelCount": len(models)}}


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
