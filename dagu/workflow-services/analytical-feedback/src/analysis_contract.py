"""Validate the compact analysis and its comparison identity."""

import hashlib
import json
import re
from workflow_io import identifier


SCHEMA = "analysis-feedback/v3"
LEGACY_SCHEMA = "analysis-feedback/v1"
CATEGORIES = ("nodes", "attributes", "connections", "other")
FACT_STATUSES = ("satisfied", "violated", "unresolved", "not_evaluated", "not_applicable")
IDENTITY_STATUSES = ("uniquely_supported", "supported", "unresolved")
RECOGNITION_STATUSES = ("evaluated", "partial", "not_evaluated", "not_applicable")
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
        parameters = {key: value for key, value in hint.items() if key not in ("code", "target", "status", "facts", "targets")}
        addressed = {(target["side"], target["id"]): target for target in list(targets) + hint.get("targets", [])}
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


def legacy_category_summary(bundle, nodes, mapped_reference_ids, comparison=None):
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


def recognized_reference_ids(comparison):
    """Count only selected, uniquely supported identities; never infer anchors."""
    rows = [row for field in ("provisionalElements", "provisionalConnections") for row in comparison["mapping"][field]]
    selected = {(row["referenceId"], row["studentId"]): row for row in rows}
    require(len(selected) == len(rows) and len({ref for ref, _ in selected}) == len(rows)
            and len({sub for _, sub in selected}) == len(rows), "recognition requires one-to-one correspondences")
    pending = {pair: {(dep["referenceId"], dep["studentId"]) for dep in row.get("dependsOn", [])} for pair, row in selected.items()}
    require(all(dependencies <= selected.keys() for dependencies in pending.values()), "unknown identity dependency")
    resolved = set()
    while True:
        ready = {pair for pair, dependencies in pending.items() if dependencies <= resolved} - resolved
        if not ready:
            break
        resolved.update(ready)
    require(len(resolved) == len(selected), "cyclic identity dependencies")
    recognized = set()
    for fact in comparison.get("propertyFacts", {}).get("items", []):
        if not fact["code"].startswith("identity.") or fact["evidence"].get("identityStatus") != "uniquely_supported":
            continue
        require(len(fact["referenceIds"]) == len(fact["submissionIds"]) == 1, "invalid selected identity fact")
        pair = fact["referenceIds"][0], fact["submissionIds"][0]
        require(pair in selected and fact["status"] == "satisfied" and any(
            criterion["role"] == "identity_anchor" and criterion["result"] == "satisfied"
            and criterion["method"] != "type_compatibility" for criterion in fact["evidence"]["criteria"]), "identity lacks sufficient evidence")
        require(pair[0] not in recognized, "duplicate recognized identity")
        recognized.add(pair[0])
    return recognized


def recognition_bucket(bundle, node):
    """Use the parser's unambiguous group, scoped by language and object kind."""
    if node["kind"] in ("structuralElement", "connectionLabel") or node.get("comparisonRole") == "structural":
        return None
    language = node.get("language") or {}
    group_id = node.get("comparisonGroup")
    native_type = node.get("type")
    key = {"language": language, "kind": node["kind"], "groupId": group_id, "type": None if group_id else native_type}
    name = group_id or native_type or "Unbekannter Typ"
    if group_id:
        for definition in bundle["languages"]:
            if all(definition[field] == language.get(field) for field in ("languageId", "versionId")):
                name = next((group["name"] for group in definition["data"].get("evaluation", {}).get("comparisonGroups", [])
                             if group["id"] == group_id), name)
    return {"id": content_hash(key), "label": name, "kind": node["kind"], "grouped": bool(group_id)}


