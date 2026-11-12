"""Describe containment evidence for validated candidate pairs."""

from collections import defaultdict


def _containment(index, identity):
    """Keep every child-to-root path; a cycle ends with the repeated node."""
    parents = sorted({edge["target"] for edge in index.parents.get(identity, ())})
    paths = []
    unambiguous = True
    pending = [(identity, [identity], {identity})]
    while pending:
        current, path, visited = pending.pop()
        edges = index.parents.get(current, ())
        if not edges:
            paths.append(path)
            continue
        if len(edges) != 1:
            unambiguous = False
        for edge in edges:
            parent = edge["target"]
            next_path = path + [parent]
            if parent in visited:
                unambiguous = False
                paths.append(next_path)
            else:
                pending.append((parent, next_path, visited | {parent}))
    paths.sort()
    owner = index.owner(identity) if parents else None
    return parents, owner, paths, unambiguous


def analyze_containment(indices, candidates, anchors):
    """Return structural evidence, not confirmed matches or errors."""
    reference_anchors = defaultdict(set)
    student_anchors = defaultdict(set)
    for anchor in anchors:
        reference_anchors[anchor["referenceId"]].add(anchor["studentId"])
        student_anchors[anchor["studentId"]].add(anchor["referenceId"])

    evidence = []
    for row in candidates["synonymMatrix"]:
        reference_id = row["referenceElementId"]
        reference_parents, reference_owner, reference_paths, reference_unambiguous = _containment(
            indices["reference"], reference_id
        )
        for match in row["matches"]:
            student_id = match["submissionElementId"]
            student_parents, student_owner, student_paths, student_unambiguous = _containment(
                indices["student"], student_id
            )
            relation = "unknown"
            mapped_owners = reference_anchors.get(reference_owner, set())
            if (reference_unambiguous and student_unambiguous and reference_owner is not None
                    and student_owner is not None and len(mapped_owners) == 1):
                mapped_owner = next(iter(mapped_owners))
                if len(student_anchors[mapped_owner]) == 1:
                    relation = "consistent" if mapped_owner == student_owner else "conflicting"
            evidence.append({
                "referenceId": reference_id,
                "studentId": student_id,
                "referenceParentIds": reference_parents,
                "studentParentIds": student_parents,
                "referenceOwnerId": reference_owner,
                "studentOwnerId": student_owner,
                "referenceContainmentPaths": reference_paths,
                "studentContainmentPaths": student_paths,
                "ownerAnchorRelation": relation,
            })
    evidence.sort(key=lambda item: (item["referenceId"], item["studentId"]))
    return evidence
