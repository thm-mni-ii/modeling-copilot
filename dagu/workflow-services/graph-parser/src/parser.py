"""Normalize maxGraph snapshots without validating the modeled content."""
import hashlib
import json
import xml.etree.ElementTree as ET
from typing import Literal, NotRequired, TypedDict


class LanguageReference(TypedDict):
    languageId: str
    versionId: str


class LanguageVersion(LanguageReference):
    data: dict
    includedLanguageVersions: list[LanguageReference]


class DefinitionReference(LanguageReference):
    # JSON Pointer relative to LanguageVersion.data.
    path: str
    definitionId: NotRequired[str]


DefinitionEntry = tuple[DefinitionReference, dict]
Scalar = str | int | float | bool | None


class DefinitionBinding(TypedDict):
    language: LanguageReference | None
    languageResolution: Literal["resolved", "ambiguous", "unresolved"]
    definition: DefinitionReference | None
    definitionCandidates: NotRequired[list[DefinitionReference]]


class TextFormatting(TypedDict):
    fontStyle: int
    bold: bool
    italic: bool
    underline: bool


class GraphNode(DefinitionBinding):
    id: str
    kind: Literal["modelElement", "structuralElement", "connection", "connectionLabel"] | None
    type: str | None
    comparisonGroup: str | None
    label: str
    properties: NotRequired[dict[str, Scalar | TextFormatting]]
    comparisonRole: Literal["semantic", "structural", "unsupported"]
    connectionLabelId: NotRequired[str]
    directed: NotRequired[bool | None]


class GraphEdge(TypedDict):
    id: NotRequired[str]
    kind: Literal["contains", "endpoint"]
    role: str | None
    source: str | None
    target: str | None


class Graph(TypedDict):
    schemaVersion: Literal[3]
    languages: list[LanguageReference]
    nodes: list[GraphNode]
    edges: list[GraphEdge]


def content_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_languages(bundle: dict, references: list[LanguageReference]) -> list[LanguageVersion]:
    """Select pinned language versions and their dependencies from the snapshot."""
    catalog = {(item["languageId"], item["versionId"]): item for item in bundle["languages"]}
    selected = {}
    pending = list(references)
    while pending:
        reference = pending.pop()
        key = (reference["languageId"], reference["versionId"])
        if key in selected:
            continue
        if key not in catalog:
            raise ValueError("a referenced language version is missing from the frozen input")
        selected[key] = catalog[key]
        pending.extend(catalog[key].get("includedLanguageVersions", []))
    return [selected[key] for key in sorted(selected)]


def flag(value: object) -> bool:
    return value is True or value in ("true", "1", 1)


def object_field(cell: ET.Element, name: str) -> dict:
    for child in cell:
        if child.get("as") == name:
            return dict(child.attrib)
    return {}


def style_of(cell: ET.Element) -> dict:
    # Current exports store an Object; older exports can store a style string.
    style = dict(part.split("=", 1) for part in cell.get("style", "").split(";") if "=" in part)
    style.update(object_field(cell, "style"))
    return style


def scalar_properties(cell: ET.Element) -> dict:
    # Explicit model properties only, never the whole rendering style/geometry.
    return {key: value for key, value in object_field(cell, "diagramAttributes").items()
            if key not in ("as", "id", "type", "label")}


def text_formatting(style: dict) -> TextFormatting | None:
    value = style.get("fontStyle")
    try:
        font_style = int(value)
    except (TypeError, ValueError):
        return None
    if font_style < 0:
        return None
    return {
        "fontStyle": font_style,
        "bold": bool(font_style & 1),
        "italic": bool(font_style & 2),
        "underline": bool(font_style & 4),
    }


def label_of(cell: ET.Element) -> str:
    return cell.get("value", object_field(cell, "diagramAttributes").get("label", ""))


def type_of(cell: ET.Element) -> str:
    if flag(cell.get("edge")):
        return cell.get("connectionId", "")
    if cell.get("connectionLabelId") is not None:
        return cell.get("connectionLabelId", "")
    return cell.get("diagramElementType") or object_field(cell, "diagramAttributes").get("type") or ""


