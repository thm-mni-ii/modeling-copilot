"""Summarize existing matching results for individual submission objects."""

from collections import defaultdict
import unicodedata

from analysis_contract import require


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


def _connections(index):
    result = defaultdict(set)
    for connection, endpoints in index.endpoints.items():
        for endpoint in endpoints.values():
            if endpoint is not None:
                result[endpoint].add(connection)
    return result


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
    for identity, node in submission.nodes.items():
        ref = reverse.get(identity)
        row = mappings.get(ref)
        target = {"side": "submission", "id": identity, "kind": node["kind"]}
        match = {"status": "provisional" if row else
                 "unresolved" if node["kind"] in ("modelElement", "connection") else "not_evaluated"}
        item = {"target": target, "match": match, "checks": {}, "hints": []}
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

    relation_statuses = defaultdict(list)
    for row in comparison.get("provisionalContainmentEvidence", []):
        for prefix in ("Source", "Target"):
            sub = row["student" + prefix + "Id"]
            if sub is not None and sub in annotations:
                relation_statuses[sub].append(row["status"])
        if row["status"] == "violated":
            sub = row["studentSourceId"] or row["studentTargetId"]
            if sub is not None and sub in annotations:
                annotations[sub]["hints"].append({"code": "containment.violated",
                    "referenceId": row["referenceSourceId"], "referenceParentId": row["referenceTargetId"],
                    "submissionParentIds": row["studentParentIds"], "basis": row["decisionBasis"]})
    for sub, statuses in relation_statuses.items():
        annotations[sub]["checks"]["containment"] = ("violated" if "violated" in statuses else
                                                       "unresolved" if "unresolved" in statuses else "satisfied")

    for sub, item in annotations.items():
        if submission.nodes[sub]["kind"] != "connection":
            continue
        ref = reverse.get(sub)
        reference_endpoints = reference.endpoints.get(ref, {})
        student_endpoints = submission.endpoints.get(sub, {})
        if (ref is None or any(reference_endpoints.get(role) not in mappings or not student_endpoints.get(role)
                               for role in ("source", "target"))):
            item["checks"]["endpoints"] = "unresolved"
        else:
            mapped = {mappings[reference_endpoints[role]]["studentId"] for role in ("source", "target")}
            observed = {student_endpoints[role] for role in ("source", "target")}
            item["checks"]["endpoints"] = "equal" if mapped == observed else "different"
            if mapped != observed:
                item["hints"].append({"code": "connection.endpoints_different", "referenceId": ref})

    for row in comparison.get("provisionalConnectionStructure", {}).get("byEndpoints", []):
        refs = [item["id"] for item in row["referenceConnections"]]
        subs = [item["id"] for item in row["studentConnections"]]
        for sub in subs:
            require(sub in annotations, "connection group refers to unknown submission object")
            annotations[sub]["checks"]["direction"] = row["directionStatus"]
            annotations[sub]["checks"]["connectionType"] = row["typeStatus"]
            annotations[sub]["checks"]["connectionScope"] = "endpoint_group"
        dimensions = [name for name, key in (("configuration", "configurationStatus"),
                                               ("direction", "directionStatus"), ("type", "typeStatus"))
                      if row[key] == "different"]
        if dimensions or row["referenceOnlyCount"] or row["studentOnlyCount"]:
            for sub in subs:
                annotations[sub]["hints"].append({"code": "connection.group_difference", "dimensions": dimensions,
                    "referenceIds": refs, "submissionIds": subs,
                    "referenceOnlyCount": row["referenceOnlyCount"], "submissionOnlyCount": row["studentOnlyCount"]})

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
    for sub, item in annotations.items():
        ref = reverse.get(sub, reverse_contexts.get(sub))
        sub_children = _children(submission, sub)
        ref_children = _children(reference, ref) if ref is not None else set()
        sub_connections = adjacent["student"].get(sub, set())
        ref_connections = adjacent["reference"].get(ref, set()) if ref is not None else set()
        is_parent = (submission.nodes[sub]["kind"] == "structuralElement" or bool(submission.children.get(sub))
                     or ref is not None and bool(reference.children.get(ref)))
        local = {}
        for name, expected, observed in (("children", ref_children, sub_children),
                                         ("connections", ref_connections, sub_connections)):
            if not expected and not observed and not is_parent:
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

    model_id = next(model["source"]["modelId"] for model in bundle["models"]
                    if model["source"]["key"] == "submission")

    def display_target(identity):
        node = reference.nodes[identity]
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
        return {"side": "submission", "id": model_id, "kind": "model"}

    reference_hints = []
    for field in ("unresolvedReferenceIds", "unresolvedReferenceConnectionIds"):
        for identity in comparison[field]:
            require(identity in reference.nodes and identity not in mappings, "invalid unresolved reference")
            hint = {"target": display_target(identity), "code": "reference.unresolved",
                    "referenceId": identity, "kind": reference.nodes[identity]["kind"]}
            if reference.nodes[identity]["type"] is not None:
                hint["referenceType"] = reference.nodes[identity]["type"]
            if reference.nodes[identity].get("label"):
                hint["label"] = reference.nodes[identity]["label"]
            if identity in ambiguous_references:
                hint["reason"] = "ambiguous_candidates"
            reference_hints.append(hint)

    summary = {}
    for row in compact["categories"]:
        summary[row["category"]] = {"recognized": row["provisionalRecognizedCount"],
                                    "expected": row["referenceCount"], "percent": row["percentage"],
                                    "evaluationStatus": row["evaluationStatus"]}
    return {"schema": "analysis-feedback/v1", "evaluationId": bundle["evaluationId"],
            "pair": comparison["pair"], "comparisonHash": comparison["comparisonHash"],
            "status": "provisional", "assessmentAvailable": False, "summary": summary,
            "annotations": list(annotations.values()), "referenceHints": reference_hints}
