"""Summarize existing matching results for individual submission objects."""

from collections import defaultdict
import unicodedata

from analysis_contract import canonical_status, category_for, category_summary, content_hash, require, structure_hints
from fact_projection import project_facts


def _normalized(value):
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def _children(index, parent):
    children, seen, pending = set(), {parent}, [parent]
    while pending:
        for edge in index.children.get(pending.pop(), ()):
            child = edge["source"]
            if child in seen:
                continue
            seen.add(child)
            kind = index.nodes[child]["kind"]
            if kind == "structuralElement":
                pending.append(child)
            elif kind == "modelElement":
                children.add(child)
    return children


def _connections(index, role=None):
    result = defaultdict(set)
    for connection, endpoints in index.endpoints.items():
        directed = index.nodes[connection].get("directed")
        roles = ("source", "target")
        if role is not None:
            available = (("outgoing", "incoming") if directed is True else
                         ("undirected", "undirected") if directed is False else ("unresolved", "unresolved"))
            roles = tuple(key for key, category in zip(roles, available) if category == role)
        for key in roles:
            endpoint = endpoints.get(key)
            if endpoint is not None:
                result[endpoint].add(connection)
    return result


def _connection_value(index, identity):
    if identity is None:
        return None
    node = index.nodes[identity]
    return {"id": identity, "sourceId": index.endpoints.get(identity, {}).get("source"),
            "targetId": index.endpoints.get(identity, {}).get("target"),
            "directed": node.get("directed"), "type": node["type"]}


def _parents(index, identity):
    return [{"parentId": edge["target"], "role": edge["role"]}
            for edge in sorted(index.parents.get(identity, ()), key=lambda edge: (edge["target"], edge["role"] or ""))]


