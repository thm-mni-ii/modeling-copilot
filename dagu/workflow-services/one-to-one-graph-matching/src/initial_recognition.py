"""Conservative connection proposals and provisional recognition counts."""

from collections import Counter, defaultdict

from artifacts import _key
from initial_evaluation import _class_key, _language_value, _sort_key, _type_key


def propose_connections(indices, elements):
    pairs = [(item["referenceId"], item["studentId"]) for item in elements]
    if len(set(pairs)) != len(pairs) or len({r for r, _ in pairs}) != len(pairs) or len({s for _, s in pairs}) != len(pairs):
        raise ValueError("provisional elements must be unique one-to-one pairs")
    mapping = dict(pairs)
    connections = {
        side: {identity: node for identity, node in index.nodes.items() if node["kind"] == "connection"}
        for side, index in indices.items()
    }

    def signature(index, identity, node, endpoint_mapping=None):
        key = _key(node)
        direction = node.get("directed")
        endpoints = index.endpoints.get(identity, {})
        source, target = endpoints.get("source"), endpoints.get("target")
        if (key is None or node["languageResolution"] != "resolved" or node["comparisonRole"] != "semantic"
                or not isinstance(direction, bool) or source is None or target is None):
            return None
        if endpoint_mapping is not None:
            source, target = endpoint_mapping.get(source), endpoint_mapping.get(target)
            if source is None or target is None:
                return None
        terminals = (source, target) if direction else tuple(sorted((source, target)))
        return key, direction, terminals

    grouped = {side: defaultdict(list) for side in connections}
    for side, nodes in connections.items():
        for identity, node in nodes.items():
            value = signature(indices[side], identity, node, mapping if side == "reference" else None)
            if value is not None:
                grouped[side][value].append(identity)
    proposals = []
    for signature_key, references in grouped["reference"].items():
        students = grouped["student"].get(signature_key, [])
        if len(references) == len(students) == 1:
            proposals.append({"referenceId": references[0], "studentId": students[0],
                              "reason": "compatible_type_and_mapped_endpoints", "status": "provisional"})
    proposals.sort(key=lambda item: (item["referenceId"], item["studentId"]))
    return {
        "proposals": proposals,
        "evaluableReferenceIds": sorted(identity for identities in grouped["reference"].values()
                                        for identity in identities),
        "unresolvedReferenceIds": sorted(set(connections["reference"]) - {p["referenceId"] for p in proposals}),
        "unresolvedStudentIds": sorted(set(connections["student"]) - {p["studentId"] for p in proposals}),
    }


def evaluate_connections(indices, elements):
    """Compare connection relations without selecting connection identities."""
    pairs = [(item["referenceId"], item["studentId"]) for item in elements]
    if (len({reference for reference, _ in pairs}) != len(pairs)
            or len({student for _, student in pairs}) != len(pairs)
            or any(reference not in indices["reference"].nodes
                   or indices["reference"].nodes[reference]["kind"] != "modelElement"
                   or student not in indices["student"].nodes
                   or indices["student"].nodes[student]["kind"] != "modelElement"
                   for reference, student in pairs)):
        raise ValueError("provisional elements must be unique one-to-one model element pairs")
    mapping = dict(pairs)
    inverse = {student: reference for reference, student in pairs}
    groups = defaultdict(lambda: {"reference": [], "student": []})
    unresolved = {"reference": [], "student": []}
    counts = {"reference": 0, "student": 0}
    for side, index in indices.items():
        for identity, node in index.nodes.items():
            if node["kind"] != "connection":
                continue
            counts[side] += 1
            endpoints = index.endpoints.get(identity, {})
            source, target = endpoints.get("source"), endpoints.get("target")
            source_student = mapping.get(source) if side == "reference" else source
            target_student = mapping.get(target) if side == "reference" else target
            if source_student not in inverse or target_student not in inverse:
                unresolved[side].append(identity)
                continue
            endpoints_key = tuple(sorted((source_student, target_student)))
            groups[endpoints_key][side].append({
                "id": identity, "sourceId": source, "targetId": target,
                "directed": node.get("directed"), "type": node["type"],
                "language": node["language"], "languageResolution": node["languageResolution"],
                "_mappedSource": source_student, "_mappedTarget": target_student,
            })

    def direction_signature(item):
        if item["directed"]:
            return True, item["_mappedSource"], item["_mappedTarget"]
        return (False,)

    rows = []
    for endpoints, grouped in sorted(groups.items()):
        references = sorted(grouped["reference"], key=lambda item: item["id"])
        students = sorted(grouped["student"], key=lambda item: item["id"])
        balanced = bool(references and len(references) == len(students))
        directions_known = all(isinstance(item["directed"], bool) for item in references + students)
        direction_status = "not_evaluated"
        if balanced and directions_known:
            direction_status = ("equal" if Counter(map(direction_signature, references))
                                == Counter(map(direction_signature, students)) else "different")

        def language_key(item):
            language = item["language"]
            if (item["languageResolution"] != "resolved" or not language
                    or not item["type"]):
                return None
            return language["languageId"], language["versionId"]

        languages = {language_key(item) for item in references + students}
        type_status = "not_evaluated"
        if balanced and len(languages) == 1 and None not in languages:
            type_status = ("equal" if Counter(item["type"] for item in references)
                           == Counter(item["type"] for item in students) else "different")
        configuration_status = "not_evaluated"
        if direction_status != "not_evaluated" and type_status != "not_evaluated":
            def configuration(item):
                return direction_signature(item), item["type"]

            configuration_status = ("equal" if Counter(map(configuration, references))
                                    == Counter(map(configuration, students)) else "different")

        def public(items):
            return [{key: value for key, value in item.items() if not key.startswith("_")} for item in items]

        rows.append({
            "referenceEndpointIds": sorted(inverse[identity] for identity in endpoints),
            "studentEndpointIds": list(endpoints),
            "referenceCount": len(references), "studentCount": len(students),
            "referenceOnlyCount": max(0, len(references) - len(students)),
            "studentOnlyCount": max(0, len(students) - len(references)),
            "directionStatus": direction_status, "typeStatus": type_status,
            "configurationStatus": configuration_status,
            "referenceConnections": public(references), "studentConnections": public(students),
        })
    return {
        "completeness": "partial" if any(unresolved.values()) else "complete",
        "referenceConnectionCount": counts["reference"], "studentConnectionCount": counts["student"],
        "unresolvedReferenceConnectionIds": sorted(unresolved["reference"]),
        "unresolvedStudentConnectionIds": sorted(unresolved["student"]),
        "byEndpoints": rows,
    }


