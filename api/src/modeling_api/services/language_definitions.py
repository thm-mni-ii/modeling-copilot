"""Normalize historical language payloads to a single connection identifier."""

from copy import deepcopy


def normalize_connection_types(data: dict) -> dict:
    """Resolve former rule aliases without modifying a stored language release."""
    result = deepcopy(data)
    aliases: dict[str, list[str]] = {}
    for connection in result.get("connections", []):
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
