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


DefinitionEntry = tuple[DefinitionReference, dict]
Scalar = str | int | float | bool | None


class Anchor(TypedDict, total=False):
    cellId: str | None
    pointId: str
    name: str
    groups: list[str]
    role: Literal["input", "output", "bidirectional"]
    x: str | float
    y: str | float
    dx: str
    dy: str
    perimeter: str
    position: dict[str, str]
    pointSource: Literal["language", "model"]


class DefinitionBinding(TypedDict):
    language: LanguageReference | None
    languageResolution: Literal["resolved", "ambiguous", "unresolved"]
    definition: DefinitionReference | None
    definitionCandidates: list[DefinitionReference]


class GraphNode(DefinitionBinding):
    id: str
    kind: Literal["element", "connection"]
    type: str | None
    nativeType: str | None
    label: str
    properties: dict[str, Scalar]
    comparisonRole: Literal["semantic", "structural", "unsupported"]
    origin: dict
    directed: NotRequired[bool | None]


class GraphEdge(TypedDict):
    id: NotRequired[str]
    kind: Literal["contains", "endpoint"]
    type: str | None
    source: str | None
    target: str | None
    directed: bool | None
    label: str
    language: LanguageReference | None
    properties: NotRequired[dict[str, Scalar]]
    origin: NotRequired[dict]
    port: NotRequired[dict]


class Graph(TypedDict):
    schemaVersion: Literal[1]
    languages: list[LanguageReference]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    excluded: list[dict]


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


def label_of(cell: ET.Element) -> str:
    return cell.get("value", object_field(cell, "diagramAttributes").get("label", ""))


def type_of(cell: ET.Element) -> str:
    return cell.get("connectionId", "") if flag(cell.get("edge")) else (
        cell.get("diagramElementType") or object_field(cell, "diagramAttributes").get("type") or cell.get("connectionLabelId", ""))


