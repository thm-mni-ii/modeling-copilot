"""Project matcher facts without making matching or property decisions."""

from copy import deepcopy

from analysis_contract import category_for, category_summary, content_hash, require, structure_hints


CHECK_NAMES = {
    "identity": "identity",
    "label": "label", "type": "type", "owner": "owner", "containment": "containment",
    "counterpart": "counterpart", "children": "children", "direct_children": "directChildren",
    "connections": "connections", "incoming": "incoming", "outgoing": "outgoing", "undirected": "undirected",
}


def project_facts(comparison, annotations, reference_hints, groups):
    source = comparison.get("propertyFacts")
    if source is None:
        return False
    require(source.get("version") in ("1.0", "1.1") and isinstance(source.get("items"), list), "unsupported matcher facts")
    facts = source["items"]

    def hint(item):
        prefix = "fact.group_" if item["code"].startswith("connection_group.") else "fact."
        return {"code": prefix + item["status"], "factCode": item["code"],
                "basis": item["evidence"]["basis"], "reason": item["evidence"]["reason"],
                "referenceIds": item["referenceIds"], "submissionIds": item["submissionIds"],
                **({"findingId": item["evidence"]["findingId"]} if "findingId" in item["evidence"] else {}),
                **({"targets": item["targets"]} if "targets" in item else {})}

    for sub, annotation in annotations.items():
        selected = deepcopy([item for item in facts if sub in item["submissionIds"]])
        annotation["facts"] = selected
        identity = next((item for item in selected if item["code"].startswith("identity.")), None)
        if identity:
            annotation["identity"] = {"status": identity["evidence"]["identityStatus"],
                                      "criteria": deepcopy(identity["evidence"]["criteria"]),
                                      "supportingCandidateCount": identity["evidence"]["supportingCandidateCount"]}
        checks = {}
        for item in selected:
            prefix, _, dimension = item["code"].partition(".")
            name = CHECK_NAMES.get(prefix)
            if prefix == "connection":
                name = dimension
            if name is not None:
                # Multiple facts for a dimension (e.g. outgoing absence and
                # neighborhood closure) keep the more restrictive status.
                previous = checks.get(name)
                priority = {"not_applicable": 0, "satisfied": 1, "not_evaluated": 2, "unresolved": 3, "violated": 4}
                if previous is None or priority[item["status"]] > priority[previous]:
                    checks[name] = item["status"]
        annotation["checks"] = checks or {"counterpart": "not_evaluated"}
        annotation["hints"] = [item for item in annotation["hints"] if item["code"].startswith("identity.")]
        findings = set()
        for item in selected:
            finding = item["evidence"].get("findingId", item.get("id"))
            if item["status"] in ("violated", "unresolved") and (finding is None or finding not in findings):
                annotation["hints"].append(hint(item))
                if finding:
                    findings.add(finding)
        if "owner" in annotation:
            annotation["owner"]["status"] = checks.get("owner", "not_evaluated")
        for item in selected:
            if item["code"].endswith(".complete"):
                name = CHECK_NAMES.get(item["code"].split(".")[0])
                local = annotation.get("local", {}).get(name)
                if local is not None:
                    local["evaluationStatus"] = item["status"]
                    local["complete"] = item["status"] == "satisfied"
        states = {item["status"] for item in selected}
        individual_states = {item["status"] for item in selected if not item["code"].startswith("connection_group.")}
        annotation["consistency"] = (
            "different" if "violated" in individual_states else
            "fully_consistent" if selected and states <= {"satisfied", "not_applicable"}
                and "satisfied" in states and annotation["match"]["status"] == "provisional" else
            "partial" if "satisfied" in states else "unresolved" if "unresolved" in states else "not_evaluated")
        annotation["status"] = ("different" if "violated" in individual_states else
                                "unresolved" if "unresolved" in states or "violated" in states else annotation["match"]["status"])

    for reference_hint in reference_hints:
        selected = deepcopy([item for item in facts if reference_hint["referenceId"] in item["referenceIds"]])
        reference_hint["facts"] = selected
        if any(item["code"] == "counterpart.missing" for item in selected):
            reference_hint["code"] = "reference.missing"
            reference_hint.pop("reason", None)
    for group in groups:
        group["facts"] = deepcopy([item for item in facts if item["code"].startswith("connection_group.")
                                   and item["referenceIds"] == group["referenceIds"]
                                   and item["submissionIds"] == group["submissionIds"]])
    return True


