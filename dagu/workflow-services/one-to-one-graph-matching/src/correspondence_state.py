"""Build a provisional correspondence state without confirming matches."""

from collections import defaultdict, deque
from copy import deepcopy

from matching import propose_containment_anchors, propose_exact_anchors
from structural_evidence import analyze_containment


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
    return {
        "proposals": [proposal for proposal in proposals
                      if (proposal["referenceId"], proposal["studentId"]) not in excluded_pairs],
        "conflictingProposals": conflicts,
        "blockedProposals": blocked,
        **_candidate_graph(indices, candidates),
    }
