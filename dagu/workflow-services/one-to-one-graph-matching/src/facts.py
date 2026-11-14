"""Property evidence for existing correspondences; never select new matches."""

import unicodedata

from artifacts import _key
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
        ref_parents, ref_owner, _, ref_unique = _containment(reference, ref)
        sub_parents, sub_owner, _, sub_unique = _containment(student, sub)
        for name, expected, observed, available in (
            ("owner", [ref_owner] if ref_owner is not None else [],
             [sub_owner] if sub_owner is not None else [], mapping),
            ("containment", ref_parents, sub_parents, direct_mapping),
        ):
            basis = ("independent_evidence" if ref in independent and set(expected) <= independent
                     else "conditional_mapping")
            status = "unresolved"
            if ref_unique and sub_unique:
                if not expected and not observed:
                    status = "not_applicable"
                elif all(identity in available for identity in expected):
                    mapped = sorted(available[identity] for identity in expected)
                    status = "satisfied" if mapped == sorted(observed) else "violated" if complete else "unresolved"
                    if name == "containment" and status == "satisfied":
                        ref_roles = sorted(edge["role"] or "" for edge in reference.parents.get(ref, ()))
                        sub_roles = sorted(edge["role"] or "" for edge in student.parents.get(sub, ()))
                        status = "satisfied" if ref_roles == sub_roles else "violated"
            result.append(fact(name + "." + status, status, [ref], [sub], basis=basis,
                               reason="compared_" + name, referenceParentIds=expected,
                               submissionParentIds=observed,
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
            if name == "direct_children":
                for identity in expected & set(available):
                    left = [edge["role"] for edge in reference.parents[identity] if edge["target"] == ref]
                    right = [edge["role"] for edge in student.parents[available[identity]] if edge["target"] == sub]
                    roles_equal &= left == right
            status = ("unresolved" if not paths_known else
                      "violated" if outside or foreign or not roles_equal or len(observed) != len(expected) and complete else
                      "satisfied" if complete and not open_ids and not additional else "unresolved")
            result.append(fact(name + ".complete", status, [ref], [sub], basis="conditional_mapping",
                               reason="local_children_under_mapping", expected=len(expected), observed=len(observed),
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
    result = []
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
            if unique and owner in mapping and no_alternative and not candidate_alternatives:
                # The fixed mapping consumes all other compatible identities. A
                # count deficit alone with several remaining peers cannot do this.
                status, reason, basis = "violated", "unique_unassigned_child_class_absent", "conditional_mapping"
                dependencies = [{"referenceId": identity, "studentId": mapped}
                                for identity, mapped in sorted(mapping.items())]
        code = "counterpart.missing" if status == "violated" else "counterpart.present" if sub else "counterpart.unresolved"
        result.append(fact(code, status, [ref], [sub] if sub else [], basis=basis, reason=reason,
                           dependsOn=dependencies))
    for sub, node in sorted(student.nodes.items()):
        if sub not in reverse and node["kind"] in ("modelElement", "connection"):
            result.append(fact("counterpart.unresolved", "unresolved", [], [sub], reason="identity_unresolved"))

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
    result = []
    for row in rows:
        ref, sub = row["referenceId"], row["studentId"]
        left, right = reference.nodes[ref], student.nodes[sub]
        values = labels.get((ref, sub), (left.get("label"), right.get("label")))
        values = tuple(normalized(value) for value in values)
        if left["kind"] == "connection" and inventories is not None:
            values = tuple(sorted(normalized(text["matchText"]) for text in inventories[side]["connectionTexts"]
                                  if text["ownerConnectionId"] == identity and normalized(text["matchText"]))
                           for side, identity in (("reference", ref), ("student", sub)))
        label_status = ("not_applicable" if not any(values) else
                        "satisfied" if values[0] == values[1] else "violated")
        result.append(fact("label.different" if label_status == "violated" else "label.equal",
                           label_status, [ref], [sub], reason="compared_labels",
                           referenceValue=values[0], submissionValue=values[1]))
        known = all(node.get("languageResolution") == "resolved" and node.get("type")
                    and node.get("language") for node in (left, right))
        same_language = left["language"] == right["language"]
        status = ("unresolved" if not known or not same_language else
                  "satisfied" if left["type"] == right["type"] else "violated")
        result.append(fact("type.equal" if status != "violated" else "type.different", status,
                           [ref], [sub], reason="compared_concrete_types",
                           referenceValue=left["type"], submissionValue=right["type"]))
    result.extend(_structure_facts(indices, evaluation, graphs))
    result.extend(_connection_facts(indices, evaluation))
    result.extend(_presence_facts(indices, evaluation, graphs, candidates))
    result.extend(_local_connection_facts(indices, evaluation, graphs, result))
    return {"version": "1.0", "items": sorted(result, key=lambda item: (
        item["referenceIds"], item["submissionIds"], item["code"]))}
