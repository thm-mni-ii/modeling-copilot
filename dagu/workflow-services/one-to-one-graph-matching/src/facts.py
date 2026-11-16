"""Property evidence for existing correspondences; never select new matches."""

import unicodedata

from artifacts import _key, content_hash
from structural_evidence import _containment


STATUSES = ("satisfied", "violated", "unresolved", "not_evaluated", "not_applicable")
BASES = ("direct_observation", "conditional_mapping", "independent_evidence")


def fact(code, status, references=(), submissions=(), *, basis="direct_observation", reason, **evidence):
    if status not in STATUSES or basis not in BASES:
        raise ValueError("invalid fact status or evidence basis")
    return {"code": code, "status": status, "referenceIds": sorted(set(references)),
            "submissionIds": sorted(set(submissions)),
            "evidence": {"basis": basis, "reason": reason, **evidence}}


def normalized(value):
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def semantic_children(index, parent):
    """Cross structural containers, but stop at the next domain element."""
    children, seen, pending = set(), {parent}, [parent]
    while pending:
        for edge in index.children.get(pending.pop(), ()):
            child = edge["source"]
            if child in seen:
                continue
            seen.add(child)
            node = index.nodes[child]
            if node["kind"] == "structuralElement":
                pending.append(child)
            elif node["kind"] == "modelElement":
                children.add(child)
    return children


