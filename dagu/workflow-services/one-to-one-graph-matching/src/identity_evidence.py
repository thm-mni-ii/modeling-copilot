"""Explain identity separately from compatibility and structural correctness."""

import unicodedata

from artifacts import _key
from assignment_capacity import necessary_pairs
from structural_evidence import analyze_child_owner_evidence, analyze_containment


METHODS = ("exact_label", "type_compatibility", "independent_children", "combined_children", "identified_owner", "connection_structure")


def normalized(value):
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def dependency_pairs(row):
    return {(item["referenceId"], item["studentId"]) for item in row.get("dependsOn", [])}


def evaluate_identity(indices, candidates, proposals, *, combined=(), connection_pairs=(), connection_candidates=()):
    """No new correspondence selection: explain the supplied one-to-one pairs.

    Unique means forced among evidence-backed alternatives after independent
    anchors, rather than unique among mere type-compatible alternatives.
    """
    proposals = list(proposals) + list(connection_pairs)
    selected = {(row["referenceId"], row["studentId"]): row for row in proposals}
    if (len(selected) != len(proposals) or len({r for r, _ in selected}) != len(selected)
            or len({s for _, s in selected}) != len(selected)):
        raise ValueError("identity evidence requires one-to-one correspondences")
    containment = {(row["referenceId"], row["studentId"]): row
                   for row in analyze_containment(indices, candidates, [row for row in proposals
                       if indices["reference"].nodes[row["referenceId"]]["kind"] == "modelElement"])}
    children = {(row["referenceId"], row["studentId"]): row
                for row in analyze_child_owner_evidence(indices, candidates, proposals)}
    combined = {(row["referenceId"], row["studentId"]): row for row in combined}
    rows = {}

    def criterion(method, result, refs, subs, depends=(), **details):
        return {"method": method, "role": "compatibility" if method == "type_compatibility" else "support",
                "result": result, "referenceIds": sorted(set(refs)), "submissionIds": sorted(set(subs)),
                "dependsOn": [{"referenceId": r, "studentId": s} for r, s in sorted(set(depends))], **details}

    for row in candidates["synonymMatrix"]:
        ref = row["referenceElementId"]
        for match in row["matches"]:
            sub = match["submissionElementId"]
            pair = ref, sub
            left, right = indices["reference"].nodes[ref], indices["student"].nodes[sub]
            compatible = _key(left) is not None and _key(left) == _key(right)
            exact = bool(normalized(row["referenceLabel"])) and normalized(row["referenceLabel"]) == normalized(match["submissionLabel"])
            owner = containment[pair]
            supported_children = children.get(pair, {}).get("supportingChildren", [])
            child_pairs = {(item["referenceId"], item["studentId"]) for item in supported_children}
            shared = combined.get(pair)
            evidence = [
                criterion("exact_label", "satisfied" if exact else "violated", [ref], [sub],
                          dependency_pairs(selected[pair]) if selected.get(pair, {}).get("reason") == "unique_exact_after_reservations" else ()),
                criterion("type_compatibility", "satisfied" if compatible else "violated", [ref], [sub],
                          sameConcreteType=left["type"] == right["type"]),
                criterion("independent_children", "satisfied" if child_pairs else "unresolved" if pair in children else "not_applicable", [ref], [sub], child_pairs,
                          matched=len(child_pairs), expected=children.get(pair, {}).get("expected", 0)),
                criterion("combined_children", "satisfied" if shared and shared["matched"] else "unresolved" if shared else "not_evaluated" if pair in children else "not_applicable", [ref], [sub],
                          dependency_pairs(shared or {}), **{key: shared[key] for key in ("matched", "expected", "observed", "complete", "referenceChildIds") if shared and key in shared},
                          **({"submissionChildIds": shared["studentChildIds"]} if shared else {})),
                criterion("identified_owner", "not_applicable" if not owner["referenceParentIds"] and not owner["studentParentIds"] else
                          {"consistent": "satisfied", "conflicting": "violated", "unknown": "unresolved"}[owner["ownerAnchorRelation"]],
                          [ref], [sub], [(owner["referenceOwnerId"], owner["studentOwnerId"])] if owner["ownerAnchorRelation"] == "consistent" else []),
                criterion("connection_structure", "not_evaluated", [ref], [sub]),
            ]
            if selected.get(pair, {}).get("reason") == "supported_semantic_evidence":
                evidence.append(criterion("semantic_proposal", "satisfied", [ref], [sub], dependency_pairs(selected[pair])))
            rows[pair] = {"referenceId": ref, "studentId": sub, "status": "unresolved", "criteria": evidence}

    element_mapping = {r: s for r, s in selected if indices["reference"].nodes[r]["kind"] == "modelElement"}
    connection_evidence = {(row["referenceId"], row["studentId"]): row for row in connection_candidates}
    for pair, proposal in selected.items():
        if indices["reference"].nodes[pair[0]]["kind"] == "connection" and pair not in connection_evidence:
            connection_evidence[pair] = {"exactLabel": proposal["reason"] == "unique_exact_connection_label",
                                         "sameEndpoints": proposal["reason"] != "unique_exact_connection_label", "uniquenessVerified": True}
    for pair, source in connection_evidence.items():
        left, right = indices["reference"].nodes[pair[0]], indices["student"].nodes[pair[1]]
        endpoints = indices["reference"].endpoints.get(pair[0], {})
        dependencies = {(identity, element_mapping[identity]) for identity in endpoints.values() if identity in element_mapping}
        rows[pair] = {"referenceId": pair[0], "studentId": pair[1], "status": "unresolved", "criteria": [
            criterion("exact_label", "satisfied" if source["exactLabel"] else "violated", [pair[0]], [pair[1]]),
            criterion("type_compatibility", "satisfied" if _key(left) == _key(right) else "violated", [pair[0]], [pair[1]]),
            criterion("connection_structure", "satisfied" if source["sameEndpoints"] else "violated", [pair[0]], [pair[1]],
                      dependencies, uniquenessVerified=source["uniquenessVerified"])]}

    exact_pairs = {pair for pair, row in rows.items() if any(item["method"] == "exact_label" and item["result"] == "satisfied" for item in row["criteria"])}
    unique = necessary_pairs(exact_pairs) & selected.keys()
    for pair in unique:
        if dependency_pairs(selected[pair]):
            continue
        rows[pair]["status"] = "uniquely_supported"
        rows[pair]["criteria"][0]["role"] = "identity_anchor"
    unique = {pair for pair in unique if rows[pair]["status"] == "uniquely_supported"}
    while True:
        used_ref, used_sub = {r for r, _ in unique}, {s for _, s in unique}
        eligible = {}
        for pair, row in rows.items():
            if pair[0] in used_ref or pair[1] in used_sub:
                continue
            for item in row["criteria"]:
                dependencies = dependency_pairs(item)
                full_combination = item["method"] != "combined_children" or item.get("complete") is True
                unique_connection = item["method"] != "connection_structure" or item.get("uniquenessVerified") is True
                owner_discriminates = item["method"] != "identified_owner" or any(criterion["method"] == "exact_label" and criterion["result"] == "satisfied" for criterion in row["criteria"])
                if (item["method"] not in ("type_compatibility", "semantic_proposal") and item["result"] == "satisfied" and full_combination
                        and unique_connection and owner_discriminates
                        and pair not in dependencies and dependencies <= unique
                        and not any(r == pair[0] or s == pair[1] for r, s in dependencies)):
                    eligible.setdefault(item["method"], {})[pair] = item
        supported = {}
        for method_pairs in eligible.values():
            for pair in necessary_pairs(method_pairs) & selected.keys():
                supported.setdefault(pair, []).append(method_pairs[pair])
        promoted = set(supported)
        # Dependency edges may only point to identities established earlier.
        promoted = {pair for pair in promoted if dependency_pairs(selected[pair]) <= unique}
        if not promoted:
            break
        for pair in promoted:
            rows[pair]["status"] = "uniquely_supported"
            for item in supported[pair]:
                item["role"] = "identity_anchor"
        unique.update(promoted)
    strong = {pair for pair, row in rows.items() if any(item["role"] != "compatibility" and item["method"] != "semantic_proposal" and item["result"] == "satisfied"
              and (item["method"] != "combined_children" or item.get("complete")) for item in row["criteria"])}
    for pair, row in rows.items():
        for item in row["criteria"]:
            if item["method"] in ("identified_owner", "independent_children") and item["result"] == "satisfied" and not dependency_pairs(item) <= unique:
                item["result"] = "unresolved"
        positive = any(item["role"] == "support" and item["result"] == "satisfied" for item in row["criteria"])
        if row["status"] != "uniquely_supported" and positive:
            competitors = {other for other in strong if other != pair and (other[0] == pair[0] or other[1] == pair[1])}
            row["status"] = "unresolved" if pair in strong and competitors else "supported"
    return {"version": "1.0", "pairs": [rows[pair] for pair in sorted(rows)]}
