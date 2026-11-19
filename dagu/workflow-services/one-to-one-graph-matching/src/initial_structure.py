"""Evaluate containment only for provisional element correspondences."""

from collections import Counter
from copy import deepcopy
import json

from structural_evidence import _containment, analyze_containment


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


def evaluate_containment_relations(indices, provisional_mapping):
    """Evaluate every reference containment edge using independent correspondence evidence."""
    indices = deepcopy(indices)
    reference, student = indices["reference"], indices["student"]
    pairs = [(item["referenceId"], item["studentId"]) for item in provisional_mapping]
    if (len({ref for ref, _ in pairs}) != len(pairs)
            or len({sub for _, sub in pairs}) != len(pairs)
            or any(ref not in reference.nodes or reference.nodes[ref]["kind"] != "modelElement"
                   or sub not in student.nodes or student.nodes[sub]["kind"] != "modelElement"
                   for ref, sub in pairs)):
        raise ValueError("provisional mapping must contain unique one-to-one model element pairs")

    proposals = {item["referenceId"]: item for item in provisional_mapping}
    independent = {
        item["referenceId"]: item["studentId"] for item in provisional_mapping
        if item["reason"] == "unique_exact_label" and not item["dependsOn"]
    }
    containment = {
        side: {identity: _containment(index, identity) for identity in index.nodes}
        for side, index in indices.items()
    }

    def structural_children(index, parent):
        children = {}
        for edge in index.children.get(parent, ()):
            child = index.nodes[edge["source"]]
            if (child["kind"] != "structuralElement" or child["definition"] is None
                    or child["languageResolution"] != "resolved"):
                continue
            key = (child["type"], json.dumps(child["definition"], sort_keys=True), edge["role"])
            children.setdefault(key, []).append(edge["source"])
        return children

    structural = {}
    pending = list(sorted(independent.items()))
    while pending:
        ref_parent, sub_parent = pending.pop()
        if not containment["reference"][ref_parent][3] or not containment["student"][sub_parent][3]:
            continue
        ref_children = structural_children(reference, ref_parent)
        sub_children = structural_children(student, sub_parent)
        for key, refs in ref_children.items():
            subs = sub_children.get(key, [])
            if len(refs) != 1 or len(subs) != 1:
                continue
            ref, sub = refs[0], subs[0]
            if not containment["reference"][ref][3] or not containment["student"][sub][3]:
                continue
            structural[ref] = {
                "studentId": sub,
                "dependsOn": [{"referenceId": ref_parent, "studentId": sub_parent}]
                + (structural[ref_parent]["dependsOn"] if ref_parent in structural else []),
            }
            pending.append((ref, sub))

    def mapped(identity):
        if identity in proposals:
            item = proposals[identity]
            return item["studentId"], item["reason"], item["dependsOn"]
        if identity in structural:
            item = structural[identity]
            return item["studentId"], "structural_child_of_mapped_parent", item["dependsOn"]
        return None, None, []

    rows = []
    edges = [edge for values in reference.parents.values() for edge in values]
    for edge in sorted(edges, key=lambda item: (item["source"], item["target"], item["role"] or "")):
        ref_source, ref_target = edge["source"], edge["target"]
        sub_source, source_basis, source_dependencies = mapped(ref_source)
        sub_target, target_basis, target_dependencies = mapped(ref_target)
        ref_paths = containment["reference"][ref_source][2]
        sub_paths = containment["student"][sub_source][2] if sub_source is not None else []
        student_parents = containment["student"][sub_source][0] if sub_source is not None else []
        status = "unresolved"
        if reference.nodes[ref_source]["kind"] == "structuralElement":
            # Its inferred mapping uses this very parent relation.
            basis = "structural_source_depends_on_relation"
        elif sub_source is None:
            basis = "source_mapping_missing"
        elif ref_source not in independent:
            basis = "source_mapping_not_independent"
        elif sub_target is None:
            basis = "target_mapping_missing"
        elif ref_target not in independent and ref_target not in structural:
            basis = "target_mapping_not_independent"
        elif (not containment["reference"][ref_source][3]
              or not containment["student"][sub_source][3]):
            basis = "ambiguous_containment_path"
        elif student_parents == [sub_target]:
            status, basis = "satisfied", "same_parent"
        else:
            status, basis = "violated", "different_parent"
        rows.append({
            "referenceSourceId": ref_source, "referenceTargetId": ref_target,
            "referenceRole": edge["role"], "studentSourceId": sub_source,
            "studentTargetId": sub_target, "studentParentIds": student_parents,
            "referenceContainmentPaths": ref_paths, "studentContainmentPaths": sub_paths,
            "sourceMappingBasis": source_basis, "sourceMappingDependencies": source_dependencies,
            "targetMappingBasis": target_basis, "targetMappingDependencies": target_dependencies,
            "status": status, "decisionBasis": basis,
        })

    counts = Counter(item["status"] for item in rows)
    satisfied, violated, unresolved = (counts[status] for status in ("satisfied", "violated", "unresolved"))
    total = len(rows)
    return {
        "relations": rows,
        "metrics": {
            "referenceRelationCount": total, "satisfied": satisfied, "violated": violated,
            "unresolved": unresolved,
            "agreement": {
                "lower": satisfied / total if total else None,
                "upper": (satisfied + unresolved) / total if total else None,
            },
        },
    }
