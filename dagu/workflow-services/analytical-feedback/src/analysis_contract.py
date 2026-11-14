"""Validate the compact analysis and its comparison identity."""

import hashlib
import json


SCHEMA = "analysis-feedback/v1"
CATEGORIES = ("nodes", "attributes", "connections", "other")
STATUSES = ("provisional", "different", "ambiguous", "unresolved", "not_evaluated", "not_applicable")
KINDS = ("modelElement", "structuralElement", "connection", "connectionLabel", None)
HINT_DEFINITIONS = {
    "fact.violated": ("element", "different"), "fact.unresolved": ("element", "unresolved"),
    "fact.group_violated": ("group", "different"), "fact.group_unresolved": ("group", "unresolved"),
    "reference.missing": ("element", "different"),
    "identity.unresolved": ("element", "unresolved"), "identity.ambiguous": ("element", "ambiguous"),
    "label.different": ("element", "different"), "type.compatible_difference": ("element", "provisional"),
    "owner.violated": ("relation", "different"), "owner.different": ("relation", "different"),
    "owner.unresolved": ("relation", "unresolved"), "containment.violated": ("relation", "different"),
    "connection.endpoints_different": ("relation", "different"),
    "connection.source_different": ("relation", "different"), "connection.target_different": ("relation", "different"),
    "connection.direction_different": ("relation", "different"), "connection.connectionType_different": ("relation", "different"),
    "connection.group_difference": ("group", "different"),
    "reference.unresolved": ("element", "unresolved"), "reference.not_evaluated": ("element", "not_evaluated"),
    "input.category_metadata_unavailable": ("model", "not_evaluated"),
    "input.owner_evidence_unavailable": ("model", "not_evaluated"),
    "input.containment_evidence_unavailable": ("model", "not_evaluated"),
    "input.connection_structure_unavailable": ("model", "not_evaluated"),
}
for _prefix in ("children", "connections"):
    for _suffix in ("unresolved_reference", "unresolved_submission", "outside_target", "mapped_from_other_target"):
        HINT_DEFINITIONS[f"{_prefix}.{_suffix}"] = ("group", "unresolved")


def canonical_status(status):
    return {"satisfied": "provisional", "equal": "provisional", "exact": "provisional", "same_type": "provisional",
            "compatible_type_difference": "provisional", "violated": "different"}.get(status, status)


def structure_hints(hints, targets, indices):
    """Add a uniform contract while retaining the existing flat hint parameters."""
    result = []
    for original in hints:
        hint = dict(original)
        code = hint["code"]
        require(code in HINT_DEFINITIONS, "unknown analytical hint code")
        scope, status = HINT_DEFINITIONS[code]
        if hint.get("reason") == "ambiguous_candidates":
            status = "ambiguous"
        parameters = {key: value for key, value in hint.items() if key not in ("code", "target", "status", "facts")}
        addressed = {(target["side"], target["id"]): target for target in targets}
        for side in ("reference", "submission"):
            index = indices["student" if side == "submission" else side]
            for key, value in parameters.items():
                if not key.startswith(side) or value is None:
                    continue
                values = value if key.endswith("Ids") else [value] if key.endswith("Id") else []
                for identity in values:
                    require(identity in index.nodes, "hint refers to unknown original ID")
                    addressed[(side, identity)] = {"side": side, "id": identity, "kind": index.nodes[identity]["kind"]}
        hint.update({"status": status, "scope": scope, "parameters": parameters,
                     "targets": [addressed[key] for key in sorted(addressed)]})
        result.append(hint)
    return sorted(result, key=lambda hint: (hint["code"], content_hash(hint)))


def category_for(bundle, node):
    """Classify by frozen declarations, never by native type names or nesting."""
    if node["kind"] == "structuralElement" or node.get("comparisonRole") == "structural":
        return None
    if node["kind"] == "connection":
        return "connections"
    if node["kind"] != "modelElement" or node.get("languageResolution") != "resolved":
        return "other"
    language = node.get("language") or {}
    for definition in bundle["languages"]:
        if all(definition[key] == language.get(key) for key in ("languageId", "versionId")):
            declared = definition["data"].get("evaluation", {}).get("elementCategories", {})
            if node["type"] in declared:
                category = declared[node["type"]]
                require(category in CATEGORIES, "invalid declared element category")
                return category
    # Older snapshots froze these same declarations in comparisonConfig only.
    for row in bundle.get("comparisonConfig", {}).get("graphMatching", {}).get("elementCategories", []):
        if row["type"] == node["type"] and all(row[key] == language.get(key) for key in ("languageId", "versionId")):
            require(row["category"] in CATEGORIES, "invalid frozen element category")
            return row["category"]
    return "other"


