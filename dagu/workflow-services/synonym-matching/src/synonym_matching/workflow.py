"""Read one workflow pair and wrap its complete evidence for immutable publication."""

from copy import deepcopy
import os

from workflow_io import identifier, read_input
from .config import resolve_config
from .inventories import read_pair
from .provenance import SERVICE, content_hash, producer_metadata
from .service import compare_pair


def read_request(path=None, store=None):
    if store is None:
        if any(name in os.environ for name in ("REFERENCE_KEY", "WORKFLOW_INPUT_PATH", "WORKFLOW_OUTPUT_PATH")):
            raise ValueError("workspace variables require WORKFLOW_EVALUATION_ID")
        return read_input(path), None, None
    if path is not None or any(name in os.environ for name in ("WORKFLOW_INPUT_PATH", "TEMPLATE_INPUT")):
        raise ValueError("workspace mode reads both inventories directly; no input override is allowed")
    bundle = store.snapshot()
    reference_key = identifier(os.environ.get("REFERENCE_KEY"))
    references = [model for model in bundle["models"]
                  if model["source"]["key"] == reference_key and model["source"]["role"] == "reference"]
    if len(references) != 1:
        raise ValueError("REFERENCE_KEY must select exactly one reference from the snapshot")
    output_path = os.environ.get("WORKFLOW_OUTPUT_PATH")
    if output_path is None or store.path(output_path).name != f"{reference_key}.json":
        raise ValueError("WORKFLOW_OUTPUT_PATH must name <REFERENCE_KEY>.json")
    return {"studentInventory": store.read("labels/submission.json"),
            "referenceInventory": store.read(f"labels/{reference_key}.json"),
            "comparisonConfig": bundle["comparisonConfig"]}, bundle, reference_key


def run(payload, bundle=None, reference_key=None):
    inventories = read_pair(payload, bundle, reference_key)
    config = resolve_config(payload.get("comparisonConfig", {}))
    evidence = compare_pair(inventories, config)
    producer = producer_metadata()
    semantic_config = {"engine": config, "resources": evidence.pop("resources"),
                       "methods": deepcopy(evidence["methods"]), "combiner": deepcopy(evidence["combiner"]),
                       "threshold": None, "filtered": False, "producer": producer}
    diagnostics = []
    for element in evidence["unscoredElements"]:
        diagnostics.append({"code": "UNSCORABLE_LABEL_TEXT", "severity": "info", "scope": "element",
                            "message": "Element retained without semantic scores: " + element["reason"],
                            "modelKey": inventories[element["side"]]["source"]["key"], "elementIds": [element["id"]]})
    diagnostics.sort(key=lambda item: (item.get("code", ""), item.get("elementIds", []), content_hash(item)))
    student, reference = inventories["student"], inventories["reference"]
    result = {
        "schema": "semantic-candidates/v1", "evaluationId": student["evaluationId"], "inputHash": student["inputHash"],
        "pair": {"studentKey": student["source"]["key"], "referenceKey": reference["source"]["key"]},
        "graphHashes": {side: data["graphHash"] for side, data in inventories.items()},
        "inventoryHashes": {side: data["inventoryHash"] for side, data in inventories.items()},
        "inventoryPaths": {side: f"labels/{data['source']['key']}.json" for side, data in inventories.items()},
        "semanticConfig": semantic_config,
        "semanticConfigHash": content_hash(semantic_config), "producer": producer,
        "threshold": None, "filtered": False, **evidence,
        "completeness": {"technical": "complete", "interpretation": "partial" if any(
            data["completeness"]["interpretation"] == "partial" for data in inventories.values()) else "complete"},
        "diagnostics": diagnostics,
    }
    result["candidateHash"] = content_hash(result)
    return {"schema": "workflow-result/v1", "schemaVersion": 1, "status": "ok", "capability": SERVICE,
            "mode": "match", "summary": f"{evidence['evaluatedPairCount']} semantische Kandidatenpaare berechnet",
            "result": result}