def recognition_summary(bundle, indices, comparison):
    """The authoritative recognition report, based on matcher identity facts."""
    recognized = recognized_reference_ids(comparison)
    identities = {ref: fact for fact in comparison["propertyFacts"]["items"] if fact["code"].startswith("identity.")
                  for ref in fact["referenceIds"]}
    groups, descriptors = {}, {}
    for identity, node in indices["reference"].nodes.items():
        bucket = recognition_bucket(bundle, node)
        if bucket is not None:
            groups.setdefault(bucket["id"], []).append(identity)
            descriptors[bucket["id"]] = bucket

    def counts(ids):
        expected = len(ids)
        count = sum(identity in recognized for identity in ids)
        evaluated = sum(identities.get(identity, {}).get("evidence", {}).get("evaluationStatus") == "evaluated" for identity in ids)
        status = ("not_applicable" if not expected else "not_evaluated" if not evaluated else "partial"
                  if evaluated < expected or comparison.get("completeness", {}).get("interpretation") == "partial" else "evaluated")
        return {"recognized": count, "expected": expected, "percent": 100 * count / expected if expected and evaluated else None,
                "evaluationStatus": status}

    selected = {row["studentId"] for field in ("provisionalElements", "provisionalConnections") for row in comparison["mapping"][field]}
    unmatched = [{"id": identity, "kind": node["kind"]}
                 for identity, node in sorted(indices["student"].nodes.items()) if identity not in selected and recognition_bucket(bundle, node) is not None]
    return {"basis": "uniquely_supported", "buckets": [{**descriptors[key], **counts(groups[key])} for key in sorted(groups, key=lambda key: (descriptors[key]["label"], key))],
            "overall": counts([identity for ids in groups.values() for identity in ids]), "unmatchedSubmission": unmatched}


# Inline formatting of the editor (same tags as model-label-extraction); it is layout, never label text.
FORMATTING_TAG = re.compile(r"</?(?P<tag>b|strong|i|em|u|br|div)\s*/?>", re.IGNORECASE)


def clean_label(label: str) -> str:
    """Diagram line breaks are layout: a break before a lowercase letter splits a word, others separate words."""
    label = FORMATTING_TAG.sub(lambda match: "\n" if match.group("tag").lower() in ("br", "div") else "", label)
    return " ".join(re.sub(r"-?\s*\n\s*(?=[a-zäöüß])", "", label).split())


HINT_SOURCES = ("text_band", "neighbor_profile", "child_overlap")
HINT_RELATIONS = ("notation", "reordered", "head_form", "part_of_term", "abbreviation", "same_stem", None)


