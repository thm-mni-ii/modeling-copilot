"""Evaluate containment only for provisional element correspondences."""

from collections import Counter
from copy import deepcopy

from structural_evidence import analyze_containment


def evaluate_provisional_owners(indices, candidates, provisional_mapping):
    """Return provisional owner evidence and an agreement interval."""
    pairs = {(item["referenceId"], item["studentId"]) for item in provisional_mapping}
    if len(pairs) != len(provisional_mapping):
        raise ValueError("provisional mapping contains duplicate pairs")

    rows = []
    for row in candidates["synonymMatrix"]:
        matches = [match for match in row["matches"]
                   if (row["referenceElementId"], match["submissionElementId"]) in pairs]
        if matches:
            rows.append({"referenceElementId": row["referenceElementId"], "matches": matches})
    anchors = [item for item in provisional_mapping
               if item["reason"] == "unique_exact_label" and not item["dependsOn"]]
    evidence = analyze_containment(deepcopy(indices), {"synonymMatrix": rows}, anchors)
    if (len(evidence) != len(pairs)
            or {(item["referenceId"], item["studentId"]) for item in evidence} != pairs):
        raise ValueError("provisional mapping must contain unique candidate pairs")

    for item in evidence:
        reference_has_parent = bool(item["referenceParentIds"])
        student_has_parent = bool(item["studentParentIds"])
        if not reference_has_parent and not student_has_parent:
            status = "not_applicable"
        elif reference_has_parent != student_has_parent:
            status = "violated"
        else:
            status = {"consistent": "satisfied", "conflicting": "violated",
                      "unknown": "unresolved"}[item["ownerAnchorRelation"]]
        item["status"] = status

    counts = Counter(item["status"] for item in evidence)
    satisfied, violated, unresolved = (counts[status] for status in ("satisfied", "violated", "unresolved"))
    expected = satisfied + violated + unresolved
    return {
        "pairs": evidence,
        "metrics": {
            "expected": expected,
            "satisfied": satisfied,
            "violated": violated,
            "unresolved": unresolved,
            "agreement": {
                "lower": satisfied / expected if expected else None,
                "upper": (satisfied + unresolved) / expected if expected else None,
            },
        },
    }