def _structure_facts(indices, evaluation, graphs):
    reference, student = indices["reference"], indices["student"]
    rows = evaluation["mapping"]["provisionalElements"]
    mapping = {row["referenceId"]: row["studentId"] for row in rows}
    independent = {row["referenceId"] for row in rows
                   if row.get("reason") == "unique_exact_label" and not row.get("dependsOn")}
    if "identityEvidence" in evaluation:
        independent = {row["referenceId"] for row in evaluation["identityEvidence"]["pairs"]
                       if row["status"] == "uniquely_supported"}
    reverse = {sub: ref for ref, sub in mapping.items()}
    identities = {row["referenceId"]: row for row in evaluation.get("identityEvidence", {}).get("pairs", [])
                  if mapping.get(row["referenceId"]) == row["studentId"]}
    proposals = {row["referenceId"]: row for row in rows}

    def independent_of_relation(subject, parents):
        if subject not in independent or not set(parents) <= independent:
            return False
        if not identities:
            return True
        anchors = [item for item in identities[subject]["criteria"] if item["role"] == "identity_anchor"]
        if not any(item["method"] != "identified_owner" for item in anchors):
            return False
        for parent in parents:
            pending = [parent]
            seen = set()
            while pending:
                current = pending.pop()
                if current == subject:
                    return False
                if current in seen:
                    continue
                seen.add(current)
                if any(item["role"] == "identity_anchor" and subject in item.get("referenceChildIds", [])
                       for item in identities.get(current, {}).get("criteria", [])):
                    return False
                pending.extend(item["referenceId"] for item in proposals.get(current, {}).get("dependsOn", []))
        return True
    # Structural context is reused from the existing containment check.
    contexts = {}
    for row in evaluation.get("provisionalContainmentEvidence", []):
        for prefix in ("Source", "Target"):
            if row[prefix.lower() + "MappingBasis"] == "structural_child_of_mapped_parent":
                contexts[row["reference" + prefix + "Id"]] = row["student" + prefix + "Id"]
    direct_mapping = {**contexts, **mapping}
    result = []
    complete = all(graphs[side]["completeness"]["interpretation"] == "complete" for side in indices)
    for row in rows:
        ref, sub = row["referenceId"], row["studentId"]
        ref_parents, ref_owner, ref_paths, ref_unique = _containment(reference, ref)
        sub_parents, sub_owner, sub_paths, sub_unique = _containment(student, sub)
        for name, expected, observed, available in (
            ("owner", [ref_owner] if ref_owner is not None else [],
             [sub_owner] if sub_owner is not None else [], mapping),
            ("containment", ref_parents, sub_parents, direct_mapping),
        ):
            actual_references = {reverse.get(identity) for identity in observed}
            basis = ("independent_evidence" if independent_of_relation(ref, set(expected) | actual_references)
                     else "conditional_mapping")
            status = "unresolved"
            roles_known = all(edge["role"] is not None for index, paths in ((reference, ref_paths), (student, sub_paths))
                              for path in paths for identity in path for edge in index.parents.get(identity, ()))
            if not roles_known:
                status = "not_evaluated"
            elif ref_unique and sub_unique:
                if not expected and not observed:
                    status = "not_applicable"
                elif all(identity in available for identity in expected):
                    mapped = sorted(available[identity] for identity in expected)
                    status = "satisfied" if mapped == sorted(observed) else "violated" if complete else "unresolved"
                    if name == "containment" and status == "satisfied":
                        ref_roles = [edge["role"] for edge in reference.parents.get(ref, ())]
                        sub_roles = [edge["role"] for edge in student.parents.get(sub, ())]
                        status = "unresolved" if None in ref_roles + sub_roles else "satisfied" if sorted(ref_roles) == sorted(sub_roles) else "violated"
                if (ref in independent and observed and actual_references <= independent
                        and actual_references != set(expected)):
                    status = "violated"
                    basis = "independent_evidence" if independent_of_relation(ref, actual_references) else "conditional_mapping"
            result.append(fact(name + "." + status, status, [ref], [sub], basis=basis,
                               reason="compared_" + name, referenceParentIds=expected,
                               submissionParentIds=observed,
                               **({"placementStatus": {"satisfied": "correct_placement", "violated": "wrong_placement"}.get(status, "placement_unresolved")}
                                  if status != "not_applicable" else {}),
                               actualParentReferenceIds=sorted(identity for identity in actual_references if identity is not None),
                               expectedSubmissionParentIds=sorted(available[identity] for identity in expected if identity in available),
                               dependsOn=[{"referenceId": identity, "studentId": available[identity]}
                                          for identity in expected if identity in available]))

        for name, expected, observed, available in (
            ("children", semantic_children(reference, ref), semantic_children(student, sub), mapping),
            ("direct_children", {edge["source"] for edge in reference.children.get(ref, ())},
             {edge["source"] for edge in student.children.get(sub, ())}, direct_mapping),
        ):
            mapped = {available[identity] for identity in expected if identity in available}
            outside = sorted(identity for identity in expected if identity in available and available[identity] not in observed)
            additional = sorted(identity for identity in observed if identity not in mapped)
            foreign = sorted(identity for identity in additional if identity in set(available.values()))
            open_ids = sorted(expected - set(available))
            paths_known = all(_containment(index, identity)[3]
                              for index, values in ((reference, {ref} | expected), (student, {sub} | observed))
                              for identity in values)
            roles_equal = True
            correct = set()
            role_differences = []
            for identity in expected & set(available):
                mapped_child = available[identity]
                if mapped_child not in observed:
                    continue
                if name == "children":
                    def roles(index, child, parent):
                        _, _, paths, unique = _containment(index, child)
                        if not unique or parent not in paths[0]:
                            return None
                        path = paths[0][:paths[0].index(parent)]
                        return [index.parents[current][0]["role"] for current in path]
                    left = roles(reference, identity, ref)
                    right = roles(student, mapped_child, sub)
                else:
                    left = [edge["role"] for edge in reference.parents[identity] if edge["target"] == ref]
                    right = [edge["role"] for edge in student.parents[mapped_child] if edge["target"] == sub]
                if left is not None and right is not None and left == right and None not in left:
                    correct.add(identity)
                elif left is not None and right is not None and None not in left + right and left != right:
                    role_differences.append(identity)
            roles_equal = not role_differences
            status = ("unresolved" if not paths_known else
                      "violated" if outside or foreign or not roles_equal or len(observed) != len(expected) and complete else
                      "satisfied" if complete and not open_ids and not additional and len(correct) == len(expected) else "unresolved")
            result.append(fact(name + ".complete", status, [ref], [sub], basis="conditional_mapping",
                               reason="local_children_under_mapping", expected=len(expected), observed=len(observed),
                               matched=len(correct), recognized=len(expected & set(available)),
                               expectedReferenceIds=sorted(expected), correctlyContainedReferenceIds=sorted(correct),
                               movedReferenceIds=outside, unmatchedReferenceIds=open_ids,
                               unmatchedSubmissionIds=sorted(identity for identity in additional if identity not in set(available.values())),
                               roleDifferenceReferenceIds=sorted(role_differences),
                               outsideReferenceIds=outside, additionalSubmissionIds=additional,
                               mappedFromOtherTargets=foreign,
                               unresolvedReferenceIds=open_ids, rolesEqual=roles_equal, pathsUnambiguous=paths_known,
                               minimumMissing=max(0, len(expected) - len(observed)) if complete else None,
                               dependsOn=[{"referenceId": identity, "studentId": available[identity]}
                                          for identity in sorted(expected & set(available))]))
    return result