def category_summary(bundle, nodes, mapped_reference_ids, comparison=None):
    nodes = list(nodes)
    connection_rows = (comparison or {}).get("metrics", {}).get("provisionalRecognition", {}).get("categoryTypes", [])
    summary = {}
    for category in CATEGORIES:
        selected = [node for node in nodes if category_for(bundle, node) == category]
        expected = len(selected)
        recognized = sum(node["id"] in mapped_reference_ids for node in selected)
        evaluable = sum(node["kind"] == "modelElement"
                        and node.get("comparisonRole") == "semantic"
                        and node.get("languageResolution") == "resolved" for node in selected)
        connection_types = {(content_hash(node.get("language")), node["type"]) for node in selected if node["kind"] == "connection"}
        if connection_rows:
            evaluable += sum(row["evaluableReferenceCount"] for row in connection_rows if row["category"] == "connections"
                             and (content_hash(row["language"]), row["type"]) in connection_types)
        else:
            # A proposal proves this connection was considered; otherwise the
            # matcher's missing evaluability statement must not be reconstructed.
            evaluable += sum(node["kind"] == "connection" and node["id"] in mapped_reference_ids for node in selected)
        summary[category] = {"recognized": recognized, "expected": expected,
            "percent": 100 * recognized / expected if expected and evaluable else None,
            "evaluationStatus": "not_applicable" if not expected else "not_evaluated" if not evaluable else
                "partial" if evaluable < expected or category == "other" else "provisional"}
    return summary


def content_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analysis_key(report):
    return content_hash({key: value for key, value in report.items() if key not in ("analysisKey", "analysisHash")})


def analysis_path(report):
    return f"analysis/{report['pair']['referenceKey']}/{report['analysisKey']}.json"


