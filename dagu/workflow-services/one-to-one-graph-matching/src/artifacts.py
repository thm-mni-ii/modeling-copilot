"""Validate graph and candidate artifacts against the frozen evaluation."""

import hashlib
import json
import math

from graph_index import GraphIndex
from workflow_io import identifier

GRAPH_HASH_FIELDS = ("source", "languageResources", "producer", "graph", "completeness", "diagnostics")


def content_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _result(envelope, capability, schema):
    if (not isinstance(envelope, dict) or envelope.get("schema") != "workflow-result/v1"
            or type(envelope.get("schemaVersion")) is not int or envelope["schemaVersion"] != 1
            or envelope.get("status") != "ok" or envelope.get("capability") != capability
            or not isinstance(envelope.get("result"), dict)
            or envelope["result"].get("schema") != schema):
        raise ValueError(f"expected successful {capability} {schema} artifact")
    return envelope["result"]


def _key(node):
    language = node["language"]
    if not language:
        return None
    group = node["comparisonGroup"]
    if group is not None:
        comparison = ("group", group) if group else None
    else:
        node_type = node["type"]
        comparison = ("type", node_type) if node_type else None
    if comparison is None:
        return None
    return language["languageId"], language["versionId"], *comparison


def read_artifacts(store, reference_key):
    reference_key = identifier(reference_key)
    if reference_key == "submission":
        raise ValueError("REFERENCE_KEY must select a reference model")
    bundle = store.snapshot()
    models = {}
    for role, key in (("student", "submission"), ("reference", reference_key)):
        selected = [model for model in bundle["models"] if model["source"]["key"] == key]
        expected_role = "submission" if role == "student" else "reference"
        if len(selected) != 1 or selected[0]["source"]["role"] != expected_role:
            raise ValueError(f"{key} must select exactly one {expected_role} model")
        models[role] = selected[0]

    graphs, indices = {}, {}
    language_data = {(item["languageId"], item["versionId"]): item["data"] for item in bundle["languages"]}
    for side, model in models.items():
        key = model["source"]["key"]
        data = _result(store.read(f"graphs/{key}.json"), "graph-parser", "graph-result/v1")
        if (data["evaluationId"] != bundle["evaluationId"] or data["inputHash"] != bundle["inputHash"]
                or data["source"] != model["source"]):
            raise ValueError(f"{side} graph does not belong to the frozen model")
        if data["graphHash"] != content_hash({field: data[field] for field in GRAPH_HASH_FIELDS}):
            raise ValueError(f"{side} graph hash mismatch")
        resource_keys = set()
        for resource in data["languageResources"]:
            language = (resource["languageId"], resource["versionId"])
            if (language in resource_keys or language not in language_data
                    or resource["hash"] != content_hash(language_data[language])):
                raise ValueError(f"{side} graph language resource mismatch")
            resource_keys.add(language)
        declared_languages = [(item["languageId"], item["versionId"]) for item in data["graph"]["languages"]]
        if len(set(declared_languages)) != len(declared_languages) or set(declared_languages) != resource_keys:
            raise ValueError(f"{side} graph language references do not match its resources")
        if data["completeness"].get("interpretation") not in ("complete", "partial"):
            raise ValueError("graph interpretation completeness is required")
        graphs[side] = data
        indices[side] = GraphIndex(data["graph"])

    data = _result(store.read(f"candidates/{reference_key}.json"), "synonym-matching", "semantic-candidates/v1")
    if data["candidateHash"] != content_hash({key: value for key, value in data.items() if key != "candidateHash"}):
        raise ValueError("candidate hash mismatch")
    if (data["evaluationId"] != bundle["evaluationId"] or data["inputHash"] != bundle["inputHash"]
            or data["pair"] != {"studentKey": "submission", "referenceKey": reference_key}
            or data["graphHashes"] != {side: graph["graphHash"] for side, graph in graphs.items()}):
        raise ValueError("candidate provenance does not match the frozen model pair")
    if data["semanticConfigHash"] != content_hash(data["semanticConfig"]):
        raise ValueError("semantic configuration hash mismatch")
    semantics = bundle["comparisonConfig"].get("semantics", {})
    config = data["semanticConfig"]
    if "methods" in semantics and config["methods"] != semantics["methods"]:
        raise ValueError("candidate methods differ from the frozen configuration")
    if "preprocessing" in semantics and any(
        config["preprocessing"].get(name) != semantics["preprocessing"] for name in config["methods"]
    ):
        raise ValueError("candidate preprocessing differs from the frozen configuration")
    inventories = {}
    for side, model in models.items():
        key = model["source"]["key"]
        path = f"labels/{key}.json"
        if data["inventoryPaths"][side] != path:
            raise ValueError(f"{side} candidate inventory path mismatch")
        inventory = _result(store.read(path), "model-label-extraction", "element-inventory/v1")
        if (inventory["evaluationId"] != bundle["evaluationId"]
                or inventory["inputHash"] != bundle["inputHash"]
                or inventory["source"] != model["source"]
                or inventory["graphHash"] != graphs[side]["graphHash"]
                or inventory["graphPath"] != f"graphs/{key}.json"):
            raise ValueError(f"{side} inventory provenance mismatch")
        expected_hash = content_hash({field: value for field, value in inventory.items() if field != "inventoryHash"})
        if inventory["inventoryHash"] != expected_hash or data["inventoryHashes"][side] != expected_hash:
            raise ValueError(f"{side} inventory hash mismatch")
        inventories[side] = inventory
    _validate_candidates(data, indices, inventories)
    return bundle, graphs, indices, data