def _presence_facts(indices, evaluation, graphs, candidates):
    reference, student = indices["reference"], indices["student"]
    rows = evaluation["mapping"]["provisionalElements"] + evaluation["mapping"]["provisionalConnections"]
    mapping = {row["referenceId"]: row["studentId"] for row in rows}
    reverse = {sub: ref for ref, sub in mapping.items()}
    complete_student = graphs["student"]["completeness"]["interpretation"] == "complete"
    complete = complete_student and graphs["reference"]["completeness"]["interpretation"] == "complete"
    student_connections = set(student.by_kind["connection"])
    ambiguous = {event.get("referenceId") for event in evaluation.get("decisionEvents", [])
                 if "ambiguous_candidates" in event.get("reasonCodes", [])}
    identities = {row["referenceId"]: row["status"] for row in evaluation.get("identityEvidence", {}).get("pairs", [])
                  if (row["referenceId"], row["studentId"]) in set(mapping.items())}
    result = []
    def observation(index, identity):
        if identity is None:
            return None
        node = index.nodes[identity]
        value = {"ownerId": _containment(index, identity)[1],
                 "parents": [{"parentId": edge["target"], "role": edge["role"]}
                             for edge in sorted(index.parents.get(identity, ()), key=lambda edge: (edge["target"], edge["role"] or ""))]}
        if node["kind"] == "connection":
            endpoints = index.endpoints.get(identity, {})
            value["connection"] = {"id": identity, "sourceId": endpoints.get("source"), "targetId": endpoints.get("target"),
                                   "directed": node.get("directed"), "type": node["type"]}
        return value
    for ref, node in sorted(reference.nodes.items()):
        if node["kind"] not in ("modelElement", "connection"):
            continue
        sub = mapping.get(ref)
        status, reason, basis = ("satisfied", "existing_correspondence", "conditional_mapping") if sub else (
            "unresolved", "identity_unresolved", "direct_observation")
        dependencies = []
        if sub is None and node["kind"] == "connection" and complete_student and not student_connections:
            status, reason = "violated", "complete_submission_has_no_connections"
        elif sub is None and node["kind"] == "modelElement" and complete and ref not in ambiguous:
            _, owner, _, unique = _containment(reference, ref)
            key = _key(node)
            peers = [identity for identity, other in reference.nodes.items()
                     if identity not in mapping and other["kind"] == "modelElement" and _key(other) == key]
            free = [other for identity, other in student.nodes.items()
                    if identity not in reverse and other["kind"] == "modelElement"]
            no_alternative = (key is not None and node["languageResolution"] == "resolved" and len(peers) == 1
                              and all(other["languageResolution"] == "resolved" and _key(other) is not None
                                      and _key(other) != key for other in free))
            candidate_alternatives = [match["submissionElementId"] for row in candidates.get("synonymMatrix", [])
                                      if row["referenceElementId"] == ref for match in row["matches"]
                                      if match["submissionElementId"] not in reverse]
            owner_identified = "identityEvidence" not in evaluation or identities.get(owner) == "uniquely_supported"
            reservations_identified = "identityEvidence" not in evaluation or all(identities.get(identity) == "uniquely_supported"
                for identity in mapping if reference.nodes[identity]["kind"] == "modelElement" and _key(reference.nodes[identity]) == key)
            if unique and owner in mapping and owner_identified and reservations_identified and no_alternative and not candidate_alternatives:
                # The fixed mapping consumes all other compatible identities. A
                # count deficit alone with several remaining peers cannot do this.
                status, reason, basis = "violated", "unique_unassigned_child_class_absent", "conditional_mapping"
                dependencies = [{"referenceId": identity, "studentId": mapped}
                                for identity, mapped in sorted(mapping.items())]
        code = "counterpart.missing" if status == "violated" else "counterpart.present" if sub else "counterpart.unresolved"
        result.append(fact(code, status, [ref], [sub] if sub else [], basis=basis, reason=reason,
                           referenceObservation=observation(reference, ref), submissionObservation=observation(student, sub),
                           **({"placementStatus": "proven_absent" if status == "violated" else "unmatched_reference"} if sub is None else {}),
                           dependsOn=dependencies))
    for sub, node in sorted(student.nodes.items()):
        if sub not in reverse and node["kind"] in ("modelElement", "connection"):
            result.append(fact("counterpart.unresolved", "unresolved", [], [sub], reason="identity_unresolved",
                               submissionObservation=observation(student, sub), referenceObservation=None,
                               placementStatus="unmatched_submission"))

    for row in evaluation["mapping"]["provisionalElements"]:
        ref, sub = row["referenceId"], row["studentId"]
        expected = sorted(identity for identity, endpoints in reference.endpoints.items()
                          if endpoints.get("source") == ref and reference.nodes[identity].get("directed") is True)
        observed = sorted(identity for identity, endpoints in student.endpoints.items()
                          if endpoints.get("source") == sub and student.nodes[identity].get("directed") is True)
        unknown = any(not isinstance(student.nodes[identity].get("directed"), bool)
                      or student.endpoints.get(identity, {}).get("source") is None for identity in student_connections)
        if expected and not observed:
            result.append(fact("connections.outgoing_missing", "violated" if complete_student and not unknown else "unresolved",
                               [ref], [sub], basis="conditional_mapping", reason="no_outgoing_connection_under_parent_mapping",
                               referenceConnectionIds=expected, minimumMissing=len(expected) if complete_student and not unknown else None,
                               dependsOn=[{"referenceId": ref, "studentId": sub}]))
    structure = evaluation.get("provisionalConnectionStructure", {})
    closed_connections = complete_student and not structure.get("unresolvedStudentConnectionIds")
    for group in structure.get("byEndpoints", []):
        if group["referenceOnlyCount"]:
            # No individual connection identity is inferred from this deficit.
            result.append(fact("connection_group.minimum_missing", "violated" if closed_connections else "unresolved",
                               [item["id"] for item in group["referenceConnections"]],
                               [item["id"] for item in group["studentConnections"]], basis="conditional_mapping",
                               reason="endpoint_group_count_deficit", minimumMissing=group["referenceOnlyCount"] if closed_connections else None,
                               referenceEndpointIds=group["referenceEndpointIds"], submissionEndpointIds=group["studentEndpointIds"]))
    return result


