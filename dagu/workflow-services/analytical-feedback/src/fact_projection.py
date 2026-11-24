"""Compact projection of matcher facts; no matching or property decisions."""

from collections import defaultdict

from analysis_contract import compact_fact, compact_identity, content_hash, label_hints, recognition_summary


def build_evidence_report(bundle, indices, comparison):
    reference, submission = indices["reference"], indices["student"]
    mapping = {row["referenceId"]: row for field in ("provisionalElements", "provisionalConnections")
               for row in comparison["mapping"][field]}
    reverse = {row["studentId"]: ref for ref, row in mapping.items()}
    by_reference, by_submission, grouped = defaultdict(list), defaultdict(list), defaultdict(list)
    for fact in comparison["propertyFacts"]["items"]:
        for identity in fact["referenceIds"]:
            by_reference[identity].append(fact)
        for identity in fact["submissionIds"]:
            by_submission[identity].append(fact)
        if fact["code"].startswith("connection_group."):
            grouped[tuple(fact["referenceIds"]), tuple(fact["submissionIds"])].append(fact)

    def identity_fact(facts):
        return next((fact for fact in facts if fact["code"].startswith("identity.")), None)

    def property_facts(facts):
        return [fact for fact in facts if not fact["code"].startswith(("identity.", "connection_group."))]

    def observations(facts):
        presence = next((fact for fact in facts if fact["code"].startswith("counterpart.")), {})
        evidence = presence.get("evidence", {})
        return evidence.get("referenceObservation") or {}, evidence.get("submissionObservation") or {}

    annotations = {}
    for sub, node in sorted(submission.nodes.items()):
        ref = reverse.get(sub)
        row = mapping.get(ref)
        source = property_facts(by_submission[sub])
        left, right = observations(source)
        item = {"target": {"side": "submission", "id": sub, "kind": node["kind"]},
                "facts": [compact_fact(fact) for fact in source], "hints": []}
        identity = compact_identity(identity_fact(by_submission[sub]))
        if identity:
            item["identity"] = identity
        if row:
            item.update(referenceId=ref, mappingReason=row["reason"])
            if row.get("dependsOn"):
                item["dependencies"] = row["dependsOn"]
        if right:
            item["owner"] = {"referenceOwnerId": left.get("ownerId"), "submissionOwnerId": right.get("ownerId")}
            item["containment"] = {"referenceParents": left.get("parents") if row else None, "submissionParents": right.get("parents", [])}
        if "connection" in right:
            item["connection"] = {"reference": left.get("connection"), "submission": right["connection"]}
        seen = set()
        for fact in source:
            finding = fact["evidence"].get("findingId", fact["id"])
            if fact["status"] not in ("violated", "unresolved") or finding in seen:
                continue
            seen.add(finding)
            item["hints"].append({"code": "fact." + fact["status"], "factId": fact["id"],
                "scope": "relation" if fact["code"].startswith(("owner.", "containment.", "connection.")) else "element",
                "targets": [dict(target) for target in fact["targets"]], **({"findingId": finding} if "findingId" in fact["evidence"] else {})})
        annotations[sub] = item

    model_id = next(item["source"]["modelId"] for item in bundle["models"] if item["source"]["key"] == "submission")
    model_target = {"side": "submission", "id": model_id, "kind": "model"}
    hints = []
    for ref, node in sorted(reference.nodes.items()):
        if ref in mapping:
            continue
        source = property_facts(by_reference[ref])
        left, _ = observations(source)
        connection = left.get("connection", {})
        options = [parent["parentId"] for parent in left.get("parents", [])] + [left.get("ownerId"), connection.get("sourceId"), connection.get("targetId")]
        sub = next((mapping[identity]["studentId"] for identity in options if identity in mapping), None)
        target = annotations[sub]["target"] if sub is not None else model_target
        hint = {"code": "reference.missing" if any(fact["code"] == "counterpart.missing" for fact in source) else
                        "reference.unresolved" if node["kind"] in ("modelElement", "connection") else "reference.not_evaluated",
                "target": target, "scope": "element", "targets": [target, {"side": "reference", "id": ref, "kind": node["kind"]}],
                "referenceId": ref, "kind": node["kind"], "facts": [compact_fact(fact) for fact in source]}
        identity = compact_identity(identity_fact(by_reference[ref]))
        if identity:
            hint["identity"] = identity
        if node.get("label"):
            hint["label"] = node["label"]
        hints.append(hint)

    groups = []
    for (refs, subs), facts in sorted(grouped.items()):
        group = {"id": content_hash({"referenceIds": refs, "submissionIds": subs}),
                 "referenceIds": list(refs), "submissionIds": list(subs),
                 "referenceEndpointIds": facts[0]["evidence"]["referenceEndpointIds"],
                 "submissionEndpointIds": facts[0]["evidence"]["submissionEndpointIds"],
                 "facts": [compact_fact(fact) for fact in facts]}
        groups.append(group)
        for sub in subs:
            annotations[sub].setdefault("groupIds", []).append(group["id"])
    # Comparisons before matcher 2.12.0 have no hints; their analyses stay without the field.
    extra = {"labelHints": label_hints(bundle, indices, comparison)} if "hints" in comparison else {}
    return {"schema": "analysis-feedback/v3", "producer": {"service": "analytical-feedback", "version": "2.4.0"},
            "evaluationId": bundle["evaluationId"], "pair": comparison["pair"], "comparisonHash": comparison["comparisonHash"],
            "status": "provisional", "assessmentAvailable": False, "recognition": recognition_summary(bundle, indices, comparison),
            "annotations": list(annotations.values()), "referenceHints": hints, "connectionGroups": groups, **extra,
            "limitations": [],
            "structuralContainers": {"referenceCount": sum(node["kind"] == "structuralElement" for node in reference.nodes.values()),
                                     "submissionCount": sum(node["kind"] == "structuralElement" for node in submission.nodes.values())}}
