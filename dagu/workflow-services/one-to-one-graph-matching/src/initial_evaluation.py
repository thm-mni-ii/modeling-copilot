"""Report provisional anchor coverage and candidate capacity, not correctness."""

from collections import defaultdict
from copy import deepcopy

from assignment_capacity import (
    analyze_assignment_capacity,
    analyze_proposal_feasibility,
    maximum_assignment_for_references,
)


def _language(node):
    language = node["language"]
    return (language["languageId"], language["versionId"]) if language is not None else (None, None)


def _type_key(node):
    return (*_language(node), node["type"])


def _class_key(node):
    group = node["comparisonGroup"]
    return (*_language(node), "group" if group is not None else "type",
            group if group is not None else node["type"])


def _sort_key(key):
    return tuple((value is not None, value or "") for value in key)


def _language_value(key):
    return {"languageId": key[0], "versionId": key[1]} if key[0] is not None else None


def _metrics(reference_ids, student_ids, proposals, candidate_pairs, maximum=None):
    count = len(reference_ids)
    provisional = sum(item["referenceId"] in reference_ids for item in proposals)
    if maximum is None:
        maximum = maximum_assignment_for_references(candidate_pairs, reference_ids)
    return {
        "referenceCount": count,
        "studentCount": len(student_ids),
        "provisionalAnchorCount": provisional,
        "maximumAssignableCount": maximum,
        "anchorCoverage": provisional / count if count else None,
        "capacityUpperBound": maximum / count if count else None,
    }


def evaluate_initial_coverage(indices, state):
    """Evaluate validated candidates and provisional proposals for one pair."""
    nodes = {
        side: {identity: node for identity, node in index.nodes.items() if node["kind"] == "modelElement"}
        for side, index in indices.items()
    }
    capacity = analyze_assignment_capacity(state)
    feasibility = analyze_proposal_feasibility(state)
    candidate_pairs = state["candidatePairs"]
    for pair in candidate_pairs:
        for side, key in (("reference", "referenceId"), ("student", "studentId")):
            identity = pair[key]
            if identity not in nodes[side] or nodes[side][identity]["comparisonRole"] != "semantic":
                raise ValueError(f"{side} candidate must refer to a semantic model element")

    excluded = {
        (item["referenceId"], item["studentId"])
        for field in ("conflictingProposals", "blockedProposals") for item in state[field]
    }
    proposals = sorted(
        (item for item in state["proposals"] if (item["referenceId"], item["studentId"]) not in excluded),
        key=lambda item: (item["referenceId"], item["studentId"]),
    )
    used = {(item["referenceId"], item["studentId"]): item for item in proposals}
    for item in proposals:
        for dependency in item["dependsOn"]:
            pair = (dependency["referenceId"], dependency["studentId"])
            if (pair not in used or pair == (item["referenceId"], item["studentId"])
                    or used[pair]["reason"] != "unique_exact_label"):
                raise ValueError("proposal dependency must refer to a used original anchor")

    reference_ids, student_ids = set(nodes["reference"]), set(nodes["student"])
    metrics = {
        "overall": _metrics(reference_ids, student_ids, proposals, candidate_pairs, capacity["maximumMatches"]),
    }
    for field, key_fn in (("byReferenceType", _type_key), ("byComparisonClass", _class_key)):
        grouped = {side: defaultdict(set) for side in nodes}
        for side, elements in nodes.items():
            for identity, node in elements.items():
                grouped[side][key_fn(node)].add(identity)
        views = []
        for key in sorted(grouped["reference"], key=_sort_key):
            category = {"language": _language_value(key)}
            if field == "byReferenceType":
                category["type"] = key[2]
            else:
                category.update({"basis": key[2], "value": key[3]})
            views.append({
                "category": category,
                **_metrics(grouped["reference"][key], grouped["student"].get(key, set()),
                           proposals, candidate_pairs),
            })
        metrics[field] = views

    return {
        "mapping": {"provisionalElements": [{**deepcopy(item), "status": "provisional"} for item in proposals]},
        "unresolvedReferenceIds": sorted(reference_ids - {item["referenceId"] for item in proposals}),
        "unresolvedStudentIds": sorted(student_ids - {item["studentId"] for item in proposals}),
        "conflictingProposals": deepcopy(state["conflictingProposals"]),
        "blockedProposals": deepcopy(state["blockedProposals"]),
        "assignmentCapacity": capacity,
        "proposalFeasibility": feasibility,
        "metrics": metrics,
    }
