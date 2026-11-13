"""Describe containment evidence for validated candidate pairs."""

from collections import defaultdict

from artifacts import _key


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


def analyze_child_owner_evidence(indices, candidates, proposals):
    """Describe child evidence for existing, compatible owner candidates."""
    containment = {
        side: {identity: _containment(index, identity) for identity, node in index.nodes.items()
               if node["kind"] == "modelElement" and node["comparisonRole"] == "semantic"}
        for side, index in indices.items()
    }

    def possible_owners(index, paths):
        owners = set()
        for path in paths:
            for identity in path[1:]:
                node = index.nodes[identity]
                if node["kind"] != "structuralElement":
                    if node["kind"] == "modelElement" and node["comparisonRole"] == "semantic":
                        owners.add(identity)
                    break
        return owners

    children = {}
    for side, index in indices.items():
        children[side] = defaultdict(set)
        for identity, (_, _, paths, _) in containment[side].items():
            for owner in possible_owners(index, paths):
                children[side][owner].add(identity)

    by_reference = {item["referenceId"]: item for item in proposals}
    by_student = {item["studentId"]: item for item in proposals}
    by_pair = {(item["referenceId"], item["studentId"]): item for item in proposals}

    def dependencies(item):
        found, pending = set(), list(item["dependsOn"])
        while pending:
            dependency = pending.pop()
            pair = (dependency["referenceId"], dependency["studentId"])
            if pair in found:
                continue
            found.add(pair)
            if pair in by_pair:
                pending.extend(by_pair[pair]["dependsOn"])
        return found

    result = []
    for row in candidates["synonymMatrix"]:
        ref = row["referenceElementId"]
        for match in row["matches"]:
            sub = match["submissionElementId"]
            ref_children, sub_children = children["reference"].get(ref, set()), children["student"].get(sub, set())
            if not (ref_children or sub_children):
                continue
            ref_key, sub_key = _key(indices["reference"].nodes[ref]), _key(indices["student"].nodes[sub])
            if ref_key is None or ref_key != sub_key:
                continue
            evidence = {"referenceId": ref, "studentId": sub,
                        "supportingChildren": [], "conflictingChildren": [], "unresolvedChildren": []}
            involved = {(item["referenceId"], item["studentId"])
                        for item in proposals
                        if item["referenceId"] in ref_children or item["studentId"] in sub_children}
            for child_ref, child_sub in sorted(involved):
                item = by_pair[child_ref, child_sub]
                ref_info = containment["reference"][child_ref]
                sub_info = containment["student"][child_sub]
                ancestors = dependencies(item)
                independent = (item["reason"] in ("unique_exact_label", "unique_exact_after_reservations")
                               and not any(r == ref or s == sub for r, s in ancestors))
                entry = {
                    "referenceId": child_ref, "studentId": child_sub,
                    "referenceOwnerId": ref_info[1], "studentOwnerId": sub_info[1],
                    "referenceContainmentPaths": ref_info[2], "studentContainmentPaths": sub_info[2],
                    "reason": item["reason"], "dependsOn": [dict(dependency) for dependency in item["dependsOn"]],
                }
                if not independent or not ref_info[3] or not sub_info[3]:
                    entry["decisionBasis"] = "dependent_or_ambiguous"
                    evidence["unresolvedChildren"].append(entry)
                elif ref_info[1] == ref and sub_info[1] == sub:
                    entry["decisionBasis"] = "independent_child_pair"
                    evidence["supportingChildren"].append(entry)
                else:
                    entry["decisionBasis"] = "different_owner"
                    evidence["conflictingChildren"].append(entry)
            for side, owner_children, mapped in (
                ("reference", ref_children, by_reference), ("student", sub_children, by_student)
            ):
                for child in sorted(owner_children - mapped.keys()):
                    entry = {"referenceId": child if side == "reference" else None,
                             "studentId": child if side == "student" else None,
                             "referenceContainmentPaths": containment[side][child][2] if side == "reference" else [],
                             "studentContainmentPaths": containment[side][child][2] if side == "student" else [],
                             "decisionBasis": "child_mapping_missing"}
                    evidence["unresolvedChildren"].append(entry)
            result.append(evidence)
    return sorted(result, key=lambda item: (item["referenceId"], item["studentId"]))
