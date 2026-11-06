"""Normalize maxGraph snapshots without validating the modeled content."""
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


class Endpoints(TypedDict, total=False):
    source: Anchor
    target: Anchor


class DefinitionBinding(TypedDict):
    language: LanguageReference | None
    definition: DefinitionReference | None
    definitionCandidates: list[DefinitionReference]


class GraphNode(DefinitionBinding):
    id: str
    kind: Literal["element", "connection"]
    type: str
    label: str
    parentId: str | None
    properties: dict[str, Scalar]
    directed: NotRequired[bool | None]
    storedUndirected: NotRequired[str | None]


class GraphEdge(TypedDict):
    id: str
    kind: Literal["contains", "connection", "endpoint"]
    type: str
    source: str | None
    target: str | None
    directed: bool | None
    label: str
    language: LanguageReference | None
    properties: dict[str, Scalar]
    definition: NotRequired[DefinitionReference | None]
    definitionCandidates: NotRequired[list[DefinitionReference]]
    role: NotRequired[Literal["structural"]]
    relation: NotRequired[Literal["component", "content"] | None]
    parentId: NotRequired[str | None]
    storedUndirected: NotRequired[str | None]
    originId: NotRequired[str]
    endpoints: NotRequired[Endpoints]


class Graph(TypedDict):
    schemaVersion: Literal[2]
    languages: list[LanguageReference]
    nodes: list[GraphNode]
    edges: list[GraphEdge]


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