def _validate_candidates(data, indices, inventories):
    required = ("inventoryHashes", "inventoryPaths", "producer", "processedTexts", "connectionTextMatrix",
                "unscoredElements", "completeness", "diagnostics")
    if any(field not in data for field in required):
        raise ValueError("candidate artifact is missing required fields")
    if (not isinstance(data["connectionTextMatrix"], list)
            or not isinstance(data["synonymMatrix"], list)
            or not isinstance(data["processedTexts"], dict)
            or not isinstance(data["diagnostics"], list)
            or not isinstance(data["unscoredElements"], list)
            or not isinstance(data["producer"], dict)
            or not isinstance(data["completeness"], dict)
            or data["completeness"].get("technical") != "complete"
            or data["completeness"].get("interpretation") not in ("complete", "partial")):
        raise ValueError("invalid candidate artifact fields")
    elements = {
        side: {identity: node for identity, node in index.nodes.items()
               if node["kind"] == "modelElement" and node["comparisonRole"] == "semantic"}
        for side, index in indices.items()
    }
    inventory_elements = {}
    inventory_connections = {}
    for side, inventory in inventories.items():
        inventory_elements[side] = {item["id"]: item for item in inventory["elements"]}
        inventory_connections[side] = {item["id"]: item for item in inventory["connectionTexts"]}
        if (len(inventory_elements[side]) != len(inventory["elements"])
                or len(inventory_connections[side]) != len(inventory["connectionTexts"])
                or set(inventory_elements[side]) != set(elements[side])
                or set(inventory_elements[side]) & set(inventory_connections[side])):
            raise ValueError(f"{side} inventory IDs do not match graph elements")
        for identity, item in inventory_elements[side].items():
            node = elements[side][identity]
            if any(item[field] != node[field] for field in ("type", "comparisonGroup", "language")):
                raise ValueError(f"{side} inventory element does not match graph metadata")
            if not isinstance(item["matchText"], str):
                raise ValueError("inventory matchText must be a string")
    methods = data["methods"]
    ranges = {}
    for method in methods:
        name, bounds = method["name"], method["scoreRange"]
        if (not isinstance(name, str) or not name or name in ranges or not isinstance(bounds, list)
                or len(bounds) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                           or not math.isfinite(v) for v in bounds)
                or bounds[0] > bounds[1]):
            raise ValueError("invalid candidate method metadata")
        ranges[name] = bounds
    if not ranges or list(ranges) != data["semanticConfig"]["methods"]:
        raise ValueError("candidate methods do not match semantic configuration")
    expected = {
        (ref_id, student_id): _key(reference)[2]
        for ref_id, reference in elements["reference"].items() if _key(reference) is not None
        for student_id, student in elements["student"].items() if _key(reference) == _key(student)
    }
    seen_rows, seen_pairs, scored = set(), set(), 0
    for row in data["synonymMatrix"]:
        ref_id = row["referenceElementId"]
        if (ref_id not in elements["reference"] or ref_id in seen_rows
                or row["referenceLabel"] != inventory_elements["reference"][ref_id]["matchText"]):
            raise ValueError("invalid or duplicate candidate matrix row")
        seen_rows.add(ref_id)
        for candidate in row["matches"]:
            pair = (ref_id, candidate["submissionElementId"])
            if pair in seen_pairs or pair not in expected or candidate["comparisonBasis"] != expected[pair]:
                raise ValueError("invalid, duplicate or ineligible candidate pair")
            if candidate["submissionLabel"] != inventory_elements["student"][pair[1]]["matchText"]:
                raise ValueError("candidate submissionLabel does not match inventory")
            seen_pairs.add(pair)
            status, scores = candidate["scoreStatus"], candidate["scores"]
            if status == "unavailable":
                if scores is not None or candidate.get("unavailableReason") not in ("missing_text", "unsupported_text"):
                    raise ValueError("invalid unavailable candidate")
            elif status == "scored":
                if not isinstance(scores, dict) or set(scores) != set(ranges):
                    raise ValueError("candidate scores do not match methods")
                for name, value in scores.items():
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or not math.isfinite(value) or not ranges[name][0] <= value <= ranges[name][1]):
                        raise ValueError("candidate score outside method range")
                scored += 1
            else:
                raise ValueError("invalid candidate score status")
    if seen_rows != set(elements["reference"]) or seen_pairs != set(expected):
        raise ValueError("candidate matrix is incomplete")
    if (data["candidatePairCount"] != len(expected) or data["scoredPairCount"] != scored
            or data["unavailablePairCount"] != len(expected) - scored):
        raise ValueError("candidate counts do not match the complete matrix")
    seen_connections = set()
    for pair in data["connectionTextMatrix"]:
        identities = (pair["referenceConnectionTextId"], pair["submissionConnectionTextId"])
        if identities in seen_connections:
            raise ValueError("duplicate connection text pair")
        seen_connections.add(identities)
        for side, identity, label in (
            ("reference", identities[0], pair["referenceLabel"]),
            ("student", identities[1], pair["submissionLabel"]),
        ):
            node = indices[side].nodes.get(identity)
            text = inventory_connections[side].get(identity)
            if (node is None or node["kind"] not in ("connection", "connectionLabel")
                    or text is None or label != text["matchText"]):
                raise ValueError("invalid connection text reference")
            owner = pair["referenceOwnerConnectionId" if side == "reference" else "submissionOwnerConnectionId"]
            if owner is not None and (owner not in indices[side].nodes
                                      or indices[side].nodes[owner]["kind"] != "connection"):
                raise ValueError("invalid connection text owner")
            if (owner != text["ownerConnectionId"] or pair["kind"] != text["kind"]
                    or pair["connectionLabelId"] != text["connectionLabelId"]):
                raise ValueError("connection text metadata does not match inventory")
        scores = pair["scores"]
        if (pair["kind"] not in ("self", "additionalLabel") or not isinstance(scores, dict)
                or set(scores) != set(ranges)):
            raise ValueError("invalid connection text scores")
        for name, value in scores.items():
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not ranges[name][0] <= value <= ranges[name][1]):
                raise ValueError("connection text score outside method range")