def validate_analysis(report, store=None):
    require(isinstance(report, dict) and report.get("schema") == SCHEMA, "expected analysis-feedback/v1")
    require(report.get("status") == "provisional" and report.get("assessmentAvailable") is False,
            "analysis must remain provisional")
    require(report.get("contractVersion") in (None, "1.1", "1.2"), "unsupported analysis contract version")
    structured = report.get("contractVersion") in ("1.1", "1.2")
    factual = report.get("contractVersion") == "1.2"
    require(report.get("analysisKey") == analysis_key(report), "analysis key mismatch")
    require(report.get("analysisHash") == content_hash({key: value for key, value in report.items()
                                                        if key != "analysisHash"}), "analysis hash mismatch")
    annotations = report.get("annotations")
    hints = report.get("referenceHints")
    require(isinstance(annotations, list) and isinstance(hints, list), "invalid analysis annotations or hints")
    seen = set()
    for item in annotations:
        target = item["target"]
        identity = target.get("id")
        require(target.get("side") == "submission" and isinstance(identity, str) and identity and identity not in seen,
                "analysis targets must have unique submission IDs")
        seen.add(identity)
        match = item["match"]
        require(match["status"] in ("provisional", "unresolved", "not_evaluated"), "invalid matching status")
        require((match["status"] == "provisional") == ("referenceId" in item),
                "provisional matching must identify its reference")
        require(isinstance(item["checks"], dict) and isinstance(item["hints"], list),
                "invalid annotation checks or hints")
        require(target.get("kind") in KINDS, "invalid annotation object kind")
        if structured:
            require(item.get("status") in STATUSES and item.get("category") in (*CATEGORIES, None),
                    "invalid annotation status or category")
            require(all(key in ("label", "type", "owner", "containment", "source", "target", "endpoints", "direction", "connectionType",
                               "counterpart", "children", "directChildren", "connections", "incoming", "outgoing", "undirected")
                        and canonical_status(value) in STATUSES for key, value in item["checks"].items()), "invalid check status")
    require(set(report["summary"]) == {"nodes", "attributes", "connections", "other"},
            "invalid recognition categories")
    for row in report["summary"].values():
        require(all(type(row.get(key)) is int and row[key] >= 0 for key in ("recognized", "expected"))
                and row["recognized"] <= row["expected"]
                and row.get("evaluationStatus") in ("provisional", "partial", "not_evaluated", "not_applicable"),
                "invalid category counts or status")
        percent = row.get("percent")
        require(percent is None or type(percent) in (int, float) and row["expected"] > 0
                and abs(percent - 100 * row["recognized"] / row["expected"]) < 0.000001, "invalid category percentage")
        require(row["evaluationStatus"] not in ("not_evaluated", "not_applicable") or percent is None,
                "unevaluated category has percentage")
    if structured:
        def validate_hint(hint):
            require(hint.get("code") in HINT_DEFINITIONS and hint.get("scope") == HINT_DEFINITIONS[hint["code"]][0]
                    and hint.get("status") in STATUSES and isinstance(hint.get("parameters"), dict)
                    and isinstance(hint.get("targets"), list), "invalid structured hint")
            require(hint["parameters"] == {key: value for key, value in hint.items()
                    if key not in ("code", "target", "status", "scope", "parameters", "targets", "facts")}, "hint parameters differ from legacy fields")

        for item in annotations:
            for hint in item["hints"]:
                validate_hint(hint)
        for hint in hints:
            validate_hint(hint)
        for hint in report.get("limitations", []):
            validate_hint(hint)
        groups = report.get("connectionGroups")
        relations = report.get("containmentRelations")
        require(isinstance(groups, list) and isinstance(relations, list), "missing structured relations")
        for group in groups:
            require(group.get("status") in STATUSES, "invalid group status")
            for hint in group["hints"]:
                validate_hint(hint)
        for relation in relations:
            require(relation.get("status") in STATUSES and relation.get("scope") == "relation"
                    and canonical_status(relation.get("roleStatus")) in STATUSES, "invalid containment status")
        group_ids, relation_ids = {row["id"] for row in groups}, {row["id"] for row in relations}
        require(len(group_ids) == len(groups) and len(relation_ids) == len(relations), "duplicate group or relation ID")
        for item in annotations:
            require(set(item.get("groupIds", ())) <= group_ids and set(item.get("relationIds", ())) <= relation_ids,
                    "unknown annotation group or relation")
    if factual:
        def validate_facts(items):
            require(isinstance(items, list), "missing projected facts")
            for item in items:
                require(isinstance(item, dict) and isinstance(item.get("code"), str)
                        and item.get("status") in ("satisfied", "violated", "unresolved", "not_evaluated", "not_applicable")
                        and all(isinstance(item.get(key), list) and all(isinstance(identity, str) for identity in item[key])
                                for key in ("referenceIds", "submissionIds"))
                        and isinstance(item.get("evidence"), dict)
                        and item["evidence"].get("basis") in ("direct_observation", "conditional_mapping", "independent_evidence")
                        and isinstance(item["evidence"].get("reason"), str), "invalid matcher fact")
        for item in annotations:
            validate_facts(item.get("facts"))
            require(item.get("consistency") in ("fully_consistent", "partial", "different", "unresolved", "not_evaluated"),
                    "invalid factual consistency")
            if item["consistency"] == "fully_consistent":
                require(item["match"]["status"] == "provisional" and item["facts"]
                        and all(fact["status"] in ("satisfied", "not_applicable") for fact in item["facts"])
                        and any(fact["status"] == "satisfied" for fact in item["facts"]), "unsupported full consistency")
        for hint in hints:
            validate_facts(hint.get("facts"))
        for group in report["connectionGroups"]:
            validate_facts(group.get("facts"))
    if store is not None:
        reference_key = report["pair"]["referenceKey"]
        student = store.read("graphs/submission.json")["result"]["graph"]
        reference = store.read(f"graphs/{reference_key}.json")["result"]["graph"]
        student_nodes = {node["id"]: node for node in student["nodes"]}
        reference_nodes = {node["id"]: node for node in reference["nodes"]}
        require(seen == set(student_nodes), "annotations must cover submission graph objects once")
        comparison = store.read(f"comparisons/{reference_key}.json")["result"]
        if factual:
            source = comparison.get("propertyFacts", {})
            require(source.get("version") == "1.0" and isinstance(source.get("items"), list), "missing matcher fact source")
            for fact in source["items"]:
                require(set(fact["referenceIds"]) <= set(reference_nodes)
                        and set(fact["submissionIds"]) <= set(student_nodes), "fact has unknown original ID")
            for item in annotations:
                require(item["facts"] == [fact for fact in source["items"] if item["target"]["id"] in fact["submissionIds"]],
                        "annotation facts differ from matcher")
            for hint in hints:
                require(hint["facts"] == [fact for fact in source["items"] if hint["referenceId"] in fact["referenceIds"]],
                        "reference facts differ from matcher")
        pairs = {row["studentId"]: row["referenceId"] for field in ("provisionalElements", "provisionalConnections")
                 for row in comparison["mapping"][field]}
        for item in annotations:
            identity = item["target"]["id"]
            require(item["target"]["kind"] == student_nodes[identity]["kind"]
                    and item.get("referenceId") == pairs.get(identity), "annotation does not match graph or mapping")
            for dependency in item["match"].get("dependsOn", []):
                require(pairs.get(dependency["submissionId"]) == dependency["referenceId"], "unknown mapping dependency")
        expected = set(comparison["unresolvedReferenceIds"]) | set(comparison["unresolvedReferenceConnectionIds"])
        if structured:
            expected = set(reference_nodes) - set(pairs.values())
            require(report["summary"] == category_summary(store.snapshot(), reference_nodes.values(), set(pairs.values()), comparison),
                    "category summary does not match frozen metadata and mapping")
        require(len(hints) == len(expected) and {hint["referenceId"] for hint in hints} == expected,
                "unresolved reference hints do not match comparison")
        model_id = next(model["source"]["modelId"] for model in store.snapshot()["models"]
                        if model["source"]["key"] == "submission")
        for hint in hints:
            target, identity = hint["target"], hint["referenceId"]
            require(target["side"] == "submission" and identity in reference_nodes
                    and hint["kind"] == reference_nodes[identity]["kind"]
                    and (target["id"] in student_nodes and target["kind"] == student_nodes[target["id"]]["kind"]
                         or target["kind"] == "model" and target["id"] == model_id),
                    "invalid unresolved reference display target")
        if structured:
            catalogs = {"reference": reference_nodes, "submission": student_nodes}

            def original(side, identity, kind=None):
                require(identity in catalogs[side] and (kind is None or catalogs[side][identity]["kind"] == kind),
                        "unknown original object reference")

            def hint_targets(hint):
                for target in hint["targets"]:
                    require(target.get("side") in catalogs and target.get("kind") in (*KINDS, "model"), "invalid hint target")
                    if target["kind"] == "model":
                        require(target["side"] == "submission" and target["id"] == model_id, "unknown model display target")
                    else:
                        original(target["side"], target["id"])
                        require(catalogs[target["side"]][target["id"]]["kind"] == target["kind"], "hint target kind mismatch")

            for item in annotations:
                require(item["category"] == category_for(store.snapshot(), student_nodes[item["target"]["id"]]), "annotation category mismatch")
                if "context" in item:
                    original("reference", item["context"]["referenceId"], "structuralElement")
                for side in catalogs:
                    descriptor = item.get("connection", {}).get(side)
                    if descriptor:
                        original(side, descriptor["id"], "connection")
                        for key in ("sourceId", "targetId"):
                            if descriptor[key] is not None:
                                original(side, descriptor[key])
                    owner = item.get("owner", {}).get(side + "OwnerId")
                    if owner is not None:
                        original(side, owner)
                    for parent in item.get("containment", {}).get(side + "Parents") or []:
                        original(side, parent["parentId"])
                for hint in item["hints"]:
                    hint_targets(hint)
            for group in groups:
                for side in catalogs:
                    for identity in group[side + "Ids"]:
                        original(side, identity, "connection")
                    for identity in group[side + "EndpointIds"]:
                        original(side, identity)
                for hint in group["hints"]:
                    hint_targets(hint)
            for relation in relations:
                for side in catalogs:
                    for key in ("ChildId", "ParentId"):
                        if relation[side + key] is not None:
                            original(side, relation[side + key])
                for parent in relation["observedParents"]:
                    original("submission", parent["parentId"])
            for hint in hints:
                hint_targets(hint)
            for hint in report.get("limitations", []):
                hint_targets(hint)
    return report


def read_analysis(store, path, reference_key, comparison):
    envelope = store.read(path)
    require(envelope.get("schema") == "workflow-result/v1" and envelope.get("schemaVersion") == 1
            and envelope.get("status") == "ok" and envelope.get("capability") == "analytical-feedback",
            "expected successful analytical feedback")
    report = envelope["result"]
    require(report["evaluationId"] == comparison["evaluationId"] and report["pair"] == comparison["pair"]
            and report["pair"]["referenceKey"] == reference_key
            and report["comparisonHash"] == comparison["comparisonHash"], "analysis comparison mismatch")
    require(path == analysis_path(report) and envelope.get("analysisPath") == path
            and envelope.get("analysisKey") == report["analysisKey"], "analysis path mismatch")
    return validate_analysis(report, store)