def _identity_facts(indices, evaluation):
    if "identityEvidence" not in evaluation:
        return []
    pairs = evaluation["identityEvidence"]["pairs"]
    mapping = {row["referenceId"]: row["studentId"] for field in ("provisionalElements", "provisionalConnections")
               for row in evaluation["mapping"][field]}
    result = []
    for side, index in indices.items():
        for identity, node in sorted(index.nodes.items()):
            if node["kind"] not in ("modelElement", "connection"):
                continue
            key = "referenceId" if side == "reference" else "studentId"
            candidates = [row for row in pairs if row[key] == identity]
            selected = next((row for row in candidates if mapping.get(row["referenceId"]) == row["studentId"]), None)
            if selected and side == "student":
                continue
            status = selected["status"] if selected else "supported" if any(row["status"] == "supported" for row in candidates) else "unresolved"
            criteria = selected["criteria"] if selected else []
            if not selected:
                methods = sorted({item["method"] for row in candidates for item in row["criteria"]})
                for method in methods:
                    values = [item for row in candidates for item in row["criteria"] if item["method"] == method]
                    results = {item["result"] for item in values}
                    criteria.append({"method": method, "role": "compatibility" if method == "type_compatibility" else "support",
                                     "result": "satisfied" if "satisfied" in results else "unresolved" if "unresolved" in results else
                                               "violated" if results == {"violated"} else "not_evaluated",
                                     "referenceIds": [identity] if side == "reference" else [],
                                     "submissionIds": [identity] if side == "student" else [], "dependsOn": []})
            refs = [selected["referenceId"]] if selected else [identity] if side == "reference" else []
            subs = [selected["studentId"]] if selected else [identity] if side == "student" else []
            result.append(fact("identity." + status, "satisfied" if status == "uniquely_supported" else "unresolved", refs, subs,
                               basis="independent_evidence" if status == "uniquely_supported" else "conditional_mapping",
                               reason="evaluated_identity_evidence", identityStatus=status, criteria=criteria,
                               evaluationStatus="evaluated" if node.get("comparisonRole") == "semantic" and node.get("languageResolution") == "resolved" and _key(node) is not None else "not_evaluated",
                               supportingCandidateCount=sum(any(item["result"] == "satisfied" and item["role"] != "compatibility"
                                                                for item in row["criteria"]) for row in candidates)))
    return result