def language_catalog(languages: object) -> tuple[dict, dict, set, set, list, dict]:
    if not isinstance(languages, list):
        raise ValueError("input.languages must be an array of resolved language versions")
    elements, connections, feedback_elements, feedback_connections, references = {}, {}, set(), set(), []
    comparison_groups = {}
    seen = set()
    for language in languages:
        if not isinstance(language, dict) or not all(isinstance(language.get(key), str) and language[key] for key in ("languageId", "versionId")):
            raise ValueError("each language needs non-empty languageId and versionId")
        reference = {key: language[key] for key in ("languageId", "versionId")}
        identity = (reference["languageId"], reference["versionId"])
        if identity in seen:
            raise ValueError(f"duplicate language version: {identity}")
        seen.add(identity)
        references.append(reference)
        data = language.get("data")
        if not isinstance(data, dict):
            raise ValueError("each language needs its definition in data")

        def register(definitions: object, catalog: dict, path: str, nested: bool = False) -> None:
            if not isinstance(definitions, list):
                raise ValueError("language elements/connections/children must be arrays")
            for index, definition in enumerate(definitions):
                if not isinstance(definition, dict) or not isinstance(definition.get("type"), str) or not definition["type"]:
                    raise ValueError("each language definition needs a non-empty type")
                definition_path = f"{path}/{index}"
                definition_reference = {**reference, "path": definition_path}
                if isinstance(definition.get("id"), str) and definition["id"]:
                    definition_reference["definitionId"] = definition["id"]
                entry = (definition_reference, definition)
                candidates = catalog.setdefault(definition["type"], [])
                candidates.append(entry)
                if nested:
                    register(definition.get("children", []), catalog, definition_path + "/children", True)

        register(data.get("elements"), elements, "/elements", True)
        register(data.get("connections"), connections, "/connections")
        for index, connection in enumerate(data.get("connections", [])):
            register(connection.get("additionalLabels", []), elements, f"/connections/{index}/additionalLabels")
        evaluation = data.get("evaluation", {})
        if not isinstance(evaluation, dict):
            raise ValueError("language evaluation must be an object")
        configured_groups = evaluation.get("comparisonGroups", [])
        if not isinstance(configured_groups, list):
            raise ValueError("language evaluation comparisonGroups must be an array")
        for group in configured_groups:
            if not isinstance(group, dict) or not isinstance(group.get("id"), str) or not group["id"]:
                raise ValueError("each comparison group needs a non-empty id")
            type_fields = (("elementTypes", "element"), ("connectionTypes", "connection"))
            if not any(field in group for field, _category in type_fields):
                raise ValueError("each comparison group needs elementTypes or connectionTypes")
            for field, category in type_fields:
                configured_types = group.get(field, [])
                if (not isinstance(configured_types, list)
                        or any(not isinstance(value, str) or not value for value in configured_types)):
                    raise ValueError(f"comparison group {field} must be an array of non-empty type names")
                for configured_type in configured_types:
                    key = (category, reference["languageId"], reference["versionId"], configured_type)
                    comparison_groups.setdefault(key, set()).add(group["id"])
        feedback = data.get("feedback", {})
        if not isinstance(feedback, dict) or not isinstance(feedback.get("canvas", {}), dict):
            raise ValueError("language feedback/canvas must be objects")
        entries = feedback.get("canvas", {}).get("configurableElements", [])
        if not isinstance(entries, list):
            raise ValueError("feedback configurableElements must be an array")
        for entry in entries:
            if not isinstance(entry, dict) or not all(isinstance(entry.get(key, {}), dict) for key in ("element", "connection")):
                raise ValueError("invalid feedback element/connection definition")
            for key, target in (("element", feedback_elements), ("connection", feedback_connections)):
                element_type = entry.get(key, {}).get("type")
                if element_type is not None:
                    if not isinstance(element_type, str):
                        raise ValueError("feedback types must be strings")
                    target.add(element_type)
    references.sort(key=lambda ref: (ref["languageId"], ref["versionId"]))
    return elements, connections, feedback_elements, feedback_connections, references, comparison_groups