def build_evidence_report(bundle, indices, comparison):
    """Project the 1.1 matcher facts; never re-run a property or relation check."""
    reference, submission = indices["reference"], indices["student"]
    mapping = {row["referenceId"]: row for field in ("provisionalElements", "provisionalConnections")
               for row in comparison["mapping"][field]}
    reverse = {row["studentId"]: ref for ref, row in mapping.items()}
    source = comparison["propertyFacts"]["items"]
    annotations = {}
    for sub, node in sorted(submission.nodes.items()):
        ref = reverse.get(sub)
        row = mapping.get(ref)
        presence = next((item for item in source if item["code"].startswith("counterpart.") and sub in item["submissionIds"]), {})
        observations = presence.get("evidence", {})
        left, right = observations.get("referenceObservation") or {}, observations.get("submissionObservation") or {}
        annotation = {"target": {"side": "submission", "id": sub, "kind": node["kind"]},
                      "category": category_for(bundle, node), "checks": {}, "hints": [],
                      "match": {"status": "provisional" if row else "unresolved" if node["kind"] in ("modelElement", "connection") else "not_evaluated"},
                      "owner": {"referenceOwnerId": left.get("ownerId"), "submissionOwnerId": right.get("ownerId"), "status": "not_evaluated"},
                      "containment": {"referenceParents": left.get("parents") if row else None, "submissionParents": right.get("parents", [])}}
        if row:
            annotation["referenceId"] = ref
            annotation["match"]["reason"] = row["reason"]
            if row.get("dependsOn"):
                annotation["match"]["dependsOn"] = [{"referenceId": dep["referenceId"], "submissionId": dep["studentId"]} for dep in row["dependsOn"]]
        if "connection" in right:
            annotation["connection"] = {"reference": left.get("connection"), "submission": right["connection"]}
        annotations[sub] = annotation
    model_id = next(item["source"]["modelId"] for item in bundle["models"] if item["source"]["key"] == "submission")
    model_target = {"side": "submission", "id": model_id, "kind": "model"}
    hints = []
    for ref, node in sorted(reference.nodes.items()):
        if ref in mapping:
            continue
        presence = next((item for item in source if item["code"].startswith("counterpart.") and ref in item["referenceIds"]), {})
        observation = presence.get("evidence", {}).get("referenceObservation") or {}
        parents = [item["parentId"] for item in observation.get("parents", [])]
        connection = observation.get("connection", {})
        display_options = parents + [observation.get("ownerId"), connection.get("sourceId"), connection.get("targetId")]
        sub = next((mapping[identity]["studentId"] for identity in display_options if identity in mapping), None)
        target = annotations[sub]["target"] if sub is not None else model_target
        hints.append({"code": "reference.unresolved" if node["kind"] in ("modelElement", "connection") else "reference.not_evaluated",
                      "target": target, "referenceId": ref, "kind": node["kind"],
                      **({"label": node["label"]} if node.get("label") else {}),
                      **({"referenceType": node["type"]} if node["type"] is not None else {})})
    groups = []
    for row in comparison.get("provisionalConnectionStructure", {}).get("byEndpoints", []):
        refs, subs = sorted(item["id"] for item in row["referenceConnections"]), sorted(item["id"] for item in row["studentConnections"])
        groups.append({"id": content_hash({"referenceIds": refs, "submissionIds": subs}), "referenceIds": refs, "submissionIds": subs,
                       "referenceEndpointIds": row["referenceEndpointIds"], "submissionEndpointIds": row["studentEndpointIds"],
                       "referenceOnlyCount": row["referenceOnlyCount"], "submissionOnlyCount": row["studentOnlyCount"],
                       "checks": {"direction": row["directionStatus"], "configuration": row["configurationStatus"], "connectionType": row["typeStatus"]}, "hints": []})
    project_facts(comparison, annotations, hints, groups)
    for item in annotations.values():
        item["hints"] = structure_hints(item["hints"], [item["target"]], indices)
    for group in groups:
        group["status"] = "different" if any(item["status"] == "violated" for item in group["facts"]) else "not_evaluated" if any(item["status"] == "not_evaluated" for item in group["facts"]) else "provisional"
        group["hints"] = structure_hints([{"code": "fact.group_violated", "factCode": item["code"]} for item in group["facts"] if item["status"] == "violated"],
                                         [{"side": side, "id": identity, "kind": "connection"} for side, ids in (("reference", group["referenceIds"]), ("submission", group["submissionIds"])) for identity in ids], indices)
    hints = structure_hints(hints, [], indices)
    for hint in hints:
        if hint["target"] not in hint["targets"]:
            hint["targets"].append(hint["target"])
    category_metadata = any(language["data"].get("evaluation", {}).get("elementCategories") for language in bundle["languages"]) or bundle.get("comparisonConfig", {}).get("graphMatching", {}).get("elementCategories")
    limitations = [] if category_metadata else structure_hints([{"code": "input.category_metadata_unavailable"}], [model_target], indices)
    return {"schema": "analysis-feedback/v1", "contractVersion": "1.3", "producer": {"service": "analytical-feedback", "version": "1.3.0"},
            "evaluationId": bundle["evaluationId"], "pair": comparison["pair"], "comparisonHash": comparison["comparisonHash"],
            "status": "provisional", "assessmentAvailable": False, "summary": category_summary(bundle, reference.nodes.values(), mapping, comparison),
            "annotations": list(annotations.values()), "referenceHints": hints, "connectionGroups": groups, "containmentRelations": [], "limitations": limitations,
            "structuralContainers": {"referenceCount": sum(category_for(bundle, node) is None for node in reference.nodes.values()),
                                     "submissionCount": sum(category_for(bundle, node) is None for node in submission.nodes.values()),
                                     "contextCount": 0, "evaluationStatus": "not_evaluated"}}
