"""Project matcher facts without making matching or property decisions."""

from copy import deepcopy

from analysis_contract import require


CHECK_NAMES = {
    "label": "label", "type": "type", "owner": "owner", "containment": "containment",
    "counterpart": "counterpart", "children": "children", "direct_children": "directChildren",
    "connections": "connections", "incoming": "incoming", "outgoing": "outgoing", "undirected": "undirected",
}


def project_facts(comparison, annotations, reference_hints, groups):
    source = comparison.get("propertyFacts")
    if source is None:
        return False
    require(source.get("version") == "1.0" and isinstance(source.get("items"), list), "unsupported matcher facts")
    facts = source["items"]

    def hint(item):
        prefix = "fact.group_" if item["code"].startswith("connection_group.") else "fact."
        return {"code": prefix + item["status"], "factCode": item["code"],
                "basis": item["evidence"]["basis"], "reason": item["evidence"]["reason"],
                "referenceIds": item["referenceIds"], "submissionIds": item["submissionIds"]}

    for sub, annotation in annotations.items():
        selected = deepcopy([item for item in facts if sub in item["submissionIds"]])
        annotation["facts"] = selected
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
        annotation["hints"].extend(hint(item) for item in selected if item["status"] in ("violated", "unresolved"))
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