def build(store, bundle, indices, candidates, comparison, compact):
    reference, submission = indices["reference"], indices["student"]
    elements = comparison["mapping"]["provisionalElements"]
    connections = comparison["mapping"]["provisionalConnections"]
    mappings = {row["referenceId"]: row for row in elements + connections}
    require(len(mappings) == len(elements) + len(connections), "duplicate reference mapping")
    reverse = {row["studentId"]: row["referenceId"] for row in mappings.values()}
    require(len(reverse) == len(mappings), "duplicate submission mapping")

    derived = defaultdict(set)
    for row in comparison.get("provisionalContainmentEvidence", []):
        for prefix in ("Source", "Target"):
            if row[prefix.lower() + "MappingBasis"] == "structural_child_of_mapped_parent":
                ref, sub = row["reference" + prefix + "Id"], row["student" + prefix + "Id"]
                if ref is not None and sub is not None:
                    derived[ref].add(sub)
    contexts = {ref: next(iter(values)) for ref, values in derived.items() if len(values) == 1}
    context_reverse = defaultdict(set)
    for ref, sub in contexts.items():
        context_reverse[sub].add(ref)
    contexts = {ref: sub for ref, sub in contexts.items() if len(context_reverse[sub]) == 1}
    reverse_contexts = {sub: ref for ref, sub in contexts.items()}
    connection_dependencies = {row["referenceId"]: row["dependsOn"] for row in
        comparison.get("provisionalTypeComparison", {}).get("connections", {}).get("pairs", [])}

    annotations = {}
    for identity, node in sorted(submission.nodes.items()):
        ref = reverse.get(identity)
        row = mappings.get(ref)
        target = {"side": "submission", "id": identity, "kind": node["kind"]}
        match = {"status": "provisional" if row else
                 "unresolved" if node["kind"] in ("modelElement", "connection") else "not_evaluated"}
        item = {"target": target, "match": match,
                "checks": {key: "not_evaluated" for key in ("label", "type", "owner", "containment")}, "hints": [],
                "category": category_for(bundle, node)}
        if row:
            item["referenceId"] = ref
            match["reason"] = row["reason"]
            dependencies = row.get("dependsOn", connection_dependencies.get(ref, []))
            if dependencies:
                match["dependsOn"] = [{"referenceId": dep["referenceId"], "submissionId": dep["studentId"]}
                                      for dep in dependencies]
        elif identity in reverse_contexts:
            item["context"] = {"referenceId": reverse_contexts[identity], "basis": "structural_child_of_mapped_parent",
                               "status": "derived_context"}
        if match["status"] == "unresolved":
            item["hints"].append({"code": "identity.unresolved"})
        annotations[identity] = item

    selected = {(ref, row["studentId"]) for ref, row in mappings.items()}
    semantic = {(row["referenceId"], row["studentId"]): row for row in
                comparison["semanticRefinement"].get("candidateEvidence", [])
                if row["supportingMethods"] and (row["referenceId"], row["studentId"]) in selected}
    for row in candidates["synonymMatrix"]:
        ref = row["referenceElementId"]
        if ref not in mappings:
            continue
        sub = mappings[ref]["studentId"]
        for candidate in row["matches"]:
            if candidate["submissionElementId"] != sub:
                continue
            left, right = _normalized(row["referenceLabel"]), _normalized(candidate["submissionLabel"])
            status = "not_evaluated" if not left or not right else "exact" if left == right else "different"
            annotations[sub]["checks"]["label"] = status
            if status == "different":
                annotations[sub]["hints"].append({"code": "label.different", "referenceId": ref})
            evidence = semantic.get((ref, sub))
            if mappings[ref]["reason"] == "supported_semantic_evidence" and evidence:
                scores = candidate["scores"] or {}
                annotations[sub]["match"]["methods"] = [
                    {"name": name, "score": scores[name]} if name in scores else {"name": name}
                    for name in evidence["supportingMethods"]]
            break

    connection_texts = {}
    for side, key in (("reference", comparison["pair"]["referenceKey"]), ("student", "submission")):
        texts = defaultdict(list)
        for text in store.read(f"labels/{key}.json")["result"]["connectionTexts"]:
            value = _normalized(text["matchText"])
            if value:
                texts[text["ownerConnectionId"]].append(value)
        connection_texts[side] = texts
    for row in connections:
        ref, sub = row["referenceId"], row["studentId"]
        left = sorted(connection_texts["reference"].get(ref, ()))
        right = sorted(connection_texts["student"].get(sub, ()))
        if left and right:
            status = "exact" if left == right else "different"
            annotations[sub]["checks"]["label"] = status
            if status == "different":
                annotations[sub]["hints"].append({"code": "label.different", "referenceId": ref})

    for field in ("elements", "connections"):
        for row in comparison.get("provisionalTypeComparison", {}).get(field, {}).get("pairs", []):
            sub = row["studentId"]
            if sub is None:
                continue
            require(sub in annotations and reverse.get(sub) == row["referenceId"], "type pair has no mapping")
            annotations[sub]["checks"]["type"] = row["status"]
            if row["status"] == "compatible_type_difference":
                annotations[sub]["hints"].append({"code": "type.compatible_difference",
                    "referenceId": row["referenceId"], "referenceType": row["referenceType"],
                    "submissionType": row["studentType"], "comparisonGroup": row["comparisonGroup"]})

    for row in comparison.get("provisionalOwnerEvidence", []):
        sub = row["studentId"]
        require(sub in annotations and reverse.get(sub) == row["referenceId"], "owner pair has no mapping")
        annotations[sub]["checks"]["owner"] = row["status"]
        if row["status"] in ("violated", "unresolved", "different"):
            annotations[sub]["hints"].append({"code": "owner." + row["status"],
                "referenceOwnerId": row["referenceOwnerId"], "submissionOwnerId": row["studentOwnerId"]})

    containment_relations = []
    relation_statuses = defaultdict(list)
    for row in comparison.get("provisionalContainmentEvidence", []):
        sub_child, sub_parent = row["studentSourceId"], row["studentTargetId"]
        observed_parents = _parents(submission, sub_child)
        observed_roles = [edge["role"] for edge in observed_parents if edge["parentId"] == sub_parent]
        role_status = ("unresolved" if row["status"] == "unresolved" else
                       "not_evaluated" if row["referenceRole"] is None or not observed_roles or None in observed_roles else
                       "equal" if observed_roles == [row["referenceRole"]] else "different")
        status = "violated" if role_status == "different" else row["status"]
        relation = {"referenceChildId": row["referenceSourceId"], "referenceParentId": row["referenceTargetId"],
                    "referenceRole": row["referenceRole"], "submissionChildId": sub_child,
                    "submissionParentId": sub_parent, "observedParents": observed_parents,
                    "status": status, "roleStatus": role_status, "basis": row["decisionBasis"]}
        relation["id"] = content_hash(relation)
        containment_relations.append(relation)
        involved = {sub_child, sub_parent, *(edge["parentId"] for edge in observed_parents)} - {None}
        for sub in sorted(involved):
            if sub is not None and sub in annotations:
                annotations[sub].setdefault("relationIds", []).append(relation["id"])
                relation_statuses[sub].append(status)
                if status == "violated":
                    annotations[sub]["hints"].append({"code": "containment.violated", "relationId": relation["id"],
                    "referenceId": row["referenceSourceId"], "referenceParentId": row["referenceTargetId"],
                    "submissionId": sub_child, "submissionParentIds": row["studentParentIds"],
                    "referenceRole": row["referenceRole"], "submissionRoles": observed_roles,
                    "basis": row["decisionBasis"]})
    for sub, statuses in relation_statuses.items():
        annotations[sub]["checks"]["containment"] = ("violated" if "violated" in statuses else
                                                       "unresolved" if "unresolved" in statuses else "satisfied")

    for sub, item in annotations.items():
        if submission.nodes[sub]["kind"] != "connection":
            continue
        ref = reverse.get(sub)
        reference_endpoints = reference.endpoints.get(ref, {})
        student_endpoints = submission.endpoints.get(sub, {})
        item["connection"] = {"reference": _connection_value(reference, ref),
                              "submission": _connection_value(submission, sub)}
        item["checks"].update({key: "unresolved" for key in ("source", "target", "direction", "connectionType")})
        ref_direction = reference.nodes[ref].get("directed") if ref is not None else None
        sub_direction = submission.nodes[sub].get("directed")
        for role in ("source", "target"):
            if ref_direction is False and sub_direction is False:
                item["checks"][role] = "not_applicable"
            elif reference_endpoints.get(role) in mappings and student_endpoints.get(role) is not None:
                item["checks"][role] = ("equal" if mappings[reference_endpoints[role]]["studentId"] == student_endpoints[role]
                                        else "different")
        if (ref is None or any(reference_endpoints.get(role) not in mappings or not student_endpoints.get(role)
                               for role in ("source", "target"))):
            item["checks"]["endpoints"] = "unresolved"
        else:
            mapped = sorted(mappings[reference_endpoints[role]]["studentId"] for role in ("source", "target"))
            observed = sorted(student_endpoints[role] for role in ("source", "target"))
            item["checks"]["endpoints"] = "equal" if mapped == observed else "different"
            if mapped != observed:
                item["hints"].append({"code": "connection.endpoints_different", "referenceId": ref})
        if isinstance(ref_direction, bool) and isinstance(sub_direction, bool):
            item["checks"]["direction"] = ("different" if ref_direction != sub_direction else
                "equal" if not ref_direction else "unresolved" if item["checks"]["endpoints"] != "equal" else
                "equal" if item["checks"]["source"] == item["checks"]["target"] == "equal" else "different")
        if ref is not None:
            ref_node, sub_node = reference.nodes[ref], submission.nodes[sub]
            if all(node.get("languageResolution") == "resolved" and node["type"] for node in (ref_node, sub_node)) and ref_node["language"] == sub_node["language"]:
                item["checks"]["connectionType"] = "equal" if ref_node["type"] == sub_node["type"] else "different"
        for dimension in ("source", "target", "direction", "connectionType"):
            if item["checks"][dimension] == "different":
                item["hints"].append({"code": "connection." + dimension + "_different", "referenceId": ref})

    connection_groups = []
    for row in comparison.get("provisionalConnectionStructure", {}).get("byEndpoints", []):
        refs = sorted(item["id"] for item in row["referenceConnections"])
        subs = sorted(item["id"] for item in row["studentConnections"])
        group_id = content_hash({"referenceIds": refs, "submissionIds": subs})
        for sub in subs:
            require(sub in annotations, "connection group refers to unknown submission object")
            annotations[sub].setdefault("groupIds", []).append(group_id)
        dimensions = [name for name, key in (("configuration", "configurationStatus"),
                                               ("direction", "directionStatus"), ("type", "typeStatus"))
                      if row[key] == "different"]
        connection_groups.append({"id": group_id, "referenceIds": refs, "submissionIds": subs,
            "referenceEndpointIds": sorted(row["referenceEndpointIds"]),
            "submissionEndpointIds": sorted(row["studentEndpointIds"]),
            "checks": {"configuration": row["configurationStatus"], "direction": row["directionStatus"],
                       "connectionType": row["typeStatus"]},
            "referenceOnlyCount": row["referenceOnlyCount"], "submissionOnlyCount": row["studentOnlyCount"],
            "hints": [{"code": "connection.group_difference", "dimensions": dimensions}]
                if dimensions or row["referenceOnlyCount"] or row["studentOnlyCount"] else []})

    ambiguous_references = set()
    for event in comparison.get("decisionEvents", []):
        if "ambiguous_candidates" in event.get("reasonCodes", []):
            ambiguous_references.add(event.get("referenceId"))
        sub = event.get("studentId")
        if (sub in annotations and annotations[sub]["match"]["status"] == "unresolved"
                and "ambiguous_candidates" in event.get("reasonCodes", [])):
            hint = {"code": "identity.ambiguous"}
            if hint not in annotations[sub]["hints"]:
                annotations[sub]["hints"].append(hint)

    adjacent = {"reference": _connections(reference), "student": _connections(submission)}
    role_adjacency = {role: {"reference": _connections(reference, role), "student": _connections(submission, role)}
                      for role in ("incoming", "outgoing", "undirected", "unresolved")}
    for sub, item in annotations.items():
        ref = reverse.get(sub, reverse_contexts.get(sub))
        item["containment"] = {"referenceParents": _parents(reference, ref) if ref is not None else None,
                               "submissionParents": _parents(submission, sub)}
        item["owner"] = {"referenceOwnerId": reference.owner(ref) if ref is not None else None,
                         "submissionOwnerId": submission.owner(sub),
                         "status": item["checks"].get("owner", "not_evaluated")}
        sub_children = _children(submission, sub)
        ref_children = _children(reference, ref) if ref is not None else set()
        sub_connections = adjacent["student"].get(sub, set())
        ref_connections = adjacent["reference"].get(ref, set()) if ref is not None else set()
        is_parent = (submission.nodes[sub]["kind"] == "structuralElement" or bool(submission.children.get(sub))
                     or ref is not None and bool(reference.children.get(ref)))
        local = {}
        neighborhoods = [("children", ref_children, sub_children), ("connections", ref_connections, sub_connections)]
        ref_direct = {edge["source"] for edge in reference.children.get(ref, ())}
        sub_direct = {edge["source"] for edge in submission.children.get(sub, ())}
        if ref_direct or sub_direct or is_parent:
            neighborhoods.append(("directChildren", ref_direct, sub_direct))
        if submission.nodes[sub]["kind"] in ("modelElement", "structuralElement"):
            neighborhoods += [(role, sides["reference"].get(ref, set()), sides["student"].get(sub, set()))
                              for role, sides in role_adjacency.items()]
        for name, expected, observed in neighborhoods:
            if not expected and not observed and not is_parent and name not in role_adjacency:
                continue
            recognized = {identity for identity in expected if identity in mappings}
            at_target = {identity for identity in recognized if mappings[identity]["studentId"] in observed}
            unresolved_ref = sorted(expected - recognized)
            unresolved_sub = sorted(identity for identity in observed if identity not in reverse)
            other_targets = sorted(identity for identity in observed
                                   if identity in reverse and reverse[identity] not in expected) if ref is not None else []
            local[name] = {"expected": len(expected) if ref is not None else None, "observed": len(observed),
                           "recognized": len(recognized) if ref is not None else None,
                           "recognizedAtTarget": len(at_target) if ref is not None else None,
                           "unresolvedReference": len(unresolved_ref) if ref is not None else None,
                           "unresolvedSubmission": len(unresolved_sub),
                           "mappedFromOtherTargets": len(other_targets) if ref is not None else None}
            if name not in ("children", "directChildren"):
                local[name]["deviating"] = sum(any(annotations[identity]["checks"].get(key) == "different"
                    for key in ("source", "target", "endpoints", "direction", "connectionType")) for identity in observed)
                local[name]["unresolvedChecks"] = sum("unresolved" in annotations[identity]["checks"].values() for identity in observed)
            if name not in ("children", "connections"):
                continue
            if unresolved_ref:
                item["hints"].append({"code": name + ".unresolved_reference", "referenceIds": unresolved_ref})
            if unresolved_sub:
                item["hints"].append({"code": name + ".unresolved_submission", "submissionIds": unresolved_sub})
            if other_targets:
                item["hints"].append({"code": name + ".mapped_from_other_target",
                    "submissionIds": other_targets, "referenceIds": [reverse[identity] for identity in other_targets],
                    "status": "provisional"})
            elsewhere = sorted(recognized - at_target)
            if elsewhere:
                item["hints"].append({"code": name + ".outside_target", "referenceIds": elsewhere,
                                      "status": "unresolved"})
        if local:
            item["local"] = local
        if is_parent:
            expected_relations = [row for row in containment_relations if row["referenceParentId"] == ref]
            local["containmentRelations"] = {"expected": len(ref_direct) if ref is not None else None,
                "observed": len(sub_direct), "recognized": sum(row["status"] == "satisfied" for row in expected_relations),
                "deviating": sum(row["status"] == "violated" for row in expected_relations),
                "unresolvedReference": sum(row["status"] == "unresolved" for row in expected_relations)
                    + max(0, len(ref_direct) - len(expected_relations)) if ref is not None else None,
                "evaluationStatus": "provisional" if ref is not None and len(expected_relations) == len(ref_direct) else "not_evaluated"}
            roles = {edge["role"] for index, identity in ((reference, ref), (submission, sub))
                     for edge in index.children.get(identity, ())}
            local["childRoles"] = [{"role": role,
                "expected": sum(edge["role"] == role for edge in reference.children.get(ref, ())) if ref is not None else None,
                "observed": sum(edge["role"] == role for edge in submission.children.get(sub, ())),
                "recognized": sum(row["status"] == "satisfied" and row["referenceRole"] == role for row in expected_relations),
                "deviating": sum(row["status"] == "violated" and row["referenceRole"] == role for row in expected_relations),
                "unresolvedReference": (sum(edge["role"] == role for edge in reference.children.get(ref, ()))
                    - sum(row["status"] != "unresolved" and row["referenceRole"] == role for row in expected_relations)) if ref is not None else None}
                for role in sorted(roles, key=lambda role: role or "")]

    model_id = next(model["source"]["modelId"] for model in bundle["models"]
                    if model["source"]["key"] == "submission")
    model_target = {"side": "submission", "id": model_id, "kind": "model"}
    limitations = [{"code": code} for field, code in (
        ("provisionalOwnerEvidence", "input.owner_evidence_unavailable"),
        ("provisionalContainmentEvidence", "input.containment_evidence_unavailable"),
        ("provisionalConnectionStructure", "input.connection_structure_unavailable")) if field not in comparison]
    if not (any(language["data"].get("evaluation", {}).get("elementCategories") for language in bundle["languages"])
            or bundle.get("comparisonConfig", {}).get("graphMatching", {}).get("elementCategories")):
        limitations.append({"code": "input.category_metadata_unavailable"})

    def display_target(identity):
        node = reference.nodes[identity]
        if identity in contexts:
            return annotations[contexts[identity]]["target"]
        if node["kind"] == "connection":
            for role in ("source", "target"):
                endpoint = reference.endpoints.get(identity, {}).get(role)
                if endpoint in mappings:
                    sub = mappings[endpoint]["studentId"]
                    return annotations[sub]["target"]
        pending, visited = {identity}, {identity}
        while pending:
            parents = {edge["target"] for current in pending for edge in reference.parents.get(current, ())
                       if edge["target"] not in visited}
            options = {mappings[parent]["studentId"] if parent in mappings else contexts[parent]
                       for parent in parents if parent in mappings or parent in contexts}
            if len(options) == 1:
                return annotations[next(iter(options))]["target"]
            if len(options) > 1:
                break
            visited.update(parents)
            pending = parents
        return model_target

    reference_hints = []
    for identity in sorted(set(reference.nodes) - set(mappings)):
        evaluated = reference.nodes[identity]["kind"] in ("modelElement", "connection")
        hint = {"target": display_target(identity), "code": "reference.unresolved" if evaluated else "reference.not_evaluated",
                "referenceId": identity, "kind": reference.nodes[identity]["kind"]}
        if reference.nodes[identity]["type"] is not None:
            hint["referenceType"] = reference.nodes[identity]["type"]
        if reference.nodes[identity].get("label"):
            hint["label"] = reference.nodes[identity]["label"]
        if identity in ambiguous_references:
            hint["reason"] = "ambiguous_candidates"
        reference_hints.append(hint)

    summary = category_summary(bundle, reference.nodes.values(), mappings, comparison)
    has_facts = project_facts(comparison, annotations, reference_hints, connection_groups)
    for item in annotations.values():
        item["hints"] = structure_hints(item["hints"], [item["target"]], indices)
        if not has_facts:
            item["status"] = ("different" if any(item["checks"].get(key) in ("different", "violated")
                            for key in ("owner", "containment", "source", "target", "endpoints", "direction", "connectionType")) else
                          "ambiguous" if any(hint["status"] == "ambiguous" for hint in item["hints"]) else
                          "unresolved" if "unresolved" in item["checks"].values() or item["match"]["status"] == "unresolved"
                              or any(hint["status"] == "unresolved" for hint in item["hints"]) else
                          item["match"]["status"])
        for field in ("relationIds", "groupIds"):
            if field in item:
                item[field] = sorted(set(item[field]))
    for group in connection_groups:
        group["status"] = ("different" if group["hints"] else "not_evaluated"
                           if "not_evaluated" in group["checks"].values() else "provisional")
        targets = [{"side": side, "id": identity, "kind": "connection"}
                   for side, identities in (("reference", group["referenceIds"]), ("submission", group["submissionIds"]))
                   for identity in identities]
        group["hints"] = structure_hints(group["hints"], targets, indices)
    for relation in containment_relations:
        relation["status"] = canonical_status(relation["status"])
        relation["scope"] = "relation"
    reference_hints = structure_hints(reference_hints, [], indices)
    for hint in reference_hints:
        hint["targets"].append(hint["target"])
    return {"schema": "analysis-feedback/v1", "contractVersion": "1.2" if has_facts else "1.1",
            "producer": {"service": "analytical-feedback", "version": "1.2.0"}, "evaluationId": bundle["evaluationId"],
            "pair": comparison["pair"], "comparisonHash": comparison["comparisonHash"],
            "status": "provisional", "assessmentAvailable": False, "summary": summary,
            "structuralContainers": {"referenceCount": sum(category_for(bundle, node) is None for node in reference.nodes.values()),
                "submissionCount": sum(category_for(bundle, node) is None for node in submission.nodes.values()),
                "contextCount": len(contexts), "evaluationStatus": "not_evaluated"},
            "connectionGroups": sorted(connection_groups, key=lambda row: row["id"]),
            "containmentRelations": sorted(containment_relations, key=lambda row: row["id"]),
            "limitations": structure_hints(limitations, [model_target], indices),
            "annotations": [annotations[key] for key in sorted(annotations)], "referenceHints": reference_hints}
