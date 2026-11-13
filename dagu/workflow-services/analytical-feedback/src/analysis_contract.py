"""Validate the compact analysis and its comparison identity."""

import hashlib
import json


SCHEMA = "analysis-feedback/v1"


def content_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analysis_key(report):
    return content_hash({key: value for key, value in report.items() if key not in ("analysisKey", "analysisHash")})


def analysis_path(report):
    return f"analysis/{report['pair']['referenceKey']}/{report['analysisKey']}.json"


def validate_analysis(report, store=None):
    require(isinstance(report, dict) and report.get("schema") == SCHEMA, "expected analysis-feedback/v1")
    require(report.get("status") == "provisional" and report.get("assessmentAvailable") is False,
            "analysis must remain provisional")
    require(report.get("analysisKey") == analysis_key(report), "analysis key mismatch")
    require(report.get("analysisHash") == content_hash({key: value for key, value in report.items()
                                                        if key != "analysisHash"}), "analysis hash mismatch")
    annotations = report.get("annotations")
    hints = report.get("referenceHints")
    require(isinstance(annotations, list) and isinstance(hints, list), "invalid analysis annotations or hints")
    seen = set()
    for item in annotations:
        target = item["target"]
        identity = target.get("id")
        require(target.get("side") == "submission" and isinstance(identity, str) and identity and identity not in seen,
                "analysis targets must have unique submission IDs")
        seen.add(identity)
        match = item["match"]
        require(match["status"] in ("provisional", "unresolved", "not_evaluated"), "invalid matching status")
        require((match["status"] == "provisional") == ("referenceId" in item),
                "provisional matching must identify its reference")
        require(isinstance(item["checks"], dict) and isinstance(item["hints"], list),
                "invalid annotation checks or hints")
    require(set(report["summary"]) == {"nodes", "attributes", "connections", "other"},
            "invalid recognition categories")
    if store is not None:
        reference_key = report["pair"]["referenceKey"]
        student = store.read("graphs/submission.json")["result"]["graph"]
        reference = store.read(f"graphs/{reference_key}.json")["result"]["graph"]
        student_nodes = {node["id"]: node for node in student["nodes"]}
        reference_nodes = {node["id"]: node for node in reference["nodes"]}
        require(seen == set(student_nodes), "annotations must cover submission graph objects once")
        comparison = store.read(f"comparisons/{reference_key}.json")["result"]
        pairs = {row["studentId"]: row["referenceId"] for field in ("provisionalElements", "provisionalConnections")
                 for row in comparison["mapping"][field]}
        for item in annotations:
            identity = item["target"]["id"]
            require(item["target"]["kind"] == student_nodes[identity]["kind"]
                    and item.get("referenceId") == pairs.get(identity), "annotation does not match graph or mapping")
        expected = set(comparison["unresolvedReferenceIds"]) | set(comparison["unresolvedReferenceConnectionIds"])
        require(len(hints) == len(expected) and {hint["referenceId"] for hint in hints} == expected,
                "unresolved reference hints do not match comparison")
        model_id = next(model["source"]["modelId"] for model in store.snapshot()["models"]
                        if model["source"]["key"] == "submission")
        for hint in hints:
            target, identity = hint["target"], hint["referenceId"]
            require(target["side"] == "submission" and identity in reference_nodes
                    and hint["kind"] == reference_nodes[identity]["kind"]
                    and (target["id"] in student_nodes and target["kind"] == student_nodes[target["id"]]["kind"]
                         or target["kind"] == "model" and target["id"] == model_id),
                    "invalid unresolved reference display target")
    return report


def read_analysis(store, path, reference_key, comparison):
    envelope = store.read(path)
    require(envelope.get("schema") == "workflow-result/v1" and envelope.get("schemaVersion") == 1
            and envelope.get("status") == "ok" and envelope.get("capability") == "analytical-feedback",
            "expected successful analytical feedback")
    report = envelope["result"]
    require(report["evaluationId"] == comparison["evaluationId"] and report["pair"] == comparison["pair"]
            and report["pair"]["referenceKey"] == reference_key
            and report["comparisonHash"] == comparison["comparisonHash"], "analysis comparison mismatch")
    require(path == analysis_path(report) and envelope.get("analysisPath") == path
            and envelope.get("analysisKey") == report["analysisKey"], "analysis path mismatch")
    return validate_analysis(report, store)
