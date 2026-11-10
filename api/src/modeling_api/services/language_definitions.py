"""Normalize language syntax defaults and historical connection identifiers."""

from copy import deepcopy

from modeling_api.db.migrations.resources import load_data


def normalize_syntax(data: dict, *, reset_templates: bool = False, default_state: str = "allowed") -> dict:
    """Materialize syntax defaults; only the one-time migration resets custom text.

    Missing cycle rules stay absent: an empty cycle rule would forbid cycles.
    Missing matrix defaults stay permissive, matching historical validation.
    """
    result = deepcopy(data)
    templates = load_data("10_language_syntax_defaults", "templates.json")
    syntax = result.setdefault("syntax", [])
    for rule_type in ("multiplicity", "containment"):
        if not any(rule["ruleType"] == rule_type for rule in syntax):
            syntax.append({"ruleType": rule_type, "config": {"relations": []}})

    def fill_templates(config, defaults):
        for key, value in defaults.items():
            if isinstance(value, dict):
                fill_templates(config.setdefault(key, {}), value)
            elif reset_templates or not (config.get(key) or "").strip():
                config[key] = value

    for rule in syntax:
        config = rule["config"]
        if rule["ruleType"] == "multiplicity":
            fill_templates(config, templates["multiplicity"])
            config.setdefault("defaultState", default_state)
            for relation in config.setdefault("relations", []):
                refinement = relation["refinement"]
                refinement.pop("messageTemplate", None)
                refinement.setdefault("endpoints", [])
                for route in refinement.setdefault("routes", []):
                    route.pop("messageTemplate", None)
            for limit in config.setdefault("incoming", []):
                limit.pop("messageTemplate", None)
                limit.setdefault("direction", "incoming")
                limit.setdefault("connectionTypes", [])
                limit.setdefault("neighborTypes", [])
                limit.setdefault("countScope", "element")
                limit.setdefault("endpoints", {"pointIds": [], "groups": []})
        elif rule["ruleType"] == "containment":
            config.setdefault("relations", [])
            fill_templates(config, {"messageTemplate": templates["containment"]})
        elif rule["ruleType"] == "acyclic":
            config.setdefault("mode", "forbid")
            config.setdefault("connectionTypes", [])
            config.setdefault("elementTypes", [])
            config.setdefault("ignoreDirection", False)
            fill_templates(config, {"messageTemplate": templates["acyclic"][config["mode"]]})
    return result


def normalize_connection_types(data: dict, inherited_connections: list[dict] | None = None) -> dict:
    """Resolve former rule aliases without modifying a stored language release."""
    result = deepcopy(data)
    aliases: dict[str, list[str]] = {}
    for connection in [*(inherited_connections or []), *result.get("connections", [])]:
        identifier = connection.get("type")
        previous = connection.get("connectionType") or identifier
        if isinstance(identifier, str) and isinstance(previous, str):
            aliases.setdefault(previous, []).append(identifier)

    def rewrite(value, *, syntax=False):
        if isinstance(value, list):
            for item in value:
                rewrite(item, syntax=syntax)
        elif isinstance(value, dict):
            if "type" in value and "style" in value:
                value.pop("connectionType", None)
                if "renderMode" not in value:
                    value.pop("points", None)
            for key, item in value.items():
                if syntax and key == "connectionTypes" and isinstance(item, list):
                    value[key] = list(dict.fromkeys(
                        identifier for selected in item
                        for identifier in aliases.get(selected, [selected])
                    ))
                else:
                    rewrite(item, syntax=syntax or key == "syntax")

    rewrite(result)
    return result
