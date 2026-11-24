"""Conservative semantic proposals: objects first, then declared substructure children of semantic owners."""

from collections import defaultdict
from copy import deepcopy

from assignment_capacity import capacity_preserving_proposals
from decision_diagnostics import record
from structural_evidence import analyze_containment
from text_similarity import configured_tiers, legacy_thresholds, pair_similarity, with_glossary


def refine_semantic_proposals(indices, candidates, state, thresholds, *, text_evidence=None, glossary=None):
    """Assess candidate evidence and propose only mutually unambiguous pairs.

    `thresholds` is the single-tier `minimumSimilarity`; `text_evidence` replaces it with ordered tiers.
    """
    graph_matching = {"minimumSimilarity": thresholds}
    if text_evidence is not None:
        graph_matching["textEvidence"] = text_evidence
    tiers = configured_tiers(candidates, graph_matching)
    thresholds = legacy_thresholds(tiers)
    ranked = with_glossary(tiers, glossary)
    similarity = pair_similarity(candidates, ranked, glossary)
    events = []
    excluded = {(item["referenceId"], item["studentId"])
                for field in ("conflictingProposals", "blockedProposals") for item in state[field]}
    # Owners inferred from their children, or from text in an earlier round, scope the remaining children
    # just like exact-label owners.
    anchors = [item for item in state["proposals"]
               if (item["reason"] == "unique_exact_label" and not item["dependsOn"]
                   or item["reason"] in ("independent_child_evidence", "combined_child_structure",
                                         "supported_semantic_evidence"))
               and (item["referenceId"], item["studentId"]) not in excluded]
    containment = analyze_containment(deepcopy(indices), candidates, anchors)
    owners = {(item["referenceId"], item["studentId"]): item for item in containment}
    pairs = {
        pair: {"referenceId": pair[0], "studentId": pair[1], "status": item["status"],
               "scoreStatus": item["scoreStatus"], "supportingMethods": item["supportingMethods"],
               "ownerAnchorRelation": owners[pair]["ownerAnchorRelation"], "_scores": item["scores"],
               "_rank": item["tierRank"], **({"tier": item["tier"]} if text_evidence is not None else {})}
        for pair, item in similarity.items()
    }

    reserved = state["proposals"] + state["conflictingProposals"] + state["blockedProposals"]
    used_references = {item["referenceId"] for item in reserved}
    used_students = {item["studentId"] for item in reserved}
    available_pairs = {
        pair: item for pair, item in pairs.items()
        if pair[0] not in used_references and pair[1] not in used_students
        and item["status"] != "below_threshold"
    }
    for pair, item in pairs.items():
        if pair not in available_pairs:
            reserved_pair = pair[0] in used_references or pair[1] in used_students
            record(events, "semantic", "supported_semantic_evidence", *pair,
                   "deferred" if reserved_pair else "rejected",
                   ["one_to_one_reservation" if reserved_pair else "below_threshold"])
    by_reference, by_student = defaultdict(list), defaultdict(list)
    for pair, item in available_pairs.items():
        by_reference[pair[0]].append(item)
        by_student[pair[1]].append(item)

    def dominates(item, competitor):
        owner_rank = {"conflicting": 0, "unknown": 1, "consistent": 2}
        item_owner = owner_rank[item["ownerAnchorRelation"]]
        competitor_owner = owner_rank[competitor["ownerAnchorRelation"]]
        rank, competitor_rank = item["_rank"], competitor["_rank"]
        if rank is None or item_owner < competitor_owner:
            return False
        # A stronger tier wins outright; a weaker one never does.
        if competitor_rank is not None and competitor_rank != rank:
            return competitor_rank > rank
        methods = ranked[rank]["minimumSimilarity"]
        if not methods:  # glossary tier: no score to compare, two accepted pairs stay a tie unless the owner decides
            return competitor_rank is None or item_owner > competitor_owner
        if any(name not in item["_scores"] or name not in competitor["_scores"] for name in methods):
            return False
        return (all(item["_scores"][name] >= competitor["_scores"][name] for name in methods)
                and (item_owner > competitor_owner
                     or any(item["_scores"][name] > competitor["_scores"][name] for name in methods)))

    proposed = []
    for pair, item in available_pairs.items():
        if item["status"] != "supported" or item["ownerAnchorRelation"] == "conflicting":
            reasons = []
            if item["status"] != "supported":
                reasons.append("semantic_not_configured" if not tiers else "score_unavailable")
            if item["ownerAnchorRelation"] == "conflicting":
                reasons.append("owner_conflict")
            record(events, "semantic", "supported_semantic_evidence", *pair, "deferred", reasons)
            continue
        owner = owners[pair]
        if (item["ownerAnchorRelation"] == "unknown"
                and (owner["referenceSubstructure"] or owner["studentSubstructure"])):
            record(events, "semantic", "supported_semantic_evidence", *pair, "deferred", ["owner_unresolved"])
            continue
        competitors = [other for other in by_reference[pair[0]] + by_student[pair[1]] if other is not item]
        if not all(dominates(item, other) for other in competitors):
            record(events, "semantic", "supported_semantic_evidence", *pair, "deferred",
                   ["ambiguous_candidates"], competitors=[{"referenceId": other["referenceId"],
                    "studentId": other["studentId"]} for other in competitors])
            continue
        dependencies = []
        if owner["ownerAnchorRelation"] == "consistent":
            dependencies = [{"referenceId": owner["referenceOwnerId"], "studentId": owner["studentOwnerId"]}]
        proposed.append({"referenceId": pair[0], "studentId": pair[1],
                         "reason": "supported_semantic_evidence", "dependsOn": dependencies,
                         "status": "provisional"})
    proposed.sort(key=lambda item: (item["referenceId"], item["studentId"]))

    individually_feasible, proposals = capacity_preserving_proposals(state, proposed)
    for item in proposed:
        accepted = item in proposals
        record(events, "semantic_capacity", "supported_semantic_evidence", item["referenceId"],
               item["studentId"], "proposed" if accepted else "blocked",
               ["supported_semantic_evidence" if accepted else "capacity_conflict"],
               depends_on=item["dependsOn"], individuallyFeasible=item in individually_feasible,
               jointlyFeasible=accepted)
    proposals = proposals + _substructure_children(indices, candidates, state, anchors, proposals, pairs,
                                                   used_references, used_students, dominates, events)
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
        "configurationStatus": "configured" if tiers else "not_configured",
        "minimumSimilarity": thresholds,
        **({"textEvidence": {"tiers": tiers}} if text_evidence is not None else {}),
        "proposals": proposals,
        "unresolvedReferenceIds": unresolved,
        "noSupportedReferenceIds": no_supported,
        "candidateEvidence": [
            {key: value for key, value in pairs[pair].items() if not key.startswith("_")} for pair in sorted(pairs)
        ],
        "decisionEvents": sorted(events, key=lambda item: item["id"]),
    }