def _connection_facts(indices, evaluation):
    reference, student = indices["reference"], indices["student"]
    elements = {row["referenceId"]: row["studentId"] for row in evaluation["mapping"]["provisionalElements"]}
    result = []
    for row in evaluation["mapping"]["provisionalConnections"]:
        ref, sub = row["referenceId"], row["studentId"]
        left, right = reference.endpoints.get(ref, {}), student.endpoints.get(sub, {})
        ld, rd = reference.nodes[ref].get("directed"), student.nodes[sub].get("directed")
        states = {}
        for role in ("source", "target"):
            states[role] = ("not_applicable" if ld is False and rd is False else
                            "unresolved" if left.get(role) not in elements or right.get(role) is None else
                            "satisfied" if elements[left[role]] == right[role] else "violated")
        endpoints_known = all(left.get(role) in elements and right.get(role) is not None for role in ("source", "target"))
        states["endpoints"] = ("unresolved" if not endpoints_known else
                               "satisfied" if sorted(elements[left[role]] for role in ("source", "target"))
                               == sorted(right[role] for role in ("source", "target")) else "violated")
        states["direction"] = ("unresolved" if not isinstance(ld, bool) or not isinstance(rd, bool) else
                               "violated" if ld != rd else "satisfied" if not ld else
                               "unresolved" if states["endpoints"] != "satisfied" else
                               "satisfied" if states["source"] == states["target"] == "satisfied" else "violated")
        for name, status in states.items():
            result.append(fact("connection." + name, status, [ref], [sub], basis="conditional_mapping",
                               reason="compared_connection_" + name,
                               referenceEndpoints=left, submissionEndpoints=right,
                               dependsOn=[{"referenceId": identity, "studentId": elements[identity]}
                                          for identity in sorted(set(left.values()) & set(elements))]))
    # Group evidence never assigns identities to parallel or reversed connections.
    for group in evaluation.get("provisionalConnectionStructure", {}).get("byEndpoints", []):
        refs = [row["id"] for row in group["referenceConnections"]]
        subs = [row["id"] for row in group["studentConnections"]]
        for name, field in (("direction", "directionStatus"), ("type", "typeStatus"), ("configuration", "configurationStatus")):
            status = {"equal": "satisfied", "different": "violated", "not_evaluated": "not_evaluated"}[group[field]]
            result.append(fact("connection_group." + name, status, refs, subs, basis="conditional_mapping",
                               reason="endpoint_group_without_individual_identity",
                               referenceEndpointIds=group["referenceEndpointIds"],
                               submissionEndpointIds=group["studentEndpointIds"]))
    return result