def parse_model(value: object) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("model"), dict):
        raise ValueError("input.model must be a complete model snapshot")
    model = value["model"]
    if model.get("format", "maxgraph-xml") not in ("maxgraph-xml", "maxgraph-model") or type(model.get("version", 1)) is not int or model.get("version", 1) != 1:
        raise ValueError("unsupported model format/version")
    xml = model.get("xml")
    if not isinstance(xml, str) or not xml.strip():
        raise ValueError("input.model.xml is required")
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("DTD/entity declarations are not supported")
    try:
        document = ET.fromstring(xml)
    except ET.ParseError as error:
        raise ValueError(f"invalid model XML: {error}") from error
    if document.tag != "GraphDataModel" or document.find("root") is None:
        raise ValueError("expected GraphDataModel/root (current maxGraph export)")
    diagnostics = []

    def diagnose(code: str, identities: list[str], message: str, severity: str = "warning", **details) -> None:
        diagnostics.append({"code": code, "severity": severity, "scope": "element" if identities else "model",
                            "message": message, "source": value["source"], "elementIds": sorted(set(identities)), **details})

    cells = {}
    for cell in document.find("root"):
        if cell.tag != "Cell":
            raise ValueError(f"unsupported root entry: {cell.tag}; provide a current maxGraph export")
        identity = cell.get("id")
        if not identity or identity in cells:
            raise ValueError("every Cell needs a unique non-empty id")
        cells[identity] = cell

    children = {}
    for identity, cell in cells.items():
        children.setdefault(cell.get("parent"), []).append(identity)
    roots = children.get(None, [])
    if len(roots) != 1:
        raise ValueError("invalid canvas layer structure: expected exactly one canvas root without a parent")
    root = roots[0]
    layers = children.get(root, [])
    if len(layers) < 2:
        raise ValueError("invalid canvas layer structure: expected modeling and feedback layers as the first two root children")
    modeling_layer, feedback_layer = layers[:2]
    if any(flag(cells[identity].get("vertex")) or flag(cells[identity].get("edge"))
           for identity in (root, modeling_layer, feedback_layer)):
        raise ValueError("invalid canvas layer structure: canvas root and both layers must be infrastructure cells")

    # maxGraph exports children in their stored order, with each subtree in between.
    # The editor assigns the first direct root child to modeling and the second to feedback.
    scope = set()
    pending = list(children.get(modeling_layer, []))
    while pending:
        identity = pending.pop()
        if identity in scope:
            continue
        scope.add(identity)
        pending.extend(children.get(identity, []))

    elements, connections, feedback_elements, feedback_connections, references, comparison_groups = language_catalog(value.get("languages"))
    excluded = set(cells) - scope
    for identity in scope:
        cell = cells[identity]
        style = style_of(cell)
        roles = (cell.get("cellRole"), cell.get("canvasRole"), style.get("cellRole"))
        is_connection = flag(cell.get("edge"))
        catalog = feedback_connections if is_connection else feedback_elements
        model_catalog = connections if is_connection else elements
        cell_type = type_of(cell)
        # A regular definition in an included language prevents type-only exclusion.
        feedback_type = (cell_type in catalog or cell_type == "__feedback_note_link__") and cell_type not in model_catalog
        if "feedback" in roles or feedback_type:
            excluded.add(identity)
    changed = True
    while changed:
        changed = False
        for identity, cell in sorted(cells.items()):
            if identity not in excluded and ((cell.get("parent") != modeling_layer and cell.get("parent") in excluded) or (
                flag(cell.get("edge")) and any(cell.get(end) in excluded for end in ("source", "target")))):
                excluded.add(identity)
                changed = True

    model_cells = {identity: cell for identity, cell in cells.items() if identity not in excluded}
    for identity, cell in cells.items():
        parent_id = cell.get("parent")
        if identity not in model_cells and parent_id is not None and parent_id not in cells:
            is_connection = flag(cell.get("edge"))
            model_catalog = connections if is_connection else elements
            feedback_catalog = feedback_connections if is_connection else feedback_elements
            cell_type = type_of(cell)
            feedback_type = (cell_type in feedback_catalog or cell_type == "__feedback_note_link__") and cell_type not in model_catalog
            roles = (cell.get("cellRole"), cell.get("canvasRole"), style_of(cell).get("cellRole"))
            if ("feedback" in roles or feedback_type
                    or not (flag(cell.get("vertex")) or is_connection or cell_type or "connectionLabelId" in cell.attrib)):
                continue
            diagnose("INVALID_OWNER", [identity], "Parent reference does not name a stored cell.",
                     sourceField="parent", originalParentId=parent_id, nativeType=cell_type or None,
                     label=label_of(cell))
    parents = {identity: None if cell.get("parent") == modeling_layer else cell.get("parent")
               for identity, cell in model_cells.items()}
    nodes, edges = {}, []
    reserved_ids = set(cells)

    def derived_id(kind: str, *parts: str) -> str:
        identity = "@graph:" + json.dumps([kind, *parts], ensure_ascii=False, separators=(",", ":"))
        while identity in reserved_ids:
            identity += ":"
        reserved_ids.add(identity)
        return identity

    definitions: dict[str, DefinitionEntry | None] = {}
    candidates_by_cell: dict[str, list[DefinitionEntry]] = {}
    pinned_by_cell = {}
    bindings = {}
    node_kinds = {}

    def belongs_to(child: DefinitionReference, parent: DefinitionReference, section: str) -> bool:
        return (all(child[key] == parent[key] for key in ("languageId", "versionId"))
                and child["path"].rsplit("/", 2)[0] == parent["path"]
                and child["path"].rsplit("/", 2)[1] == section)

    for identity, cell in sorted(model_cells.items()):
        catalog = connections if flag(cell.get("edge")) else elements
        is_connection_label = cell.get("connectionLabelId") is not None
        candidates = [entry for entry in catalog.get(type_of(cell), [])
                      if ("/additionalLabels/" in entry[0]["path"]) == is_connection_label]
        attributes = object_field(cell, "diagramAttributes")
        language_id = cell.get("languageId", attributes.get("languageId"))
        version_id = cell.get("languageVersionId", attributes.get("languageVersionId"))
        pinned = {"languageId": language_id, "versionId": version_id}
        if language_id is not None or version_id is not None:
            if pinned in references:
                candidates = [entry for entry in candidates if all(entry[0][key] == pinned[key] for key in pinned)]
            else:
                diagnose("INVALID_LANGUAGE_REFERENCE", [identity], "Original language reference is not a supplied version.", language=pinned)
                pinned = None
        else:
            pinned = None
        candidates.sort(key=lambda entry: (entry[0]["languageId"], entry[0]["versionId"], entry[0]["path"]))
        candidates_by_cell[identity] = candidates
        pinned_by_cell[identity] = pinned

    # Resolve parents before declared children, independently of original IDs.
    order = []
    pending = sorted(identity for identity in model_cells if parents[identity] not in model_cells)
    while pending:
        identity = pending.pop()
        order.append(identity)
        pending.extend(sorted(child for child in children.get(identity, []) if child in model_cells))
    # Keep malformed cyclic components available for neutral diagnostics below.
    order.extend(sorted(set(model_cells) - set(order)))
    for identity in order:
        cell = model_cells[identity]
        available = candidates_by_cell[identity]
        independent = [entry for entry in available
                       if "/children/" not in entry[0]["path"] and "/additionalLabels/" not in entry[0]["path"]]
        parent = definitions.get(parents[identity])
        contextual = [entry for entry in available if parent and any(
            belongs_to(entry[0], parent[0], section) for section in ("children", "additionalLabels"))]
        candidates = contextual or independent
        declared_child = bool(contextual) or cell.get("connectionLabelId") is not None or bool(available and not independent)
        entry = candidates[0] if len(candidates) == 1 else None
        if flag(cell.get("edge")):
            node_kind = "connection"
        elif cell.get("connectionLabelId") is not None:
            node_kind = "connectionLabel"
        elif len(contextual) == 1:
            node_kind = "structuralElement"
        elif contextual or (available and not independent):
            node_kind = None
        else:
            node_kind = "modelElement" if type_of(cell) else None
        node_kinds[identity] = node_kind
        definitions[identity] = entry
        remaining = candidates or available
        origins = {(candidate[0]["languageId"], candidate[0]["versionId"]) for candidate in remaining}
        language = pinned_by_cell[identity]
        if len(origins) == 1:
            language_id, version_id = next(iter(origins))
            language = {"languageId": language_id, "versionId": version_id}
        resolution = "resolved" if language else "ambiguous" if origins else "unresolved"
        bindings[identity] = {"language": language, "languageResolution": resolution,
                              "definition": entry[0] if entry else None}
        if not entry and remaining:
            bindings[identity]["definitionCandidates"] = [candidate[0] for candidate in remaining]
        if resolution != "resolved":
            diagnose("AMBIGUOUS_LANGUAGE_ORIGIN" if origins else "UNRESOLVED_LANGUAGE_ORIGIN", [identity],
                     "Language origin cannot be uniquely resolved.",
                     definitionCandidates=bindings[identity].get("definitionCandidates", []))
        if entry is None:
            code = "UNRESOLVED_CHILD_DEFINITION" if declared_child else (
                "AMBIGUOUS_DEFINITION" if candidates else "UNRESOLVED_DEFINITION")
            diagnose(code, [identity],
                     "Declared child cannot be uniquely resolved in its parent context." if declared_child else
                     "Type definition cannot be uniquely resolved.", nativeType=type_of(cell),
                     definitionCandidates=bindings[identity].get("definitionCandidates", []))

    for identity, cell in sorted(model_cells.items()):
        entry = definitions[identity]
        node_kind = node_kinds[identity]
        native_type = type_of(cell)
        properties = scalar_properties(cell)
        for key in ("languageId", "languageVersionId", "comparisonRole"):
            properties.pop(key, None)
        attributes = object_field(cell, "diagramAttributes")
        explicit_role = cell.get("comparisonRole", attributes.get("comparisonRole"))
        if explicit_role is None and entry:
            explicit_role = entry[1].get("comparisonRole")
        if explicit_role is not None and explicit_role not in ("semantic", "structural"):
            diagnose("INVALID_COMPARISON_ROLE", [identity], "Explicit comparison role is not semantic or structural.")
        comparison_role = "semantic" if entry else "unsupported"
        if node_kind == "structuralElement":
            comparison_role = "structural"
        elif node_kind in ("connectionLabel", None):
            comparison_role = "unsupported"
        elif entry and explicit_role in ("semantic", "structural"):
            comparison_role = explicit_role
        language = bindings[identity]["language"]
        group_category = "element" if node_kind == "modelElement" else (
            "connection" if node_kind == "connection" else None
        )
        group_ids = comparison_groups.get(
            (group_category, language["languageId"], language["versionId"], native_type), set()
        ) if group_category and language else set()
        comparison_group = next(iter(group_ids)) if len(group_ids) == 1 else None
        if len(group_ids) > 1:
            type_name = "elementType" if group_category == "element" else "connectionType"
            diagnose("AMBIGUOUS_COMPARISON_GROUP", [identity],
                     f"{type_name.capitalize()} belongs to multiple comparison groups.",
                     language=language, **{type_name: native_type}, comparisonGroupIds=sorted(group_ids))
        nodes[identity] = {"id": identity, "kind": node_kind, "type": native_type or None,
                           "comparisonGroup": comparison_group,
                           "label": label_of(cell), "comparisonRole": comparison_role,
                           **bindings[identity]}
        if properties:
            nodes[identity]["properties"] = properties
        formatting = text_formatting(style_of(cell))
        if formatting is not None:
            nodes[identity].setdefault("properties", {})["textFormatting"] = formatting
        if node_kind == "connectionLabel":
            nodes[identity]["connectionLabelId"] = cell.get("connectionLabelId", "")

    for identity, cell in sorted(model_cells.items()):
        if not flag(cell.get("edge")):
            continue
        entry = definitions[identity]
        definition = entry[1] if entry else {}
        stored_direction = cell.get("connectionUndirected")
        directed = None
        if stored_direction in ("0", "1", "true", "false"):
            directed = not flag(stored_direction)
        elif stored_direction is None and entry and isinstance(definition.get("undirected", False), bool):
            directed = not definition.get("undirected", False)
        if directed is None:
            diagnose("UNRESOLVED_DIRECTION", [identity], "Connection direction cannot be resolved.",
                     sourceField="connectionUndirected")
        nodes[identity]["directed"] = directed
        for end in ("source", "target"):
            terminal = cell.get(end)
            connected = terminal if terminal in nodes else None
            edge = {"id": derived_id("endpoint", identity, end), "source": connected if end == "source" else identity,
                    "target": identity if end == "source" else connected, "kind": "endpoint", "role": end}
            edges.append(edge)
            if connected is None:
                diagnose("OPEN_ENDPOINT", [identity], "Connection endpoint is missing or does not name a model node.",
                         sourceField=end, originalTargetId=terminal)

    for identity in sorted(model_cells):
        parent = parents[identity]
        if node_kinds[identity] == "connectionLabel" and (
                parent not in nodes or node_kinds.get(parent) != "connection"):
            diagnose("INVALID_CONNECTION_LABEL_OWNER", [identity],
                     "Connection label parent does not name a stored connection.",
                     sourceField="parent", originalParentId=model_cells[identity].get("parent"))
        if parent in nodes:
            child_definition = definitions[identity]
            relation = None
            if child_definition:
                path = child_definition[0]["path"]
                if path.count("/") == 2:
                    relation = "content"
                elif "/children/" in path or "/additionalLabels/" in path:
                    relation = "component"
            edges.append({"source": identity, "target": parent, "kind": "contains", "role": relation})
        elif parent is not None:
            diagnose("INVALID_OWNER", [identity], "Parent does not name an available model node.", sourceField="parent", originalParentId=parent)

    visited = set()
    for start in sorted(model_cells):
        chain, active = [], set()
        current = start
        while current in model_cells and current not in visited:
            if current in active:
                diagnose("CONTAINMENT_CYCLE", chain[chain.index(current):], "Containment cycle retained; traversal must bound this area.")
                break
            chain.append(current)
            active.add(current)
            current = parents[current]
        visited.update(chain)

    observed = {(node["language"]["languageId"], node["language"]["versionId"]) for node in nodes.values() if node["language"]}
    if len({language_id for language_id, _ in observed}) > 1:
        diagnose("MULTIPLE_LANGUAGE_ORIGINS", [identity for identity in model_cells if bindings[identity]["language"]], "Elements from multiple language definitions were observed.", "info",
                 languages=[{"languageId": language_id, "versionId": version_id} for language_id, version_id in sorted(observed)])
    diagnostics.sort(key=lambda item: (item["code"], item["elementIds"], content_hash(item)))
    graph: Graph = {"schemaVersion": 3, "languages": references,
                    "nodes": sorted(nodes.values(), key=lambda node: node["id"]),
                    "edges": sorted(edges, key=lambda edge: (edge["kind"], edge["source"] or "", edge["target"] or "", edge["role"] or ""))}
    return {"graph": graph,
            "completeness": {"interpretation": "partial" if any(item["severity"] != "info" for item in diagnostics) else "complete"},
            "diagnostics": diagnostics}