def language_catalog(languages: object) -> tuple[dict, dict, set, set, list]:
    if not isinstance(languages, list):
        raise ValueError("input.languages must be an array of resolved language versions")
    elements, connections, feedback_elements, feedback_connections, references = {}, {}, set(), set(), []
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
                entry = ({**reference, "path": definition_path}, definition)
                candidates = catalog.setdefault(definition["type"], [])
                candidates.append(entry)
                if nested:
                    register(definition.get("children", []), catalog, definition_path + "/children", True)

        register(data.get("elements"), elements, "/elements", True)
        register(data.get("connections"), connections, "/connections")
        for index, connection in enumerate(data.get("connections", [])):
            register(connection.get("additionalLabels", []), elements, f"/connections/{index}/additionalLabels")
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
    return elements, connections, feedback_elements, feedback_connections, references


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

    elements, connections, feedback_elements, feedback_connections, references = language_catalog(value.get("languages"))
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
    parents = {identity: None if cell.get("parent") == modeling_layer else cell.get("parent")
               for identity, cell in model_cells.items()}
    diagnose("COMPARISON_SCOPE", [],
             "Comparison includes only recursive modeling-layer contents; canvas infrastructure, other layers and feedback are excluded.", "info")
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

    def belongs_to(child: DefinitionReference, parent: DefinitionReference, section: str) -> bool:
        return (all(child[key] == parent[key] for key in ("languageId", "versionId"))
                and child["path"].rsplit("/", 2)[0] == parent["path"]
                and child["path"].rsplit("/", 2)[1] == section)

    for identity, cell in sorted(model_cells.items()):
        catalog = connections if flag(cell.get("edge")) else elements
        candidates = [entry for entry in catalog.get(type_of(cell), [])
                      if ("/additionalLabels/" in entry[0]["path"]) == bool(cell.get("connectionLabelId"))]
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
        declared_child = bool(contextual) or bool(cell.get("connectionLabelId")) or bool(available and not independent)
        entry = candidates[0] if len(candidates) == 1 else None
        definitions[identity] = entry
        remaining = candidates or available
        origins = {(candidate[0]["languageId"], candidate[0]["versionId"]) for candidate in remaining}
        language = pinned_by_cell[identity]
        if len(origins) == 1:
            language_id, version_id = next(iter(origins))
            language = {"languageId": language_id, "versionId": version_id}
        resolution = "resolved" if language else "ambiguous" if origins else "unresolved"
        bindings[identity] = {"language": language, "languageResolution": resolution,
                              "definition": entry[0] if entry else None,
                              "definitionCandidates": [] if entry else [candidate[0] for candidate in remaining]}
        if resolution != "resolved":
            diagnose("AMBIGUOUS_LANGUAGE_ORIGIN" if origins else "UNRESOLVED_LANGUAGE_ORIGIN", [identity],
                     "Language origin cannot be uniquely resolved.", definitionCandidates=bindings[identity]["definitionCandidates"])
        if entry is None:
            code = "UNRESOLVED_CHILD_DEFINITION" if declared_child else (
                "AMBIGUOUS_DEFINITION" if candidates else "UNRESOLVED_DEFINITION")
            diagnose(code, [identity],
                     "Declared child cannot be uniquely resolved in its parent context." if declared_child else
                     "Type definition cannot be uniquely resolved.", nativeType=type_of(cell),
                     definitionCandidates=bindings[identity]["definitionCandidates"])

    def origin(identity: str) -> dict:
        cell = model_cells[identity]
        parent = definitions.get(parents[identity])
        contextual = [entry[0] for entry in candidates_by_cell[identity] if parent and any(
            belongs_to(entry[0], parent[0], section) for section in ("children", "additionalLabels"))]
        return {"cellIds": [identity], "derived": False, "rule": "original-cell/v1",
                "xmlAttributes": dict(cell.attrib), "properties": scalar_properties(cell),
                "contextDefinitionCandidates": contextual}

    for identity, cell in sorted(model_cells.items()):
        entry = definitions[identity]
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
        if entry and explicit_role in ("semantic", "structural"):
            comparison_role = explicit_role
        nodes[identity] = {"id": identity, "kind": "connection" if flag(cell.get("edge")) else "element",
                           "type": entry[1]["type"] if entry else None, "nativeType": type_of(cell) or None,
                           "label": label_of(cell), "properties": properties,
                           "comparisonRole": comparison_role,
                           "origin": origin(identity), **bindings[identity]}

    def anchor(cell: ET.Element, end: str) -> Anchor:
        style = style_of(cell)
        prefix = "exit" if end == "source" else "entry"
        result = {"cellId": cell.get(end)}
        for key, suffix in (("pointId", "PointId"), ("x", "X"), ("y", "Y"),
                            ("dx", "Dx"), ("dy", "Dy"), ("perimeter", "Perimeter")):
            if prefix + suffix in style:
                result[key] = style[prefix + suffix]
        geometry = next((child for child in cell if child.get("as") == "geometry"), None)
        if geometry is not None:
            point = next((child for child in geometry if child.get("as") == end + "Point"), None)
            if point is not None:
                result["position"] = {axis: point.get("_" + axis, point.get(axis, "0")) for axis in ("x", "y")}

        entry = definitions.get(cell.get(end))
        points = entry[1].get("anchorPoints", []) if entry else []
        point_source = "language"
        # Retain instance anchor metadata when no definition could be resolved.
        if not entry and cell.get(end) in cells:
            try:
                points = json.loads(cells[cell.get(end)].get("connectionPointsJson", "[]"))
            except (ValueError, TypeError):
                points = []
            point_source = "model"

        def number_text(value: object) -> str:
            # Legacy editor IDs omit .0 for integers; keep other coordinates precise.
            return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)

        def point_id(point: dict) -> str:
            return point.get("id") or f"point-{number_text(point.get('x'))}-{number_text(point.get('y'))}"

        def matches(point: dict) -> bool:
            if result.get("pointId"):
                return point_id(point) == result["pointId"]
            try:
                return all(abs(float(result[axis]) - float(point[axis])) < 0.000001 for axis in ("x", "y"))
            except (KeyError, TypeError, ValueError):
                return False

        matches_found = [point for point in points if isinstance(point, dict) and matches(point)] if isinstance(points, list) else []
        if len(matches_found) == 1:
            point = matches_found[0]
            result["pointId"] = point_id(point)
            result["pointSource"] = point_source
            for key in ("name", "groups", "role"):
                if key in point:
                    result[key] = point[key]
            for axis in ("x", "y"):
                if axis in point:
                    result.setdefault(axis, point[axis])
        return result

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
            diagnose("UNRESOLVED_DIRECTION", [identity], "Connection direction cannot be resolved.", sourceField="connectionUndirected")
        nodes[identity]["directed"] = directed
        nodes[identity]["origin"]["storedUndirected"] = stored_direction
        for end in ("source", "target"):
            terminal = cell.get(end)
            connected = terminal if terminal in nodes else None
            metadata = anchor(cell, end)
            edge = {"id": derived_id("endpoint", identity, end), "source": connected if end == "source" else identity,
                    "target": identity if end == "source" else connected, "kind": "endpoint", "type": end,
                    "directed": True, "label": "", "language": None, "properties": {},
                    "origin": {"cellIds": [identity], "sourceField": end, "derived": True, "rule": "connection-endpoint/v1", "anchor": metadata}}
            if metadata.get("pointSource") == "language":
                port = {key: metadata[key] for key in ("pointId", "name", "groups", "role") if key in metadata}
                if set(port) - {"pointId"}:
                    edge["port"] = port
            edges.append(edge)
            if connected is None:
                diagnose("OPEN_ENDPOINT", [identity], "Connection endpoint is missing or does not name a model node.",
                         sourceField=end, originalTargetId=terminal)

    for identity in sorted(model_cells):
        parent = parents[identity]
        if parent in nodes:
            child_definition = definitions[identity]
            relation = None
            if child_definition:
                path = child_definition[0]["path"]
                if path.count("/") == 2:
                    relation = "content"
                elif "/children/" in path or "/additionalLabels/" in path:
                    relation = "component"
            edges.append({"source": parent, "target": identity,
                          "kind": "contains", "type": relation, "directed": True, "label": "",
                          "language": None})
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
    graph: Graph = {"schemaVersion": 1, "languages": references,
                    "nodes": sorted(nodes.values(), key=lambda node: node["id"]),
                    "edges": sorted(edges, key=lambda edge: (edge["kind"], edge["source"] or "", edge["target"] or "", edge["type"] or "")),
                    "excluded": []}
    return {"graph": graph,
            "completeness": {"interpretation": "partial" if any(item["severity"] != "info" for item in diagnostics) else "complete"},
            "diagnostics": diagnostics}
