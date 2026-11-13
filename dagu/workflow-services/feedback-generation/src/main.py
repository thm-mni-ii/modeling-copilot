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

    has_containment = ("provisionalContainment" in comparison["metrics"]
                       or "provisionalContainmentEvidence" in comparison)
    containment_metrics = comparison["metrics"].get("provisionalContainment")
    containment_relations = comparison.get("provisionalContainmentEvidence")
    if has_containment:
        if not isinstance(containment_metrics, dict) or not isinstance(containment_relations, list):
            raise ValueError("invalid provisional containment data")
        statuses = ("satisfied", "violated", "unresolved")
        counts = {status: sum(isinstance(row, dict) and row.get("status") == status
                              for row in containment_relations) for status in statuses}
        total = len(containment_relations)
        expected_agreement = {
            "lower": counts["satisfied"] / total if total else None,
            "upper": (counts["satisfied"] + counts["unresolved"]) / total if total else None,
        }
        if (sum(counts.values()) != total or type(containment_metrics.get("referenceRelationCount")) is not int
                or containment_metrics["referenceRelationCount"] != total
                or any(type(containment_metrics.get(status)) is not int
                       or containment_metrics[status] != counts[status] for status in statuses)
                or containment_metrics.get("agreement") != expected_agreement):
            raise ValueError("provisional containment counts do not match relations")

    type_comparison = comparison.get("provisionalTypeComparison")
    if "provisionalTypeComparison" in comparison:
        if not isinstance(type_comparison, dict) or type_comparison.get("evaluationStatus") != "provisional":
            raise ValueError("invalid provisional type comparison")
        element_pairs = {(item["referenceId"], item["studentId"]) for item in elements}
        for field, mapping, reference_count, unmatched in (
            ("elements", elements, recognition["overall"]["referenceCount"], comparison["unresolvedReferenceIds"]),
            ("connections", connections, len(connections) + len(comparison["unresolvedReferenceConnectionIds"]),
             comparison["unresolvedReferenceConnectionIds"]),
        ):
            data = type_comparison.get(field)
            if not isinstance(data, dict) or not isinstance(data.get("pairs"), list):
                raise ValueError("invalid provisional type comparison data")
            type_rows = data["pairs"]
            proposals = {item["referenceId"]: item for item in mapping}
            seen_refs, unresolved = set(), []
            counts = {"same_type": 0, "compatible_type_difference": 0, "unresolved": 0}
            for row in type_rows:
                if not isinstance(row, dict) or row.get("status") not in counts:
                    raise ValueError("invalid provisional type comparison row")
                ref, sub = row.get("referenceId"), row.get("studentId")
                if not isinstance(ref, str) or not ref or ref in seen_refs:
                    raise ValueError("invalid provisional type comparison reference")
                seen_refs.add(ref)
                proposal = proposals.get(ref)
                dependencies = row.get("dependsOn")
                if not isinstance(dependencies, list) or any(
                    not isinstance(dep, dict) or set(dep) != {"referenceId", "studentId"}
                    or not isinstance(dep["referenceId"], str) or not isinstance(dep["studentId"], str)
                    or (dep["referenceId"], dep["studentId"]) not in element_pairs for dep in dependencies
                ):
                    raise ValueError("invalid provisional type comparison dependencies")
                if proposal:
                    if (sub != proposal["studentId"] or row.get("mappingStatus") != "provisional"
                            or row.get("mappingReason") != proposal["reason"]
                            or (field == "elements" and dependencies != proposal.get("dependsOn", []))):
                        raise ValueError("provisional type comparison does not match mapping")
                elif (sub is not None or row.get("mappingStatus") != "unresolved"
                      or row.get("mappingReason") is not None or dependencies
                      or row.get("studentType") is not None or row.get("studentComparisonGroup") is not None):
                    raise ValueError("provisional type comparison invents a mapping")
                status = row["status"]
                if status != "unresolved":
                    ref_type, sub_type = row.get("referenceType"), row.get("studentType")
                    group, sub_group = row.get("comparisonGroup"), row.get("studentComparisonGroup")
                    if (not proposal or not isinstance(ref_type, str) or not ref_type
                            or not isinstance(sub_type, str) or not sub_type or group != sub_group
                            or (group is not None and (not isinstance(group, str) or not group))
                            or (status == "same_type" and ref_type != sub_type)
                            or (status == "compatible_type_difference"
                                and (ref_type == sub_type or not isinstance(group, str) or not group))):
                        raise ValueError("invalid provisional concrete type status")
                else:
                    unresolved.append(ref)
                counts[status] += 1
            evaluated = counts["same_type"] + counts["compatible_type_difference"]
            expected = {
                "referenceCount": reference_count, "mappedCount": len(mapping), "evaluatedCount": evaluated,
                "sameTypeCount": counts["same_type"],
                "compatibleTypeDifferenceCount": counts["compatible_type_difference"],
                "unresolvedCount": counts["unresolved"], "percentageDenominator": evaluated,
                "sameTypePercentage": 100 * counts["same_type"] / evaluated if evaluated else None,
                "compatibleTypeDifferencePercentage":
                    100 * counts["compatible_type_difference"] / evaluated if evaluated else None,
                "unresolvedReferenceIds": sorted(unresolved),
            }
            if (len(type_rows) != reference_count or not set(proposals).issubset(seen_refs)
                    or seen_refs - set(proposals) != set(unmatched)
                    or any(type(data.get(key)) is not int for key in (
                        "referenceCount", "mappedCount", "evaluatedCount", "sameTypeCount",
                        "compatibleTypeDifferenceCount", "unresolvedCount", "percentageDenominator"))
                    or any(data.get(key) != value for key, value in expected.items())):
                raise ValueError("provisional type comparison counts do not match mapping")

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
    if "provisionalConnectionStructure" in comparison:
        report["provisionalConnectionStructure"] = comparison["provisionalConnectionStructure"]
    if has_containment:
        report["provisionalContainment"] = {"metrics": containment_metrics, "relations": containment_relations}
    if type_comparison is not None:
        report["provisionalTypeComparison"] = type_comparison
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
