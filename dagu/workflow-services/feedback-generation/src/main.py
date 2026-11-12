#!/usr/bin/env python3
"""Aggregate one validated provisional comparison without performing matching."""
import hashlib
import json
import os
from pathlib import Path
import sys

import workflow_io
from workflow_io import Workspace, identifier, workspace, write_output

SERVICE = "feedback-generation"
CATEGORIES = ("nodes", "attributes", "connections", "other")
COUNT_FIELDS = ("referenceCount", "studentCount", "evaluableReferenceCount", "provisionalAnchorCount",
                "semanticProposalCount", "connectionProposalCount", "provisionalRecognizedCount")


def content_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_comparison(store: Workspace, reference_key: str) -> dict:
    reference_key = identifier(reference_key)
    if reference_key == "submission":
        raise ValueError("REFERENCE_KEY must select a reference model")
    bundle = store.snapshot()
    models = {}
    for role, key in (("student", "submission"), ("reference", reference_key)):
        selected = [model["source"] for model in bundle["models"] if model["source"]["key"] == key]
        expected = "submission" if role == "student" else "reference"
        if len(selected) != 1 or selected[0]["role"] != expected:
            raise ValueError("comparison pair does not match the frozen models")
        models[role] = selected[0]
    envelope = store.read(f"comparisons/{reference_key}.json")
    result = envelope.get("result")
    if (envelope.get("schema") != "workflow-result/v1" or envelope.get("schemaVersion") != 1
            or envelope.get("status") != "ok" or envelope.get("capability") != "one-to-one-graph-matching"
            or not isinstance(result, dict) or result.get("schema") != "reference-comparison/v1"
            or result.get("status") != "partial" or result.get("assessmentAvailable") is not False):
        raise ValueError("expected a successful provisional reference-comparison/v1 artifact")
    if (result.get("evaluationId") != bundle["evaluationId"] or result.get("inputHash") != bundle["inputHash"]
            or result.get("pair") != {"studentKey": "submission", "referenceKey": reference_key}
            or result.get("sources") != models):
        raise ValueError("comparison provenance does not match the frozen pair")
    if result.get("comparisonHash") != content_hash({key: value for key, value in result.items()
                                                      if key != "comparisonHash"}):
        raise ValueError("comparison hash mismatch")
    if (result["completeness"]["matching"] != "provisional"
            or result["completeness"]["structuralComparison"] != "provisional_owner_and_connections"):
        raise ValueError("unsupported comparison completeness")
    return result


def run(store: Workspace, reference_key: str) -> dict:
    comparison = read_comparison(store, reference_key)
    recognition = comparison["metrics"]["provisionalRecognition"]
    elements = comparison["mapping"]["provisionalElements"]
    connections = comparison["mapping"]["provisionalConnections"]
    rows = recognition["categoryTypes"]
    if not isinstance(rows, list) or not isinstance(elements, list) or not isinstance(connections, list):
        raise ValueError("invalid comparison recognition data")
    for mapping in (elements, connections):
        pairs = [(item["referenceId"], item["studentId"]) for item in mapping]
        if (len(set(pairs)) != len(pairs) or len({r for r, _ in pairs}) != len(pairs)
                or len({s for _, s in pairs}) != len(pairs)
                or any(item["status"] != "provisional" for item in mapping)):
            raise ValueError("comparison mapping must contain provisional one-to-one pairs")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or row.get("category") not in CATEGORIES
                or any(type(row.get(field)) is not int or row[field] < 0 for field in COUNT_FIELDS)
                or not row["provisionalRecognizedCount"] <= row["evaluableReferenceCount"] <= row["referenceCount"]
                or row["provisionalRecognizedCount"] != sum(row[field] for field in (
                    "provisionalAnchorCount", "semanticProposalCount", "connectionProposalCount"))):
            raise ValueError("invalid comparison category counts")
        key = (row["category"], json.dumps(row["language"], sort_keys=True), row["type"])
        if key in seen:
            raise ValueError("duplicate comparison category type")
        seen.add(key)
    totals = {field: sum(row[field] for row in rows) for field in COUNT_FIELDS}
    semantic_count = sum(item["reason"] == "supported_semantic_evidence" for item in elements)
    if (totals["provisionalRecognizedCount"] != len(elements) + len(connections)
            or totals["semanticProposalCount"] != semantic_count
            or totals["provisionalAnchorCount"] != len(elements) - semantic_count
            or totals["connectionProposalCount"] != len(connections)
            or recognition["overall"]["provisionalRecognizedCount"] != len(elements)
            or totals["referenceCount"] != recognition["overall"]["referenceCount"] + len(connections)
            + len(comparison["unresolvedReferenceConnectionIds"])
            or totals["studentCount"] != comparison["metrics"]["overall"]["studentCount"] + len(connections)
            + len(comparison["unresolvedStudentConnectionIds"])
            or recognition["allCategories"] != totals):
        raise ValueError("comparison recognition counts do not match mapping")
    semantics = comparison["semanticRefinement"]
    thresholds = semantics["minimumSimilarity"]
    if (not isinstance(thresholds, dict) or semantics["configurationStatus"] !=
            ("configured" if thresholds else "not_configured")):
        raise ValueError("invalid semantic configuration status")

    def evaluated(counts, category):
        denominator = counts["referenceCount"]
        evaluable = counts["evaluableReferenceCount"]
        return {**counts, "percentage": 100 * counts["provisionalRecognizedCount"] / denominator
                if denominator and evaluable else None,
                "evaluationStatus": ("not_applicable" if not denominator else
                                     "not_evaluated" if not evaluable else
                                     "partial" if evaluable < denominator or category == "other" or
                                     comparison["completeness"]["interpretation"] == "partial" else "provisional")}

    categories = []
    for category in CATEGORIES:
        items = [row for row in rows if row["category"] == category]
        counts = {field: sum(row[field] for row in items) for field in COUNT_FIELDS}
        categories.append({"category": category, **evaluated(counts, category),
                           "types": [evaluated(row, category) for row in items]})
    resource_paths = {"src/workflow_io.py": Path(workflow_io.__file__),
                      "src/main.py": Path(__file__)}
    producer = {"service": SERVICE, "version": "0.1.0",
                "resourceHash": content_hash({name: path.read_text(encoding="utf-8")
                                              for name, path in resource_paths.items()})}
    report = {
        "schema": "feedback-report/v1", "status": "partial", "assessmentAvailable": False,
        "evaluationId": comparison["evaluationId"], "inputHash": comparison["inputHash"],
        "pair": comparison["pair"], "comparisonHash": comparison["comparisonHash"], "producer": producer,
        "matching": "provisional", "recognitionTotals": totals, "categories": categories,
        "semanticConfiguration": {"status": semantics["configurationStatus"],
                                  "minimumSimilarity": thresholds},
        "unresolved": {
            "referenceElementIds": comparison["unresolvedReferenceIds"],
            "studentElementIds": comparison["unresolvedStudentIds"],
            "referenceConnectionIds": comparison["unresolvedReferenceConnectionIds"],
            "studentConnectionIds": comparison["unresolvedStudentConnectionIds"],
            "noSupportedSemanticReferenceIds": semantics["noSupportedReferenceIds"],
        },
        "completeness": comparison["completeness"],
    }
    report["feedbackHash"] = content_hash(report)
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "aggregate",
            "capability": SERVICE, "summary": "Vorläufige Erkennungsquoten; keine Gesamtbewertung", "result": report}


def main() -> int:
    try:
        store = workspace()
        write_output(run(store, os.environ.get("REFERENCE_KEY")))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