def _local_connection_facts(indices, evaluation, graphs, facts):
    rows = evaluation["mapping"]["provisionalElements"]
    connections = {row["referenceId"]: row["studentId"] for row in evaluation["mapping"]["provisionalConnections"]}
    complete = all(graph["completeness"]["interpretation"] == "complete" for graph in graphs.values())
    endpoints_known = all(set(index.endpoints.get(identity, {})) == {"source", "target"}
                          and None not in index.endpoints[identity].values()
                          and isinstance(index.nodes[identity].get("directed"), bool)
                          for index in indices.values() for identity in index.by_kind["connection"])
    result = []
    for row in rows:
        ref, sub = row["referenceId"], row["studentId"]
        for name in ("connections", "incoming", "outgoing", "undirected"):
            def adjacent(index, identity):
                return {connection for connection, endpoints in index.endpoints.items()
                        if identity in endpoints.values() and (name == "connections"
                        or name == "undirected" and index.nodes[connection].get("directed") is False
                        or name in ("incoming", "outgoing") and index.nodes[connection].get("directed") is True
                        and endpoints.get("target" if name == "incoming" else "source") == identity)}
            expected, observed = adjacent(indices["reference"], ref), adjacent(indices["student"], sub)
            mapped = {connections[identity] for identity in expected if identity in connections}
            related = [item for item in facts if item["code"].startswith(("connection.", "connection_group.", "type."))
                       and (set(item["referenceIds"]) & expected or set(item["submissionIds"]) & observed)]
            status = ("violated" if any(item["status"] == "violated" for item in related)
                      or complete and endpoints_known and len(expected) != len(observed) else
                      "satisfied" if complete and endpoints_known and len(expected) == len(mapped) and mapped == observed
                      and all(item["status"] in ("satisfied", "not_applicable") for item in related) else "unresolved")
            result.append(fact(name + ".complete", status, [ref], [sub], basis="conditional_mapping",
                               reason="local_connections_under_mapping", expected=len(expected), observed=len(observed),
                               minimumMissing=max(0, len(expected) - len(observed)) if complete and endpoints_known else None,
                               referenceConnectionIds=sorted(expected), submissionConnectionIds=sorted(observed)))
    return result