def parse_model(value: object) -> Graph:
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
    elements, connections, feedback_elements, feedback_connections, references = language_catalog(value.get("languages"))
    cells = {}
    for cell in document.find("root"):
        if cell.tag != "Cell":
            raise ValueError(f"unsupported root entry: {cell.tag}; provide a current maxGraph export")
        identity = cell.get("id")
        if not identity or identity in cells:
            raise ValueError("every Cell needs a unique non-empty id")
        cells[identity] = cell

    excluded = set()
    for identity, cell in cells.items():
        style = style_of(cell)
        roles = (cell.get("cellRole"), cell.get("canvasRole"), style.get("cellRole"))
        catalog = feedback_connections if flag(cell.get("edge")) else feedback_elements
        if "feedback" in roles or type_of(cell) in catalog or type_of(cell) == "__feedback_note_link__":
            excluded.add(identity)
    # Descendants and connections touching excluded content are excluded as well.
    changed = True
    while changed:
        changed = False
        for identity, cell in cells.items():
            if identity not in excluded and (cell.get("parent") in excluded or (
                flag(cell.get("edge")) and any(cell.get(end) in excluded for end in ("source", "target")))):
                excluded.add(identity)
                changed = True

    retained = {identity: cell for identity, cell in cells.items() if identity not in excluded}
    model_cells = {identity: cell for identity, cell in retained.items()
                   if flag(cell.get("vertex")) or flag(cell.get("edge")) or type_of(cell)}

    def model_parent(cell: ET.Element) -> str | None:
        parent, visited = cell.get("parent"), set()
        # Root/layer cells are transparent. Keep malformed parent cycles finite.
        while parent in retained and parent not in model_cells:
            if parent in visited:
                return None
            visited.add(parent)
            parent = retained[parent].get("parent")
        return parent

    parents = {identity: model_parent(cell) for identity, cell in model_cells.items()}
    # A connection with children, or serving as another connection's terminal,
    # needs a node representation to keep the output an ordinary multigraph.
    # Connections inside model containers also need an addressable contains target.
    relation_nodes = {parent for parent in parents.values()
                      if parent in model_cells and flag(model_cells[parent].get("edge"))}
    relation_nodes.update(identity for identity, cell in model_cells.items()
                          if flag(cell.get("edge")) and parents[identity] in model_cells)
    relation_nodes.update(cell.get(end) for cell in model_cells.values() if flag(cell.get("edge"))
                          for end in ("source", "target") if cell.get(end) in model_cells and flag(model_cells[cell.get(end)].get("edge")))
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

    def candidates_for(cell: ET.Element) -> list[DefinitionEntry]:
        catalog = connections if flag(cell.get("edge")) else elements
        candidates = catalog.get(type_of(cell), [])
        return [entry for entry in candidates
                if ("/additionalLabels/" in entry[0]["path"]) == bool(cell.get("connectionLabelId"))]

    def belongs_to(child: DefinitionReference, parent: DefinitionReference, section: str) -> bool:
        return (all(child[key] == parent[key] for key in ("languageId", "versionId"))
                and child["path"].rsplit("/", 2)[0] == parent["path"]
                and child["path"].rsplit("/", 2)[1] == section)

    def resolve_definition(identity: str) -> None:
        cell = model_cells[identity]
        candidates = candidates_for(cell)
        parent = definitions.get(parents[identity])
        section = "additionalLabels" if cell.get("connectionLabelId") else "children"
        contextual = [entry for entry in candidates if parent and belongs_to(entry[0], parent[0], section)]
        roots = [entry for entry in candidates if entry[0]["path"].count("/") == 2]
        if parent is None:
            possible_parents = candidates_by_cell.get(parents[identity], [])
            possible_children = [entry for entry in candidates
                                 if any(belongs_to(entry[0], possible[0], section) for possible in possible_parents)]
            if possible_children:
                candidates_by_cell[identity] = possible_children + roots
                definitions[identity] = None
                return
        selected = contextual or roots
        candidates_by_cell[identity] = selected or candidates
        definitions[identity] = selected[0] if len(selected) == 1 else None

    # Resolve parents first, independently of XML order and cell IDs. Cycles stay
    # in the graph; they only prevent a context-dependent definition lookup.
    for start in sorted(model_cells):
        chain, active = [], set()
        current = start
        while current in model_cells and current not in definitions:
            if current in active:
                for identity in chain[chain.index(current):]:
                    definitions[identity] = None
                    candidates_by_cell[identity] = candidates_for(model_cells[identity])
                break
            chain.append(current)
            active.add(current)
            current = parents[current]
        for identity in reversed(chain):
            if identity not in definitions:
                resolve_definition(identity)

    def binding(identity: str) -> DefinitionBinding:
        entry = definitions[identity]
        result = {"language": {key: entry[0][key] for key in ("languageId", "versionId")} if entry else None,
                  "definition": entry[0] if entry else None,
                  "definitionCandidates": [] if entry else [candidate[0] for candidate in candidates_by_cell[identity]]}
        return result

    for identity, cell in sorted(model_cells.items()):
        if not flag(cell.get("edge")) or identity in relation_nodes:
            nodes[identity] = {"id": identity, "kind": "connection" if flag(cell.get("edge")) else "element",
                               "type": type_of(cell) or "__unknown__", "label": label_of(cell),
                               "parentId": cell.get("parent"), "properties": scalar_properties(cell), **binding(identity)}

    def anchor(cell: ET.Element, end: str) -> dict:
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
        source, target = (cell.get(end) if cell.get(end) in nodes else None for end in ("source", "target"))
        endpoints = {end: anchor(cell, end) for end in ("source", "target")}
        if identity in relation_nodes:
            nodes[identity]["directed"] = directed
            nodes[identity]["storedUndirected"] = stored_direction
            for end, start, finish in (("source", source, identity), ("target", identity, target)):
                edges.append({"id": derived_id("endpoint", identity, end), "source": start, "target": finish,
                              "kind": "endpoint", "type": end, "directed": True, "label": "",
                              "role": "structural", "language": None, "properties": {}, "originId": identity,
                              "endpoints": {end: endpoints[end]}})
        else:
            edges.append({"id": identity, "source": source, "target": target, "kind": "connection",
                          "type": type_of(cell) or "__unknown__", "directed": directed, "label": label_of(cell),
                          "parentId": cell.get("parent"), "storedUndirected": stored_direction,
                          "properties": scalar_properties(cell), "endpoints": endpoints, **binding(identity)})

    for identity in sorted(nodes):
        parent = parents[identity]
        if parent in nodes:
            child_definition, parent_definition = definitions[identity], definitions[parent]
            relation = None
            if child_definition:
                path = child_definition[0]["path"]
                if path.count("/") == 2:
                    relation = "content"
                elif parent_definition and any(belongs_to(child_definition[0], parent_definition[0], section)
                                               for section in ("children", "additionalLabels")):
                    relation = "component"
            edges.append({"id": derived_id("contains", parent, identity), "source": parent, "target": identity,
                          "kind": "contains", "type": "contains", "directed": True, "label": "",
                          "role": "structural", "relation": relation,
                          "language": None, "properties": {}, "originId": identity})

    return {"schemaVersion": 2, "languages": references,
            "nodes": list(nodes.values()), "edges": sorted(edges, key=lambda edge: edge["id"])}