def recognition_metrics(indices, elements, connections, category_config):
    if not isinstance(category_config, list):
        raise ValueError("graphMatching.elementCategories must be an array")
    categories = {}
    for item in category_config:
        if (not isinstance(item, dict) or set(item) != {"languageId", "versionId", "type", "category"}
                or any(not isinstance(item[field], str) or not item[field]
                       for field in ("languageId", "versionId", "type"))
                or item["category"] not in ("nodes", "attributes", "other")):
            raise ValueError("invalid graphMatching.elementCategories entry")
        key = (item["languageId"], item["versionId"], item["type"])
        if key in categories:
            raise ValueError("duplicate graphMatching.elementCategories entry")
        categories[key] = item["category"]

    reference_nodes = {identity: node for identity, node in indices["reference"].nodes.items()
                       if node["kind"] == "modelElement"}
    element_pairs = {(item["referenceId"], item["studentId"]) for item in elements}
    if (len(element_pairs) != len(elements)
            or len({r for r, _ in element_pairs}) != len(elements)
            or len({s for _, s in element_pairs}) != len(elements)
            or any(r not in reference_nodes or s not in indices["student"].nodes
                   or indices["student"].nodes[s]["kind"] != "modelElement" for r, s in element_pairs)):
        raise ValueError("invalid provisional element mapping")

    def counts(reference_ids):
        selected = [item for item in elements if item["referenceId"] in reference_ids]
        semantic = sum(item["reason"] == "supported_semantic_evidence" for item in selected)
        total = len(selected)
        return {"referenceCount": len(reference_ids), "provisionalAnchorCount": total - semantic,
                "semanticProposalCount": semantic, "provisionalRecognizedCount": total,
                "coverage": total / len(reference_ids) if reference_ids else None}

    metrics = {"overall": counts(set(reference_nodes))}
    for field, key_fn in (("byReferenceType", _type_key), ("byComparisonClass", _class_key)):
        grouped = defaultdict(set)
        for identity, node in reference_nodes.items():
            grouped[key_fn(node)].add(identity)
        views = []
        for key in sorted(grouped, key=_sort_key):
            category = {"language": _language_value(key)}
            if field == "byReferenceType":
                category["type"] = key[2]
            else:
                category.update({"basis": key[2], "value": key[3]})
            views.append({"category": category, **counts(grouped[key])})
        metrics[field] = views

    def category_for(node):
        if node["kind"] == "connection":
            return "connections"
        return categories.get(_type_key(node), "other")

    by_type = {}
    matched = {
        "modelElement": {item["referenceId"]: item for item in elements},
        "connection": {item["referenceId"]: item for item in connections["proposals"]},
    }
    evaluable_connections = set(connections["evaluableReferenceIds"])
    for side, index in indices.items():
        for identity, node in index.nodes.items():
            if node["kind"] not in matched:
                continue
            type_key = _type_key(node)
            key = (category_for(node), *type_key)
            row = by_type.setdefault(key, {
                "category": key[0], "language": _language_value(type_key), "type": node["type"],
                "referenceCount": 0, "studentCount": 0, "evaluableReferenceCount": 0, "provisionalAnchorCount": 0,
                "semanticProposalCount": 0, "connectionProposalCount": 0, "provisionalRecognizedCount": 0,
            })
            row["referenceCount" if side == "reference" else "studentCount"] += 1
            if side == "reference" and (
                identity in evaluable_connections if node["kind"] == "connection" else
                node["comparisonRole"] == "semantic" and node["languageResolution"] == "resolved"
                and _key(node) is not None
            ):
                row["evaluableReferenceCount"] += 1
            if side == "reference" and identity in matched[node["kind"]]:
                row["provisionalRecognizedCount"] += 1
                reason = matched[node["kind"]][identity]["reason"]
                if reason == "supported_semantic_evidence":
                    row["semanticProposalCount"] += 1
                elif node["kind"] == "modelElement":
                    row["provisionalAnchorCount"] += 1
                else:
                    row["connectionProposalCount"] += 1
    metrics["categoryTypes"] = [by_type[key] for key in sorted(by_type, key=_sort_key)]
    metrics["allCategories"] = {
        field: sum(row[field] for row in metrics["categoryTypes"])
        for field in ("referenceCount", "studentCount", "evaluableReferenceCount", "provisionalAnchorCount",
                      "semanticProposalCount", "connectionProposalCount", "provisionalRecognizedCount")
    }
    return metrics
