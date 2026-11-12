"""Conservative one-pass proposals from configured semantic evidence."""

from collections import defaultdict
from copy import deepcopy
import math

from assignment_capacity import analyze_proposal_feasibility
from structural_evidence import analyze_containment


def _thresholds(candidates, thresholds):
    if not isinstance(thresholds, dict):
        raise ValueError("graphMatching.minimumSimilarity must be an object")
    methods = {method["name"]: method["scoreRange"] for method in candidates["methods"]}
    for name, value in thresholds.items():
        if name not in methods:
            raise ValueError(f"minimum similarity references unknown method: {name}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"minimum similarity must be finite: {name}")
        lower, upper = methods[name]
        if not lower <= value <= upper:
            raise ValueError(f"minimum similarity outside score range: {name}")
    return dict(sorted(thresholds.items()))


def refine_semantic_proposals(indices, candidates, state, thresholds):
    """Assess candidate evidence and propose only mutually unambiguous pairs."""
    thresholds = _thresholds(candidates, thresholds)
    excluded = {(item["referenceId"], item["studentId"])
                for field in ("conflictingProposals", "blockedProposals") for item in state[field]}
    anchors = [item for item in state["proposals"]
               if item["reason"] == "unique_exact_label" and not item["dependsOn"]
               and (item["referenceId"], item["studentId"]) not in excluded]
    containment = analyze_containment(deepcopy(indices), candidates, anchors)
    owners = {(item["referenceId"], item["studentId"]): item for item in containment}
    ranges = {method["name"]: method["scoreRange"] for method in candidates["methods"]}
    pairs = {}
    for row in candidates["synonymMatrix"]:
        for match in row["matches"]:
            pair = (row["referenceElementId"], match["submissionElementId"])
            scores = match.get("scores") if match.get("scoreStatus") == "scored" else None
            available = {}
            for name in thresholds:
                score = scores.get(name) if isinstance(scores, dict) else None
                if score is None:
                    continue
                if (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
                        or not ranges[name][0] <= score <= ranges[name][1]):
                    raise ValueError(f"invalid candidate score: {name}")
                available[name] = score
            supported = sorted(name for name, score in available.items() if score >= thresholds[name])
            status = ("supported" if supported else
                      "below_threshold" if thresholds and len(available) == len(thresholds) else "unavailable")
            pairs[pair] = {
                "referenceId": pair[0], "studentId": pair[1], "status": status,
                "supportingMethods": supported, "ownerAnchorRelation": owners[pair]["ownerAnchorRelation"],
                "_scores": available,
            }

    reserved = state["proposals"] + state["conflictingProposals"] + state["blockedProposals"]
    used_references = {item["referenceId"] for item in reserved}
    used_students = {item["studentId"] for item in reserved}
    available_pairs = {
        pair: item for pair, item in pairs.items()
        if pair[0] not in used_references and pair[1] not in used_students
        and item["status"] != "below_threshold"
    }
    by_reference, by_student = defaultdict(list), defaultdict(list)
    for pair, item in available_pairs.items():
        by_reference[pair[0]].append(item)
        by_student[pair[1]].append(item)

    def dominates(item, competitor):
        if len(item["_scores"]) != len(thresholds) or len(competitor["_scores"]) != len(thresholds):
            return False
        owner_rank = {"conflicting": 0, "unknown": 1, "consistent": 2}
        item_owner = owner_rank[item["ownerAnchorRelation"]]
        competitor_owner = owner_rank[competitor["ownerAnchorRelation"]]
        return (all(item["_scores"][name] >= competitor["_scores"][name] for name in thresholds)
                and item_owner >= competitor_owner
                and (item_owner > competitor_owner
                     or any(item["_scores"][name] > competitor["_scores"][name] for name in thresholds)))

    proposed = []
    for pair, item in available_pairs.items():
        if item["status"] != "supported" or item["ownerAnchorRelation"] == "conflicting":
            continue
        owner = owners[pair]
        if (item["ownerAnchorRelation"] == "unknown"
                and (owner["referenceParentIds"] or owner["studentParentIds"])):
            continue
        competitors = [other for other in by_reference[pair[0]] + by_student[pair[1]] if other is not item]
        if not all(dominates(item, other) for other in competitors):
            continue
        dependencies = []
        if owner["ownerAnchorRelation"] == "consistent":
            dependencies = [{"referenceId": owner["referenceOwnerId"], "studentId": owner["studentOwnerId"]}]
        proposed.append({"referenceId": pair[0], "studentId": pair[1],
                         "reason": "supported_semantic_evidence", "dependsOn": dependencies,
                         "status": "provisional"})
    proposed.sort(key=lambda item: (item["referenceId"], item["studentId"]))

    def preserves_capacity(extra):
        check = {**state, "proposals": state["proposals"] + extra}
        return analyze_proposal_feasibility(check)["joint"]["status"] == "preserved"

    individually_feasible = [item for item in proposed if preserves_capacity([item])]
    proposals = individually_feasible if preserves_capacity(individually_feasible) else []
    proposed_references = {item["referenceId"] for item in proposals}
    reference_ids = {identity for identity, node in indices["reference"].nodes.items()
                     if node["kind"] == "modelElement"}
    evidence_by_reference = defaultdict(list)
    for (reference, _student), item in pairs.items():
        evidence_by_reference[reference].append(item)
    unresolved, no_supported = [], []
    active_references = {item["referenceId"] for item in state["proposals"]
                         if (item["referenceId"], item["studentId"]) not in excluded}
    for reference in sorted(reference_ids - active_references - proposed_references):
        evidence = evidence_by_reference[reference]
        if reference not in used_references and evidence and all(item["status"] == "below_threshold" for item in evidence):
            no_supported.append(reference)
        else:
            unresolved.append(reference)
    return {
        "configurationStatus": "configured" if thresholds else "not_configured",
        "minimumSimilarity": thresholds,
        "proposals": proposals,
        "unresolvedReferenceIds": unresolved,
        "noSupportedReferenceIds": no_supported,
        "candidateEvidence": [
            {key: value for key, value in pairs[pair].items() if key != "_scores"} for pair in sorted(pairs)
        ],
    }