def label_hints(bundle, indices, comparison):
    """Learner hints from the matcher (AP-10); never counted and outside `recognition`.

    The reference text appears only here, and only while the frozen probe switch allows it (P9);
    everywhere else AF-19 applies unchanged.
    """
    show = (bundle["comparisonConfig"].get("graphMatching", {}).get("hints") or {}).get("showReferenceText") is True
    result = []
    for item in comparison["hints"]["items"]:
        reference = indices["reference"].nodes.get(item["referenceId"])
        submission = indices["student"].nodes.get(item["studentId"])
        require(reference is not None and submission is not None and submission["kind"] == "modelElement",
                "hint refers to unknown submission or reference objects")
        result.append({"id": item["id"], "kind": item["kind"], "submissionId": item["studentId"],
                       "referenceId": item["referenceId"], "submissionLabel": clean_label(submission.get("label") or ""),
                       "sources": list(item["sources"]), "relation": (item.get("wordRelation") or {}).get("relation"),
                       "suggestion": clean_label(reference.get("label") or "") or None if show else None})
    return result


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
    if isinstance(report, dict) and report.get("schema") in (SCHEMA, "analysis-feedback/v2"):
        return validate_current_analysis(report, store)
    require(isinstance(report, dict) and report.get("schema") == LEGACY_SCHEMA, "expected supported analytical feedback")
    require(report.get("status") == "provisional" and report.get("assessmentAvailable") is False,
            "analysis must remain provisional")
    require(report.get("contractVersion") in (None, "1.1", "1.2", "1.3"), "unsupported analysis contract version")
    structured = report.get("contractVersion") in ("1.1", "1.2", "1.3")
    factual = report.get("contractVersion") in ("1.2", "1.3")
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
                               "identity", "counterpart", "children", "directChildren", "connections", "incoming", "outgoing", "undirected")
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
            if report.get("contractVersion") == "1.3":
                identity_fact = next((fact for fact in item["facts"] if fact["code"].startswith("identity.")), None)
                if item["target"]["kind"] in ("modelElement", "connection"):
                    require(identity_fact is not None and item.get("identity") == {
                        "status": identity_fact["evidence"]["identityStatus"],
                        "criteria": identity_fact["evidence"]["criteria"],
                        "supportingCandidateCount": identity_fact["evidence"]["supportingCandidateCount"]}, "identity differs from matcher fact")
                    require(item["identity"]["status"] in ("uniquely_supported", "supported", "unresolved"), "invalid identity status")
                for fact in item["facts"]:
                    require(fact.get("id") == content_hash({key: value for key, value in fact.items() if key != "id"})
                            and isinstance(fact.get("targets"), list), "invalid fact identity or display targets")
            require(item.get("consistency") in ("fully_consistent", "partial", "different", "unresolved", "not_evaluated"),
                    "invalid factual consistency")
            if item["consistency"] == "fully_consistent":
                require(item["match"]["status"] == "provisional" and item["facts"]
                        and all(fact["status"] in ("satisfied", "not_applicable") for fact in item["facts"])
                        and any(fact["status"] == "satisfied" for fact in item["facts"]), "unsupported full consistency")
                if report.get("contractVersion") == "1.3":
                    require(item.get("identity", {}).get("status") == "uniquely_supported", "full consistency requires identified object")
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
            require(source.get("version") in ("1.0", "1.1") and isinstance(source.get("items"), list), "missing matcher fact source")
            for fact in source["items"]:
                require(set(fact["referenceIds"]) <= set(reference_nodes)
                        and set(fact["submissionIds"]) <= set(student_nodes), "fact has unknown original ID")
                catalogs = {"reference": reference_nodes, "submission": student_nodes}
                for target in fact.get("targets", []):
                    require(target.get("side") in catalogs and target.get("id") in catalogs[target["side"]]
                            and catalogs[target["side"]][target["id"]]["kind"] == target.get("kind"), "fact has unknown display target")
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
            require(report["summary"] == legacy_category_summary(store.snapshot(), reference_nodes.values(), set(pairs.values()), comparison),
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


def compact_identity(fact):
    if fact is None:
        return None
    fields = ("method", "role", "result", "matched", "expected", "observed", "complete", "referenceChildIds", "submissionChildIds",
              # The matcher's own text verdict: scores, reached tier, its applied thresholds and any guard veto.
              "scores", "tier", "minimumSimilarity", "veto")
    criteria = [{**{key: criterion[key] for key in fields if key in criterion},
                 **({"dependsOn": criterion["dependsOn"]} if criterion.get("dependsOn") else {})}
                for criterion in fact["evidence"]["criteria"] if criterion["result"] not in ("not_evaluated", "not_applicable")]
    return {"status": fact["evidence"]["identityStatus"], "criteria": criteria}


def compact_fact(fact):
    """Keep source identity and property evidence without repeated descriptors."""
    duplicated = {"referenceObservation", "submissionObservation", "criteria", "dependsOn", "referenceEndpoints", "submissionEndpoints"}
    return {"id": fact["id"], "code": fact["code"], "status": fact["status"],
            "referenceIds": fact["referenceIds"], "submissionIds": fact["submissionIds"],
            "evidence": {key: value for key, value in fact["evidence"].items() if key not in duplicated}}


def validate_recognition(recognition):
    grouped = isinstance(recognition, dict) and "buckets" in recognition
    if grouped:
        rows = recognition["buckets"]
        require(isinstance(rows, list) and all(isinstance(row, dict) and set(row) == {"id", "label", "kind", "grouped", "recognized", "expected", "percent", "evaluationStatus"}
                and isinstance(row["id"], str) and isinstance(row["label"], str) and row["kind"] in KINDS and type(row["grouped"]) is bool
                and type(row["expected"]) is int and row["expected"] > 0 for row in rows)
                and len({row["id"] for row in rows}) == len(rows), "invalid recognition buckets")
        counts = [{key: row[key] for key in ("recognized", "expected", "percent", "evaluationStatus")} for row in rows]
    else:
        counts = list(recognition.get("categories", {}).values()) if isinstance(recognition, dict) else []
    require(isinstance(recognition, dict) and recognition.get("basis") == "uniquely_supported"
            and (grouped or isinstance(recognition.get("categories"), dict) and set(recognition["categories"]) == set(CATEGORIES))
            and isinstance(recognition.get("unmatchedSubmission"), list), "invalid recognition overview")
    for row in [recognition.get("overall"), *counts]:
        require(isinstance(row, dict) and set(row) == {"recognized", "expected", "percent", "evaluationStatus"}
                and all(type(row.get(key)) is int and row[key] >= 0 for key in ("recognized", "expected"))
                and row["recognized"] <= row["expected"]
                and row.get("evaluationStatus") in RECOGNITION_STATUSES, "invalid recognition counts")
        percent = row["percent"]
        require(percent is None or type(percent) in (int, float) and row["expected"] > 0
                and abs(percent - 100 * row["recognized"] / row["expected"]) < 0.000001, "invalid recognition percentage")
        require((percent is None) == (row["evaluationStatus"] in ("not_evaluated", "not_applicable")), "invalid recognition evaluability")
    require(all(recognition["overall"][key] == sum(row[key] for row in counts)
                for key in ("recognized", "expected")), "recognition totals differ from categories")
    unmatched = recognition["unmatchedSubmission"]
    require(all(isinstance(row, dict) and isinstance(row.get("id"), str) and row.get("kind") in KINDS
                and (grouped or row.get("category") in CATEGORIES) for row in unmatched)
            and len({row["id"] for row in unmatched}) == len(unmatched), "invalid unmatched submission objects")
    return recognition


def validate_current_analysis(report, store=None):
    require(report.get("schema") in (SCHEMA, "analysis-feedback/v2") and report.get("assessmentAvailable") is False
            and report.get("status") == "provisional", "invalid analytical feedback")
    require(report.get("analysisKey") == analysis_key(report), "analysis key mismatch")
    require(report.get("analysisHash") == content_hash({key: value for key, value in report.items() if key != "analysisHash"}), "analysis hash mismatch")
    validate_recognition(report.get("recognition"))
    annotations, hints = report.get("annotations"), report.get("referenceHints")
    require(isinstance(annotations, list) and isinstance(hints, list), "invalid annotation lists")

    def facts_valid(facts):
        require(isinstance(facts, list), "missing compact facts")
        for fact in facts:
            require(isinstance(fact, dict) and set(fact) == {"id", "code", "status", "referenceIds", "submissionIds", "evidence"}
                    and isinstance(fact["id"], str) and len(fact["id"]) == 64 and isinstance(fact["code"], str)
                    and fact["status"] in FACT_STATUSES and all(isinstance(fact[key], list) and all(isinstance(identity, str) for identity in fact[key]) for key in ("referenceIds", "submissionIds"))
                    and isinstance(fact["evidence"], dict) and fact["evidence"].get("basis") in ("direct_observation", "independent_evidence", "conditional_mapping")
                    and isinstance(fact["evidence"].get("reason"), str)
                    and not {"criteria", "referenceObservation", "submissionObservation"} & fact["evidence"].keys(), "invalid compact fact")

    seen, references = set(), set()
    for item in annotations:
        target = item["target"]
        require(target.get("side") == "submission" and target.get("kind") in KINDS
                and isinstance(target.get("id"), str) and target["id"] not in seen, "invalid annotation target")
        seen.add(target["id"])
        if "referenceId" in item:
            require(isinstance(item["referenceId"], str) and item["referenceId"] not in references, "duplicate reference identity")
            references.add(item["referenceId"])
        identity = item.get("identity")
        if target["kind"] in ("modelElement", "connection"):
            require(isinstance(identity, dict) and identity.get("status") in IDENTITY_STATUSES
                    and isinstance(identity.get("criteria"), list), "invalid identity profile")
            require(all(criterion.get("role") in ("compatibility", "support", "identity_anchor") and criterion.get("result") in FACT_STATUSES
                        and isinstance(criterion.get("method"), str) for criterion in identity["criteria"]), "invalid identity criterion")
        require(not {"status", "checks", "consistency", "match"} & item.keys(), "redundant annotation status fields")
        facts_valid(item.get("facts"))
        require(isinstance(item.get("hints"), list) and all(hint.get("code") in HINT_DEFINITIONS and hint.get("scope") in ("element", "relation", "group", "model")
                and isinstance(hint.get("targets"), list) and hint.get("factId") in {fact["id"] for fact in item["facts"]} for hint in item["hints"]), "invalid compact hints")
    for hint in hints:
        facts_valid(hint.get("facts"))
        require(hint.get("code") in HINT_DEFINITIONS and isinstance(hint.get("targets"), list), "invalid reference hint")
    require(isinstance(report.get("connectionGroups"), list), "missing connection groups")
    for group in report["connectionGroups"]:
        facts_valid(group.get("facts"))
    hint_ids = set()
    for hint in report.get("labelHints", []):
        require(isinstance(hint, dict) and set(hint) == {"id", "kind", "submissionId", "referenceId", "submissionLabel", "sources", "relation", "suggestion"}
                and hint["kind"] == "label_differs" and hint["id"] not in hint_ids and isinstance(hint["submissionId"], str)
                and isinstance(hint["sources"], list) and hint["sources"] and set(hint["sources"]) <= set(HINT_SOURCES)
                and hint["relation"] in HINT_RELATIONS and (hint["suggestion"] is None or isinstance(hint["suggestion"], str)),
                "invalid label hint")
        hint_ids.add(hint["id"])
    if store is not None:
        bundle = store.snapshot()
        catalogs = {"submission": {node["id"]: node for node in store.read("graphs/submission.json")["result"]["graph"]["nodes"]},
                    "reference": {node["id"]: node for node in store.read(f"graphs/{report['pair']['referenceKey']}.json")["result"]["graph"]["nodes"]}}
        require(seen == set(catalogs["submission"]), "annotations must cover submission objects")
        comparison = store.read(f"comparisons/{report['pair']['referenceKey']}.json")["result"]
        require(report["comparisonHash"] == comparison["comparisonHash"] and report["pair"] == comparison["pair"], "analysis comparison mismatch")
        source = comparison["propertyFacts"]["items"]

        def target_valid(target):
            if target.get("kind") == "model":
                model = next(row["source"]["modelId"] for row in bundle["models"] if row["source"]["key"] == "submission")
                return target.get("side") == "submission" and target.get("id") == model
            return target.get("side") in catalogs and target.get("id") in catalogs[target["side"]] and catalogs[target["side"]][target["id"]]["kind"] == target.get("kind")

        pairs = {row["studentId"]: row["referenceId"] for field in ("provisionalElements", "provisionalConnections") for row in comparison["mapping"][field]}
        for item in annotations:
            target = item["target"]
            require(target["kind"] == catalogs["submission"][target["id"]]["kind"] and item.get("referenceId") == pairs.get(target["id"]), "annotation differs from original mapping")
            if report["schema"] == "analysis-feedback/v2":
                require(item.get("category") == category_for(bundle, catalogs["submission"][target["id"]]), "annotation category mismatch")
            selected = [fact for fact in comparison["propertyFacts"]["items"] if target["id"] in fact["submissionIds"]]
            require(item["facts"] == [compact_fact(fact) for fact in selected if not fact["code"].startswith(("identity.", "connection_group."))], "annotation facts differ from matcher")
            identity_fact = next((fact for fact in selected if fact["code"].startswith("identity.")), None)
            if identity_fact:
                require(item["identity"] == compact_identity(identity_fact), "identity differs from matcher")
            for hint in item["hints"]:
                fact = next(fact for fact in selected if fact["id"] == hint["factId"])
                require(hint["targets"] == fact["targets"] and all(target_valid(target) for target in hint["targets"]), "hint targets differ from matcher")
        require(len(hints) == len(set(catalogs["reference"]) - references)
                and {hint["referenceId"] for hint in hints} == set(catalogs["reference"]) - references, "reference hints do not cover unmatched originals")
        for hint in hints:
            require(target_valid(hint["target"]) and all(target_valid(target) for target in hint["targets"]), "unknown reference display target")
            require(hint["facts"] == [compact_fact(fact) for fact in source if hint["referenceId"] in fact["referenceIds"]
                    and not fact["code"].startswith(("identity.", "connection_group."))], "reference facts differ from matcher")
        for group in report["connectionGroups"]:
            require(group["facts"] == [compact_fact(fact) for fact in source if fact["code"].startswith("connection_group.")
                    and fact["referenceIds"] == group["referenceIds"] and fact["submissionIds"] == group["submissionIds"]], "group facts differ from matcher")
        if report["schema"] == SCHEMA:
            from types import SimpleNamespace
            indices = {"reference": SimpleNamespace(nodes=catalogs["reference"]), "student": SimpleNamespace(nodes=catalogs["submission"])}
            require(report["recognition"] == recognition_summary(bundle, indices, comparison), "recognition differs from matcher and reference buckets")
            require(("labelHints" in report) == ("hints" in comparison)
                    and report.get("labelHints", []) == (label_hints(bundle, indices, comparison) if "hints" in comparison else []),
                    "label hints differ from matcher")
        else:
            recognized = recognized_reference_ids(comparison)
            for category, row in report["recognition"]["categories"].items():
                require(row["recognized"] == sum(category_for(bundle, catalogs["reference"][ref]) == category for ref in recognized), "recognition disagrees with identities")
                require(row["expected"] == sum(category_for(bundle, node) == category for node in catalogs["reference"].values()), "recognition denominator differs from reference")
            require(report["recognition"]["unmatchedSubmission"] == [
                {"id": identity, "kind": node["kind"], "category": category_for(bundle, node)}
                for identity, node in sorted(catalogs["submission"].items())
                if identity not in pairs and category_for(bundle, node) is not None], "unmatched submission differs from original mapping")
    return report


def read_comparison(store, reference_key: str) -> dict:
    reference_key = identifier(reference_key)
    if reference_key == "submission":
        raise ValueError("REFERENCE_KEY must select a reference model")
    bundle = store.snapshot()
    models = {}
    for role, key in (("student", "submission"), ("reference", reference_key)):
        selected = [model["source"] for model in bundle["models"] if model["source"]["key"] == key]
        expected = "submission" if role == "student" else "reference"
        if len(selected) != 1 or selected[0]["role"] != expected:
            raise ValueError("comparison pair does not match the frozen models")
        models[role] = selected[0]
    envelope = store.read(f"comparisons/{reference_key}.json")
    result = envelope.get("result")
    if (envelope.get("schema") != "workflow-result/v1" or envelope.get("schemaVersion") != 1
            or envelope.get("status") != "ok" or envelope.get("capability") != "one-to-one-graph-matching"
            or not isinstance(result, dict) or result.get("schema") not in ("reference-comparison/v1", "reference-comparison/v2")
            or result.get("status") != "partial" or result.get("assessmentAvailable") is not False):
        raise ValueError("expected a successful reference-comparison/v1 or v2 artifact")
    if (result.get("evaluationId") != bundle["evaluationId"] or result.get("inputHash") != bundle["inputHash"]
            or result.get("pair") != {"studentKey": "submission", "referenceKey": reference_key}
            or result.get("sources") != models):
        raise ValueError("comparison provenance does not match the frozen pair")
    if result.get("comparisonHash") != content_hash({key: value for key, value in result.items()
                                                      if key != "comparisonHash"}):
        raise ValueError("comparison hash mismatch")
    if (result["completeness"]["matching"] != "provisional"
            or result["completeness"]["structuralComparison"] != "provisional_owner_and_connections"):
        raise ValueError("unsupported comparison completeness")
    return result


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
