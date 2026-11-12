"""Propose provisional anchors from already validated semantic candidates."""

from collections import defaultdict
import unicodedata


def propose_exact_anchors(indices, candidates):
    """Return unique exact-label anchors and competing exact candidate pairs.

    The validated graph indices are reserved for later stages; graph structure
    does not influence these provisional proposals.
    """
    pairs_by_label = defaultdict(list)
    for row in candidates["synonymMatrix"]:
        reference_label = " ".join(unicodedata.normalize("NFC", row["referenceLabel"]).split())
        if not reference_label:
            continue
        for candidate in row["matches"]:
            student_label = " ".join(unicodedata.normalize("NFC", candidate["submissionLabel"]).split())
            if reference_label == student_label:
                pairs_by_label[reference_label].append((row["referenceElementId"], candidate["submissionElementId"]))

    anchors, unresolved = [], []
    for pairs in pairs_by_label.values():
        references = {reference_id for reference_id, _ in pairs}
        students = {student_id for _, student_id in pairs}
        if len(references) == len(students) == 1:
            reference_id, student_id = pairs[0]
            anchors.append({"referenceId": reference_id, "studentId": student_id, "reason": "unique_exact_label"})
        else:
            unresolved.extend({"referenceId": reference_id, "studentId": student_id}
                              for reference_id, student_id in pairs)
    anchors.sort(key=lambda pair: (pair["referenceId"], pair["studentId"]))
    unresolved.sort(key=lambda pair: (pair["referenceId"], pair["studentId"]))
    return anchors, unresolved


def propose_containment_anchors(exact_unresolved, anchors, containment_evidence):
    """Propose one-to-one anchors supported by already anchored owners."""
    used_references = {anchor["referenceId"] for anchor in anchors}
    used_students = {anchor["studentId"] for anchor in anchors}
    unresolved_pairs = {
        (pair["referenceId"], pair["studentId"]) for pair in exact_unresolved
        if pair["referenceId"] not in used_references and pair["studentId"] not in used_students
    }
    consistent_pairs = {
        (item["referenceId"], item["studentId"]) for item in containment_evidence
        if item["ownerAnchorRelation"] == "consistent"
        and (item["referenceId"], item["studentId"]) in unresolved_pairs
    }
    references = defaultdict(set)
    students = defaultdict(set)
    for reference_id, student_id in consistent_pairs:
        references[reference_id].add(student_id)
        students[student_id].add(reference_id)
    return [
        {"referenceId": reference_id, "studentId": student_id, "reason": "consistent_owner_anchor"}
        for reference_id, student_id in sorted(consistent_pairs)
        if len(references[reference_id]) == 1 and len(students[student_id]) == 1
    ]
