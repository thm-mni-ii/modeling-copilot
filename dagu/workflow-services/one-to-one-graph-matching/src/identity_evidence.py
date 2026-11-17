"""Explain identity separately from compatibility and structural correctness."""

import unicodedata

from artifacts import _key
from assignment_capacity import necessary_pairs
from structural_evidence import analyze_child_owner_evidence, analyze_containment
from text_similarity import configured_tiers, legacy_thresholds, pair_similarity


METHODS = ("exact_label", "text_similarity", "type_compatibility", "independent_children", "combined_children", "identified_owner", "connection_structure")
SIMILARITY_RESULTS = {"supported": "satisfied", "below_threshold": "violated", "unavailable": "not_evaluated"}


def normalized(value):
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def labelled(index, connection):
    """Whether a connection carries any text, on the line itself or as an additional label."""
    if (index.nodes[connection].get("label") or "").strip():
        return True
    return any(index.nodes[edge["source"]]["kind"] == "connectionLabel" and (index.nodes[edge["source"]].get("label") or "").strip()
               for edge in index.children.get(connection, ()))


def dependency_pairs(row):
    return {(item["referenceId"], item["studentId"]) for item in row.get("dependsOn", [])}


def evaluate_identity(indices, candidates, proposals, *, combined=(), connection_pairs=(), connection_candidates=(),
                      minimum_similarity=None, text_evidence=None, label_conflicts=()):
    """No new correspondence selection: explain the supplied one-to-one pairs.

    Unique means forced among evidence-backed alternatives after independent
    anchors, rather than unique among mere type-compatible alternatives.
    Text similarity is assessed for every admissible pair, so competing
    above-threshold alternatives remain visible to the uniqueness check.
    """
    graph_matching = {"minimumSimilarity": minimum_similarity or {}}
    if text_evidence is not None:
        graph_matching["textEvidence"] = text_evidence
    tiers = configured_tiers(candidates, graph_matching)
    thresholds = legacy_thresholds(tiers)
    similarity = pair_similarity(candidates, tiers) if tiers else {}
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
                criterion("identified_owner", "not_applicable" if not owner["referenceSubstructure"] and not owner["studentSubstructure"] else
                          {"consistent": "satisfied", "conflicting": "violated", "unknown": "unresolved"}[owner["ownerAnchorRelation"]],
                          [ref], [sub], [(owner["referenceOwnerId"], owner["studentOwnerId"])] if owner["ownerAnchorRelation"] == "consistent" else []),
                criterion("connection_structure", "not_evaluated", [ref], [sub]),
            ]
            if pair in label_conflicts:
                # GM-04a: equal labels, but children and neighbours point to another counterpart.
                evidence.append(criterion("label_structure", "violated", [ref], [sub]))
            if tiers:
                text = similarity[pair]
                details = ({"minimumSimilarity": thresholds} if text_evidence is None
                           else {"tier": text["tier"], "tierRank": text["tierRank"],
                                 # The thresholds of the reached tier, so consumers need not re-derive the verdict.
                                 **({"minimumSimilarity": tiers[text["tierRank"]]["minimumSimilarity"]}
                                    if text["tierRank"] is not None else {}),
                                 **({"veto": text["veto"]} if text["veto"] else {})})
                evidence.append(criterion("text_similarity", SIMILARITY_RESULTS[text["status"]], [ref], [sub],
                                          scores=text["scores"], **details))
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
            criterion("exact_label", "satisfied" if source["exactLabel"] else
                      "violated" if labelled(indices["reference"], pair[0]) or labelled(indices["student"], pair[1]) else "not_applicable",
                      [pair[0]], [pair[1]]),
            criterion("type_compatibility", "satisfied" if _key(left) == _key(right) else "violated", [pair[0]], [pair[1]]),
            criterion("connection_structure", "satisfied" if source["sameEndpoints"] else "violated", [pair[0]], [pair[1]],
                      dependencies, uniquenessVerified=source["uniquenessVerified"])]}

    def satisfied_pairs(method):
        return {pair for pair, row in rows.items()
                if any(item["method"] == method and item["result"] == "satisfied" for item in row["criteria"])}

    exact_pairs, similar_pairs = satisfied_pairs("exact_label"), satisfied_pairs("text_similarity")
    unique = set()
    while True:
        used_ref, used_sub = {r for r, _ in unique}, {s for _, s in unique}
        exact_anchors = necessary_pairs({pair for pair in exact_pairs
                                        if pair[0] not in used_ref and pair[1] not in used_sub})
        # Like exact text: an above-threshold pair anchors only if no open above-threshold alternative remains.
        # Tiers reserve in order: anchors of a stronger tier remove their elements before weaker tiers compete.
        similarity_anchors, tier_ref, tier_sub = set(), set(used_ref), set(used_sub)
        for rank in range(len(tiers)):
            found = necessary_pairs({pair for pair in similar_pairs if similarity[pair]["tierRank"] <= rank
                                     and pair[0] not in tier_ref and pair[1] not in tier_sub})
            similarity_anchors |= found
            tier_ref |= {r for r, _ in found}
            tier_sub |= {s for _, s in found}
        # An identified owner scopes its substructure children: text needs to be unique only within that owner.
        owner_scoped = necessary_pairs({
            pair for pair in similar_pairs if pair[0] not in used_ref and pair[1] not in used_sub
            and any(item["method"] == "identified_owner" and item["result"] == "satisfied"
                    and dependency_pairs(item) and dependency_pairs(item) <= unique for item in rows[pair]["criteria"])})
        eligible = {}
        for pair, row in rows.items():
            if pair[0] in used_ref or pair[1] in used_sub:
                continue
            if indices["reference"].nodes[pair[0]]["kind"] == "connection" and any(
                other != pair and (other[0] == pair[0] or other[1] == pair[1])
                and any(item["method"] == "connection_structure" and item["result"] == "satisfied"
                        and item.get("uniquenessVerified") and not dependency_pairs(item) <= unique
                        for item in alternative["criteria"])
                for other, alternative in rows.items()
            ):
                # Check independently supported endpoint alternatives before a text anchor.
                continue
            for item in row["criteria"]:
                dependencies = dependency_pairs(item)
                full_combination = item["method"] != "combined_children" or item.get("complete") is True
                unique_connection = item["method"] != "connection_structure" or item.get("uniquenessVerified") is True
                owner_discriminates = (item["method"] != "identified_owner" or pair in owner_scoped
                                       or any(criterion["method"] == "exact_label" and criterion["result"] == "satisfied"
                                              for criterion in row["criteria"]))
                exact_discriminates = item["method"] != "exact_label" or pair in exact_anchors
                similarity_discriminates = item["method"] != "text_similarity" or pair in similarity_anchors
                if (item["method"] != "type_compatibility" and item["result"] == "satisfied" and full_combination
                        and unique_connection and owner_discriminates and exact_discriminates and similarity_discriminates
                        and pair not in dependencies and dependencies <= unique
                        and not any(r == pair[0] or s == pair[1] for r, s in dependencies)):
                    eligible.setdefault(pair, []).append(item)
        # All independent evidence sources compete in the same one-to-one graph.
        supported = {pair: eligible[pair] for pair in necessary_pairs(eligible) & selected.keys()}
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
    strong = {pair for pair, row in rows.items() if any(item["role"] != "compatibility" and item["result"] == "satisfied"
              and (item["method"] != "combined_children" or item.get("complete")) for item in row["criteria"])}
    for pair, row in rows.items():
        for item in row["criteria"]:
            # Evidence resting on endpoints or owners that are not identified themselves stays open.
            if (item["method"] in ("identified_owner", "independent_children", "connection_structure")
                    and item["result"] == "satisfied" and not dependency_pairs(item) <= unique):
                item["result"] = "unresolved"
        positive = any(item["role"] == "support" and item["result"] == "satisfied" for item in row["criteria"])
        if row["status"] != "uniquely_supported" and positive:
            competitors = {other for other in strong if other != pair and (other[0] == pair[0] or other[1] == pair[1])}
            row["status"] = "unresolved" if pair in strong and competitors else "supported"
    return {"version": "1.1", "pairs": [rows[pair] for pair in sorted(rows)]}
