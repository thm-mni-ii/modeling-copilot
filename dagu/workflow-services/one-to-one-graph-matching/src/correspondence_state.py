"""Build a provisional correspondence state without confirming matches."""

from collections import defaultdict, deque
from copy import deepcopy
import unicodedata

from artifacts import _key
from assignment_capacity import analyze_proposal_feasibility
from matching import propose_containment_anchors, propose_exact_anchors
from structural_evidence import _containment, analyze_child_owner_evidence, analyze_containment


def _candidate_graph(indices, candidates):
    candidate_pairs = [
        {
            "referenceId": row["referenceElementId"],
            "studentId": match["submissionElementId"],
            "referenceLabel": row["referenceLabel"],
            **{key: deepcopy(value) for key, value in match.items() if key != "submissionElementId"},
        }
        for row in candidates["synonymMatrix"] for match in row["matches"]
    ]
    candidate_pairs.sort(key=lambda item: (item["referenceId"], item["studentId"]))
    pairs = [(item["referenceId"], item["studentId"]) for item in candidate_pairs]
    adjacent = defaultdict(set)
    for reference_id, student_id in pairs:
        reference, student = ("reference", reference_id), ("student", student_id)
        adjacent[reference].add(student)
        adjacent[student].add(reference)

    components, visited = [], set()
    for start in sorted(adjacent):
        if start in visited:
            continue
        pending = deque([start])
        visited.add(start)
        references, students = set(), set()
        while pending:
            side, identity = pending.popleft()
            (references if side == "reference" else students).add(identity)
            for neighbor in adjacent[(side, identity)]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
        components.append({
            "referenceIds": sorted(references),
            "studentIds": sorted(students),
            "pairCount": sum(len(adjacent[("reference", identity)]) for identity in references),
        })
    components.sort(key=lambda item: (item["referenceIds"], item["studentIds"]))

    without_candidates = {}
    for side, index in indices.items():
        without_candidates[side] = sorted(
            identity for identity, node in index.nodes.items()
            if node["kind"] == "modelElement" and node["comparisonRole"] == "semantic"
            and (side, identity) not in adjacent
        )
    return {
        "candidatePairs": candidate_pairs,
        "candidateComponents": components,
        "noCandidateReferenceIds": without_candidates["reference"],
        "noCandidateStudentIds": without_candidates["student"],
    }


