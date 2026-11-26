#!/usr/bin/env python3
"""Validate and publish the complete frozen evaluation input exactly once."""
import base64
import gzip
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time
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


# Tier policy: canonical equality before spelling similarity before meaning; default values from
# the label-variant gold corpus (precision target), see docs/graph-matching-workflow/07-*.
TEXT_EVIDENCE_METHODS = ["damerau_canonical", "multilingual_expanded"]
TEXT_EVIDENCE_DEFAULTS = {"spelling": 0.85, "meaning": 0.85, "meaningFloor": 0.70}
# Hint policy (AP-05): band below a tier threshold, neighbours without text, children for an overlap,
# and the probe switch for reference text in hints (P9). Starting values, not calibrated.
HINT_DEFAULTS = {"textBand": 0.05, "minimumNeighbors": 2, "minimumChildren": 2, "showReferenceText": True}
SERVICE_VERSION = "1.4.0"
TEMPORARY_ID = re.compile(r"replay-[a-f0-9-]{36}-[0-9]+")


def cleanup_temporary(evaluation_id: str | None = None) -> None:
    """Delete only isolated replay workspaces; expire leftovers after seven days."""
    root = Path(os.environ.get("WORKFLOW_DATA_ROOT", "/work/evaluations")).resolve()
    if evaluation_id is not None and not TEMPORARY_ID.fullmatch(evaluation_id):
        raise ValueError("cleanup requires a temporary replay identifier")
    targets = [root / evaluation_id] if evaluation_id else list(root.glob("replay-*"))
    for target in targets:
        if not TEMPORARY_ID.fullmatch(target.name) or target.is_symlink():
            continue
        resolved = target.resolve()
        if resolved.parent != root:
            raise ValueError("temporary workspace leaves its configured root")
        if target.is_dir() and (evaluation_id is not None or time.time() - target.stat().st_mtime > 7 * 86400):
            shutil.rmtree(resolved)


def text_evidence_thresholds(raw: str | None) -> dict:
    """Defaults, optionally overridden by a JSON object with the keys of TEXT_EVIDENCE_DEFAULTS."""
    if raw is None or not raw.strip():
        return dict(TEXT_EVIDENCE_DEFAULTS)
    try:
        overrides = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("text_evidence must be a JSON object") from None
    if not isinstance(overrides, dict) or not set(overrides) <= TEXT_EVIDENCE_DEFAULTS.keys():
        raise ValueError(f"text_evidence accepts only {', '.join(TEXT_EVIDENCE_DEFAULTS)}")
    values = {**TEXT_EVIDENCE_DEFAULTS, **overrides}
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           or not 0 <= value <= 1 for value in values.values()):
        raise ValueError("text_evidence thresholds must be numbers between 0 and 1")
    if values["meaningFloor"] > values["meaning"]:
        raise ValueError("text_evidence meaningFloor must not exceed meaning")
    return values


def apply_text_evidence(config: dict, raw: str | None) -> dict:
    """Freeze the text-evidence tiers (with optional threshold overrides) into comparisonConfig before hashing."""
    values = text_evidence_thresholds(raw)
    tiers = [
        {"name": "canonical", "minimumSimilarity": {"damerau_canonical": 1.0}},
        {"name": "spelling", "minimumSimilarity": {"damerau_canonical": values["spelling"]}},
        {"name": "meaning", "minimumSimilarity": {"multilingual_expanded": values["meaning"]},
         "confirmationFloor": {"multilingual_expanded": values["meaningFloor"]}},
    ]
    graph_matching, semantics = config.get("graphMatching", {}), config.get("semantics", {})
    if not isinstance(graph_matching, dict) or not isinstance(semantics, dict):
        raise ValueError("comparisonConfig.graphMatching and semantics must be JSON objects")
    expected = ({"tiers": tiers}, TEXT_EVIDENCE_METHODS)
    present = (graph_matching.get("textEvidence"), semantics.get("methods"))
    if graph_matching.get("minimumSimilarity") or any(
            value not in (None, want) for value, want in zip(present, expected)):
        raise ValueError("text_evidence conflicts with the configured comparison methods")
    return {**config, "graphMatching": {**graph_matching, "textEvidence": expected[0]},
            "semantics": {**semantics, "methods": expected[1]}}