def _substructure_children(indices, candidates, state, anchors, owners, pairs, used_references, used_students,
                           dominates, events):
    """Second pass: children of semantically proposed owners compete only within that owner pair.

    Only declared substructure counts (identity owners); a candidate whose owners map elsewhere is
    outside the scope and no competitor. Same tiers and thresholds; the child depends on its owner.
    """
    if not owners:
        return []
    owner_pairs = {(item["referenceId"], item["studentId"]) for item in owners}
    containment = {(item["referenceId"], item["studentId"]): item
                   for item in analyze_containment(deepcopy(indices), candidates, anchors + owners)}
    taken_references = used_references | {item["referenceId"] for item in owners}
    taken_students = used_students | {item["studentId"] for item in owners}
    scope = {pair: {**item, "ownerAnchorRelation": containment[pair]["ownerAnchorRelation"]}
             for pair, item in pairs.items()
             if pair[0] not in taken_references and pair[1] not in taken_students and item["status"] != "below_threshold"}
    by_reference, by_student = defaultdict(list), defaultdict(list)
    for pair, item in scope.items():
        if item["ownerAnchorRelation"] != "conflicting":
            by_reference[pair[0]].append(item)
            by_student[pair[1]].append(item)
    proposed = []
    for pair, item in sorted(scope.items()):
        owner = containment[pair]
        owner_pair = (owner["referenceOwnerId"], owner["studentOwnerId"])
        if item["status"] != "supported" or item["ownerAnchorRelation"] != "consistent" or owner_pair not in owner_pairs:
            continue
        competitors = [other for other in by_reference[pair[0]] + by_student[pair[1]] if other is not item]
        if not all(dominates(item, other) for other in competitors):
            record(events, "semantic_child", "supported_semantic_evidence", *pair, "deferred", ["ambiguous_candidates"],
                   competitors=[{"referenceId": other["referenceId"], "studentId": other["studentId"]} for other in competitors])
            continue
        proposed.append({"referenceId": pair[0], "studentId": pair[1], "reason": "supported_semantic_evidence",
                         "dependsOn": [{"referenceId": owner_pair[0], "studentId": owner_pair[1]}], "status": "provisional"})
    _, accepted = capacity_preserving_proposals({**state, "proposals": state["proposals"] + owners}, proposed)
    for item in proposed:
        record(events, "semantic_child", "supported_semantic_evidence", item["referenceId"], item["studentId"],
               "proposed" if item in accepted else "blocked",
               ["semantic_owner_scope" if item in accepted else "capacity_conflict"], depends_on=item["dependsOn"])
    return accepted