def build_provisional_state(indices, candidates):
    """Combine the existing one-pass proposals and all candidate graph edges."""
    anchors, unresolved = propose_exact_anchors(indices, candidates)
    # GraphIndex.owner can populate missing defaultdict entries during a read.
    evidence = analyze_containment(deepcopy(indices), candidates, anchors)
    containment_anchors = propose_containment_anchors(unresolved, anchors, evidence)
    evidence_by_pair = {(item["referenceId"], item["studentId"]): item for item in evidence}
    original_pairs = {(item["referenceId"], item["studentId"]) for item in anchors}
    proposals = [{**anchor, "dependsOn": []} for anchor in anchors]
    for anchor in containment_anchors:
        pair = (anchor["referenceId"], anchor["studentId"])
        item = evidence_by_pair.get(pair)
        if item is None:
            raise ValueError("containment proposal lacks its evidence")
        dependency = (item["referenceOwnerId"], item["studentOwnerId"])
        if item["ownerAnchorRelation"] != "consistent" or dependency not in original_pairs:
            raise ValueError("containment proposal lacks its original owner anchor")
        proposals.append({
            **anchor,
            "dependsOn": [{"referenceId": dependency[0], "studentId": dependency[1]}],
        })
    proposals.sort(key=lambda item: (item["referenceId"], item["studentId"], item["reason"]))
    proposal_pairs = [(item["referenceId"], item["studentId"]) for item in proposals]
    if len(set(proposal_pairs)) != len(proposal_pairs):
        raise ValueError("duplicate provisional proposal")

    by_reference, by_student = defaultdict(set), defaultdict(set)
    for proposal in proposals:
        by_reference[proposal["referenceId"]].add(proposal["studentId"])
        by_student[proposal["studentId"]].add(proposal["referenceId"])
    conflicts = [
        proposal for proposal in proposals
        if len(by_reference[proposal["referenceId"]]) > 1 or len(by_student[proposal["studentId"]]) > 1
    ]
    conflict_pairs = {(item["referenceId"], item["studentId"]) for item in conflicts}
    available_original = original_pairs - conflict_pairs
    blocked = [
        proposal for proposal in proposals
        if (proposal["referenceId"], proposal["studentId"]) not in conflict_pairs
        and any((dependency["referenceId"], dependency["studentId"]) not in available_original
                for dependency in proposal["dependsOn"])
    ]
    blocked_pairs = {(item["referenceId"], item["studentId"]) for item in blocked}
    excluded_pairs = conflict_pairs | blocked_pairs
    state = {
        "proposals": [proposal for proposal in proposals
                      if (proposal["referenceId"], proposal["studentId"]) not in excluded_pairs],
        "conflictingProposals": conflicts,
        "blockedProposals": blocked,
        **_candidate_graph(indices, candidates),
    }
    indices = deepcopy(indices)

    def available_ids():
        reserved = state["proposals"] + state["conflictingProposals"] + state["blockedProposals"]
        return ({item["referenceId"] for item in reserved}, {item["studentId"] for item in reserved})

    def accept(extra):
        if not extra:
            return
        feasible = [item for item in extra if analyze_proposal_feasibility({
            **state, "proposals": state["proposals"] + [item],
        })["joint"]["status"] == "preserved"]
        if feasible and analyze_proposal_feasibility({
            **state, "proposals": state["proposals"] + feasible,
        })["joint"]["status"] == "preserved":
            state["proposals"].extend(feasible)

    # Reuse the exact matcher after active one-to-one reservations. Preserve
    # every reservation that removed an exact-label alternative as evidence.
    used_ref, used_sub = available_ids()
    active_ref = {item["referenceId"]: item for item in state["proposals"]}
    active_sub = {item["studentId"]: item for item in state["proposals"]}
    rows = [{"referenceElementId": row["referenceElementId"], "referenceLabel": row["referenceLabel"],
             "matches": [match for match in row["matches"] if match["submissionElementId"] not in active_sub]}
            for row in candidates["synonymMatrix"] if row["referenceElementId"] not in active_ref]
    remaining = propose_exact_anchors(indices, {"synonymMatrix": rows})[0] if unresolved else []
    labels = {row["referenceElementId"]: " ".join(unicodedata.normalize("NFC", row["referenceLabel"]).split())
              for row in candidates["synonymMatrix"]}
    candidate_pairs = {(item["referenceId"], item["studentId"]) for item in state["candidatePairs"]}
    residual = []
    for item in remaining:
        ref, sub = item["referenceId"], item["studentId"]
        ref_info, sub_info = _containment(indices["reference"], ref), _containment(indices["student"], sub)
        owner_ref, owner_sub = ref_info[1], sub_info[1]
        if (ref in used_ref or sub in used_sub or not ref_info[3] or not sub_info[3]
                or owner_ref is None or owner_sub is None
                or owner_ref in used_ref or owner_sub in used_sub or (owner_ref, owner_sub) not in candidate_pairs
                or _key(indices["reference"].nodes[owner_ref]) is None
                or _key(indices["reference"].nodes[owner_ref]) != _key(indices["student"].nodes[owner_sub])):
            continue
        blockers = {}
        for pair in unresolved:
            if labels[pair["referenceId"]] != labels[ref]:
                continue
            for reserved in (active_ref.get(pair["referenceId"]), active_sub.get(pair["studentId"])):
                if reserved:
                    blockers[(reserved["referenceId"], reserved["studentId"])] = reserved
        if not blockers:
            continue
        residual.append({"referenceId": ref, "studentId": sub, "reason": "unique_exact_after_reservations",
                         "dependsOn": [{"referenceId": r, "studentId": s} for r, s in sorted(blockers)]})
    accept(residual)

    child_evidence = analyze_child_owner_evidence(indices, candidates, state["proposals"])
    used_ref, used_sub = available_ids()
    supported = [item for item in child_evidence
                 if item["supportingChildren"] and not item["conflictingChildren"]
                 and item["referenceId"] not in used_ref and item["studentId"] not in used_sub]
    refs, subs = defaultdict(set), defaultdict(set)
    for item in supported:
        refs[item["referenceId"]].add(item["studentId"])
        subs[item["studentId"]].add(item["referenceId"])
    owner_proposals = [
        {"referenceId": item["referenceId"], "studentId": item["studentId"],
         "reason": "independent_child_evidence",
         "dependsOn": [{"referenceId": child["referenceId"], "studentId": child["studentId"]}
                       for child in item["supportingChildren"]]}
        for item in supported if len(refs[item["referenceId"]]) == 1 and len(subs[item["studentId"]]) == 1
    ]
    accept(owner_proposals)
    proposed_pairs = {(item["referenceId"], item["studentId"]) for item in state["proposals"]
                      if item["reason"] == "independent_child_evidence"}
    for item in child_evidence:
        ref, sub = item["referenceId"], item["studentId"]
        if (ref, sub) in proposed_pairs:
            item["proposalStatus"] = "proposed"
        elif ref in used_ref or sub in used_sub:
            item["proposalStatus"] = "reserved"
        elif item["conflictingChildren"]:
            item["proposalStatus"] = "conflicting"
        elif not item["supportingChildren"]:
            item["proposalStatus"] = "no_independent_support"
        elif len(refs[ref]) != 1 or len(subs[sub]) != 1:
            item["proposalStatus"] = "competing"
        else:
            item["proposalStatus"] = "capacity_not_preserved"

    new_owners = [item for item in state["proposals"] if item["reason"] == "independent_child_evidence"]
    if new_owners:
        owner_anchors = [item for item in state["proposals"] if item["reason"] == "unique_exact_label"] + new_owners
        owner_evidence = analyze_containment(indices, candidates, owner_anchors)
        owner_evidence_by_pair = {(item["referenceId"], item["studentId"]): item for item in owner_evidence}
        used_ref, used_sub = available_ids()
        remaining_unresolved = [item for item in unresolved
                                if item["referenceId"] not in used_ref and item["studentId"] not in used_sub]
        children = propose_containment_anchors(remaining_unresolved, owner_anchors, owner_evidence)
        new_owner_pairs = {(item["referenceId"], item["studentId"]) for item in new_owners}
        extra = []
        for child in children:
            item = owner_evidence_by_pair[child["referenceId"], child["studentId"]]
            dependency = (item["referenceOwnerId"], item["studentOwnerId"])
            if dependency in new_owner_pairs:
                extra.append({**child, "dependsOn": [{"referenceId": dependency[0], "studentId": dependency[1]}]})
        accept(extra)
    state["proposals"].sort(key=lambda item: (item["referenceId"], item["studentId"], item["reason"]))
    state["childOwnerEvidence"] = child_evidence
    return state
