"""Resolve recognition categories from frozen language definitions, without type-name heuristics."""

from modeling_api.core.errors import ApiError


def element_categories(definitions: list[dict]) -> list[dict]:
    result = []
    for language in definitions:
        data = language["data"]
        defaults = {}

        def visit(elements):
            for element in elements:
                defaults[element["type"]] = "other"
                visit(element.get("children", []))

        visit(data.get("elements", []))
        configured = data.get("evaluation", {}).get("elementCategories", {})
        if (not isinstance(configured, dict)
                or any(key not in defaults or value not in ("nodes", "attributes", "other")
                       for key, value in configured.items())):
            raise ApiError(422, "INVALID_ELEMENT_CATEGORIES", "Recognition categories must classify known element types.")
        for native_type, category in sorted({**defaults, **configured}.items()):
            result.append({"languageId": language["languageId"], "versionId": language["versionId"],
                           "type": native_type, "category": category})
    return result
