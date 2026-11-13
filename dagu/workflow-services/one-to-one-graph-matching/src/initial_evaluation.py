"""Report provisional anchor coverage and candidate capacity, not correctness."""

from collections import defaultdict
from copy import deepcopy

from artifacts import _key
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
    dependencies = {}
    for item in proposals:
        item_pair = (item["referenceId"], item["studentId"])
        dependencies[item_pair] = set()
        for dependency in item["dependsOn"]:
            pair = (dependency["referenceId"], dependency["studentId"])
            if pair not in used or pair == item_pair:
                raise ValueError("proposal dependency must refer to a used active proposal")
            dependencies[item_pair].add(pair)
    ready = [pair for pair, required in dependencies.items() if not required]
    while ready:
        pair = ready.pop()
        for other, required in dependencies.items():
            if pair in required:
                required.remove(pair)
                if not required:
                    ready.append(other)
    if any(dependencies.values()):
        raise ValueError("proposal dependencies must not contain cycles")

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


def evaluate_type_comparison(indices, elements, connections):
    """Describe concrete types for existing provisional mappings only."""
    element_mapping = {item["referenceId"]: item for item in elements}
    result = {"evaluationStatus": "provisional"}
    for kind, field, mapping in (
        ("modelElement", "elements", elements), ("connection", "connections", connections),
    ):
        references = {identity: node for identity, node in indices["reference"].nodes.items()
                      if node["kind"] == kind}
        students = {identity: node for identity, node in indices["student"].nodes.items()
                    if node["kind"] == kind}
        pairs = [(item["referenceId"], item["studentId"]) for item in mapping]
        if (len({ref for ref, _ in pairs}) != len(pairs)
                or len({sub for _, sub in pairs}) != len(pairs)
                or any(ref not in references or sub not in students for ref, sub in pairs)
                or any(item["status"] != "provisional" for item in mapping)):
            raise ValueError("type comparison requires provisional one-to-one mappings")
        mapped = {item["referenceId"]: item for item in mapping}
        rows = []
        for ref, reference in sorted(references.items()):
            item = mapped.get(ref)
            student = students[item["studentId"]] if item else None
            status = "unresolved"
            group = reference["comparisonGroup"]
            if student is not None:
                ref_key, sub_key = _key(reference), _key(student)
                metadata_known = all(node["comparisonRole"] == "semantic"
                                     and node["languageResolution"] == "resolved"
                                     and _key(node) is not None
                                     for node in (reference, student))
                if metadata_known and ref_key != sub_key:
                    raise ValueError("incompatible provisional type mapping")
                if metadata_known and reference["type"] and student["type"]:
                    status = ("same_type" if reference["type"] == student["type"]
                              else "compatible_type_difference")
            dependencies = deepcopy(item.get("dependsOn", [])) if item else []
            if item and kind == "connection":
                endpoints = indices["reference"].endpoints.get(ref, {})
                if (set(endpoints) != {"source", "target"}
                        or any(identity not in element_mapping for identity in endpoints.values())):
                    raise ValueError("connection type mapping requires mapped endpoints")
                dependencies = [
                    {"referenceId": identity, "studentId": element_mapping[identity]["studentId"]}
                    for identity in sorted(set(endpoints.values()))
                ]
            rows.append({
                "referenceId": ref, "studentId": item["studentId"] if item else None,
                "referenceType": reference["type"], "studentType": student["type"] if student else None,
                "comparisonGroup": group,
                "studentComparisonGroup": student["comparisonGroup"] if student else None,
                "status": status, "mappingStatus": "provisional" if item else "unresolved",
                "mappingReason": item["reason"] if item else None, "dependsOn": dependencies,
            })
        same = sum(row["status"] == "same_type" for row in rows)
        different = sum(row["status"] == "compatible_type_difference" for row in rows)
        evaluated = same + different
        unresolved = [row["referenceId"] for row in rows if row["status"] == "unresolved"]
        result[field] = {
            "referenceCount": len(rows), "mappedCount": len(mapping), "evaluatedCount": evaluated,
            "sameTypeCount": same, "compatibleTypeDifferenceCount": different,
            "unresolvedCount": len(unresolved), "percentageDenominator": evaluated,
            "sameTypePercentage": 100 * same / evaluated if evaluated else None,
            "compatibleTypeDifferencePercentage": 100 * different / evaluated if evaluated else None,
            "unresolvedReferenceIds": unresolved, "pairs": rows,
        }
    return result