def apply_hints(config: dict) -> dict:
    """Freeze the hint parameters into comparisonConfig before hashing; a supplied policy must be complete."""
    graph_matching = config.get("graphMatching", {})
    hints = graph_matching.get("hints", HINT_DEFAULTS)
    if not isinstance(hints, dict) or set(hints) != set(HINT_DEFAULTS) or any(
            type(hints[key]) is not type(value) for key, value in HINT_DEFAULTS.items()):
        raise ValueError(f"graphMatching.hints requires exactly {', '.join(HINT_DEFAULTS)}")
    if not 0 <= hints["textBand"] < 1 or hints["minimumNeighbors"] < 1 or hints["minimumChildren"] < 1:
        raise ValueError("graphMatching.hints values are out of range")
    return {**config, "graphMatching": {**graph_matching, "hints": dict(hints)}}


def validate_glossaries(config: dict, reference_keys: set[str]) -> None:
    """Frozen administrator decisions per reference; part of the hashed input."""
    glossaries = config.get("graphMatching", {}).get("glossaries", {})
    if not isinstance(glossaries, dict) or not set(glossaries) <= reference_keys:
        raise ValueError("graphMatching.glossaries must be keyed by reference model")
    for glossary in glossaries.values():
        if (not isinstance(glossary, dict) or set(glossary) != {"revision", "termNormalization", "entries"}
                or type(glossary["revision"]) is not int or glossary["revision"] < 1
                or glossary["termNormalization"] != "nfc-casefold-space-v1"
                or not isinstance(glossary["entries"], list) or not glossary["entries"]):
            raise ValueError("invalid frozen glossary")
        pairs = set()
        for entry in glossary["entries"]:
            if (not isinstance(entry, dict) or not {"referenceElementId", "termKey", "status"} <= set(entry) <= {"referenceElementId", "termKey", "status", "matchingSource", "term"}
                    or not all(isinstance(entry[key], str) and entry[key] for key in ("referenceElementId", "termKey"))
                    or entry["status"] not in ("accepted", "rejected")):
                raise ValueError("invalid frozen glossary entry")
            if "matchingSource" in entry and type(entry["matchingSource"]) is not bool:
                raise ValueError("matchingSource must be a boolean")
            if entry.get("matchingSource"):
                if entry["status"] != "accepted" or not isinstance(entry.get("term"), str) or not entry["term"].strip() or len(entry["term"]) > 256:
                    raise ValueError("matching sources require accepted terms")
            pairs.add((entry["referenceElementId"], entry["termKey"]))
        if len(pairs) != len(glossary["entries"]):
            raise ValueError("duplicate frozen glossary entry")


def prepare(store: Workspace, bundle: EvaluationInput, text_evidence: str | None = None) -> dict:
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
    bundle["comparisonConfig"] = apply_hints(apply_text_evidence(bundle["comparisonConfig"], text_evidence))
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
    validate_glossaries(bundle["comparisonConfig"], set(keys) - {"submission"})
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
                       "modelCount": len(models), "comparisonConfig": bundle["comparisonConfig"]}}


def main() -> int:
    try:
        if os.environ.get("WORKFLOW_INPUT_PATH") == "cleanup-temporary":
            cleanup_temporary(identifier(os.environ.get("WORKFLOW_EVALUATION_ID")))
            write_output({"status": "ok", "capability": "temporary-workspace-cleanup", "version": SERVICE_VERSION})
            return 0
        cleanup_temporary()
        encoded = os.environ["EVALUATION_INPUT_GZIP_BASE64"]
        bundle = json.loads(gzip.decompress(base64.b64decode(encoded, validate=True)).decode("utf-8"))
        if not isinstance(bundle, dict):
            raise ValueError("evaluation input must be a JSON object")
        result = prepare(workspace(), bundle, os.environ.get("TEXT_EVIDENCE"))
        write_output(result)
        return 0
    except (ValueError, TypeError, KeyError, OSError, EOFError) as error:
        print(f"[workflow-data] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