def evaluate_facts(indices, evaluation, graphs, candidates, inventories=None):
    """Keep property results independent of provisional identity and other checks."""
    reference, student = indices["reference"], indices["student"]
    mappings = evaluation["mapping"]
    rows = mappings["provisionalElements"] + mappings["provisionalConnections"]
    labels = {(row["referenceElementId"], match["submissionElementId"]):
              (row["referenceLabel"], match["submissionLabel"])
              for row in candidates.get("synonymMatrix", []) for match in row["matches"]}
    inventory_labels = {side: {item["id"]: item for item in data["elements"]}
                        for side, data in (inventories or {}).items()}

    def text_status(value):
        return "missing" if value is None or isinstance(value, str) and not value.strip() else "present" if isinstance(value, str) else "unsupported"

    result = []
    for row in rows:
        ref, sub = row["referenceId"], row["studentId"]
        left, right = reference.nodes[ref], student.nodes[sub]
        values = labels.get((ref, sub), (left.get("label"), right.get("label")))
        statuses = {side: inventory_labels.get(side, {}).get(identity, {}).get("labelStatus", text_status(value))
                    for side, identity, value in (("reference", ref, values[0]), ("student", sub, values[1]))}
        values = tuple(normalized(value) if isinstance(value, str) else "" for value in values)
        if left["kind"] == "connection" and inventories is not None:
            values = tuple(sorted(normalized(text["matchText"]) for text in inventories[side]["connectionTexts"]
                                  if text["ownerConnectionId"] == identity and normalized(text["matchText"]))
                           for side, identity in (("reference", ref), ("student", sub)))
            statuses = {side: "unsupported" if any(text["labelStatus"] == "unsupported" for text in inventories[side]["connectionTexts"]
                                                   if text["ownerConnectionId"] == identity) else "present" if values[i] else "missing"
                        for i, (side, identity) in enumerate((("reference", ref), ("student", sub)))}
        unavailable = any(status != "present" for status in statuses.values())
        label_status = ("not_evaluated" if unavailable else
                        "satisfied" if values[0] == values[1] else "violated")
        result.append(fact("label.unavailable" if unavailable else "label.different" if label_status == "violated" else "label.equal",
                           label_status, [ref], [sub], reason="text_unavailable" if unavailable else "compared_labels",
                           referenceValue=values[0], submissionValue=values[1],
                           **({"labelStatus": statuses, "availability": "unavailable",
                               "unavailableReason": "unsupported_text" if "unsupported" in statuses.values() else "missing_text"}
                              if unavailable else {})))
        known = all(node.get("languageResolution") == "resolved" and node.get("comparisonRole") == "semantic" and node.get("type")
                    and node.get("language") for node in (left, right))
        same_language = left["language"] == right["language"]
        status = ("not_evaluated" if not known else "unresolved" if not same_language else
                  "satisfied" if left["type"] == right["type"] else "violated")
        result.append(fact("type.equal" if status != "violated" else "type.different", status,
                           [ref], [sub], reason="compared_concrete_types",
                           referenceValue=left["type"], submissionValue=right["type"]))
    result.extend(_structure_facts(indices, evaluation, graphs))
    result.extend(_connection_facts(indices, evaluation))
    result.extend(_presence_facts(indices, evaluation, graphs, candidates))
    result.extend(_local_connection_facts(indices, evaluation, graphs, result))
    result.extend(_identity_facts(indices, evaluation))
    missing = {ref for item in result if item["code"] == "counterpart.missing" for ref in item["referenceIds"]}
    for item in result:
        evidence = item["evidence"]
        targets = {("reference", identity) for identity in item["referenceIds"]} | {("submission", identity) for identity in item["submissionIds"]}
        if item["code"].startswith(("owner.", "containment.")):
            targets.update(("reference", identity) for identity in evidence["referenceParentIds"])
            targets.update(("submission", identity) for identity in evidence["submissionParentIds"] + evidence["expectedSubmissionParentIds"])
            if item["status"] == "violated":
                evidence["findingId"] = content_hash({"kind": "placement", "referenceIds": item["referenceIds"], "submissionIds": item["submissionIds"]})
        if item["code"] in ("children.complete", "direct_children.complete"):
            evidence["provenAbsentReferenceIds"] = sorted(set(evidence["expectedReferenceIds"]) & missing)
        item["targets"] = [{"side": side, "id": identity, "kind": indices["student" if side == "submission" else side].nodes[identity]["kind"]}
                           for side, identity in sorted(targets)]
        item["id"] = content_hash(item)
    return {"version": "1.1" if "identityEvidence" in evaluation else "1.0", "items": sorted(result, key=lambda item: (
        item["referenceIds"], item["submissionIds"], item["code"]))}
