"""Draft maxGraph adapter. Only containment is a forest; connections are unrestricted."""
import json
import xml.etree.ElementTree as ET


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

        def register(definitions: object, catalog: dict, nested: bool = False) -> None:
            if not isinstance(definitions, list):
                raise ValueError("language elements/connections/children must be arrays")
            for definition in definitions:
                if not isinstance(definition, dict) or not isinstance(definition.get("type"), str) or not definition["type"]:
                    raise ValueError("each language definition needs a non-empty type")
                entry = (reference, definition)
                candidates = catalog.setdefault(definition["type"], [])
                # A child type may occur in multiple compositions of one language.
                if entry not in candidates:
                    candidates.append(entry)
                if nested:
                    register(definition.get("children", []), catalog, True)

        register(data.get("elements"), elements, True)
        register(data.get("connections"), connections)
        for connection in data.get("connections", []):
            if "undirected" in connection and not isinstance(connection["undirected"], bool):
                raise ValueError("connection.undirected must be boolean")
            register(connection.get("additionalLabels", []), elements)
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


def parse_model(value: object) -> tuple[dict, list]:
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

    diagnostics = []

    def diagnose(code: str, cell_id: str, message: str, severity: str = "error", **details: object) -> None:
        diagnostics.append({"severity": severity, "code": code, "cellId": cell_id, "message": message, "details": details})

    # Reject cycles, including cycles hidden by technical/feedback cells.
    visited = set()
    for start in sorted(cells):
        path = set()
        current = start
        while current in cells and current not in visited:
            if current in path:
                raise ValueError(f"containment cycle at Cell {current}")
            path.add(current)
            current = cells[current].get("parent")
        visited.update(path)

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
    # A connection with children, or serving as another connection's terminal,
    # needs a node representation to keep the output an ordinary multigraph.
    relation_nodes = {cell.get("parent") for cell in model_cells.values()
                      if cell.get("parent") in model_cells and flag(model_cells[cell.get("parent")].get("edge"))}
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

    def definition_for(identity: str, cell: ET.Element) -> tuple[dict | None, dict]:
        catalog = connections if flag(cell.get("edge")) else elements
        candidates = catalog.get(type_of(cell), [])
        # Label type names (e.g. 'role') can be shared across languages. A label
        # belongs to its parent connection's definition, not to the global set.
        parent = cells.get(cell.get("parent"))
        if cell.get("connectionLabelId") and parent is not None and flag(parent.get("edge")):
            candidates = [(reference, label)
                          for reference, connection in connections.get(type_of(parent), [])
                          for label in connection.get("additionalLabels", [])
                          if label["type"] == type_of(cell)]
        owners = {(entry[0]["languageId"], entry[0]["versionId"]) for entry in candidates}
        if len(owners) != 1:
            diagnose("unknown_type" if not candidates else "ambiguous_type", identity,
                     "Element type is missing/unknown or belongs to multiple language versions.", type=type_of(cell))
            return None, {}
        reference = candidates[0][0]
        if flag(cell.get("edge")) and len({entry[1].get("undirected", False) for entry in candidates}) > 1:
            diagnose("ambiguous_direction", identity, "Connection definitions disagree about direction.")
            return reference, {}
        return reference, candidates[0][1]

    definitions = {}
    for identity, cell in sorted(model_cells.items()):
        definitions[identity] = definition_for(identity, cell)
        if not flag(cell.get("edge")) or identity in relation_nodes:
            reference, _ = definitions[identity]
            nodes[identity] = {"id": identity, "kind": "connection" if flag(cell.get("edge")) else "element",
                               "type": type_of(cell) or "__unknown__", "label": label_of(cell),
                               "language": reference, "properties": scalar_properties(cell)}

    def terminal(identity: str, cell: ET.Element, end: str) -> str | None:
        target = cell.get(end)
        if target in nodes:
            return target
        diagnose("invalid_endpoint", identity, "Connection endpoint is missing or not an addressable model node.", endpoint=end, originalId=target)
        return None

    def anchor(cell: ET.Element, end: str) -> dict:
        style = style_of(cell)
        prefix = "exit" if end == "source" else "entry"
        if style.get(prefix + "PointId"):
            result = {"pointId": style[prefix + "PointId"]}
            endpoint_id = cell.get(end)
            if endpoint_id in definitions:
                points = definitions[endpoint_id][1].get("anchorPoints", [])
                for point in points if isinstance(points, list) else []:
                    if not isinstance(point, dict):
                        continue
                    point_id = point.get("id", f"point-{point.get('x')}-{point.get('y')}")
                    if point_id == result["pointId"] and point.get("role") in ("input", "output", "bidirectional"):
                        result["role"] = point["role"]
            return result
        # Older exports can lack point IDs; retain anchor coordinates as fallback.
        return {key: style[prefix + suffix] for key, suffix in (("x", "X"), ("y", "Y")) if prefix + suffix in style}

    for identity, cell in sorted(model_cells.items()):
        if not flag(cell.get("edge")):
            continue
        reference, definition = definitions[identity]
        stored_direction = cell.get("connectionUndirected")
        directed = not flag(stored_direction) if stored_direction is not None else (not definition.get("undirected", False) if definition else None)
        if stored_direction is not None and stored_direction not in ("0", "1", "true", "false"):
            directed = None
        if directed is None:
            diagnose("unknown_direction", identity, "No valid stored direction or unambiguous connection definition.")
        elif stored_direction is not None and definition and directed == definition.get("undirected", False):
            diagnose("direction_conflict", identity, "Stored direction differs from the pinned language; stored value retained.")
        source, target = terminal(identity, cell, "source"), terminal(identity, cell, "target")
        endpoints = {end: anchor(cell, end) for end in ("source", "target")}
        if identity in relation_nodes:
            nodes[identity]["directed"] = directed
            for end, start, finish in (("source", source, identity), ("target", identity, target)):
                edges.append({"id": derived_id("endpoint", identity, end), "source": start, "target": finish,
                              "kind": "endpoint", "type": end, "directed": directed, "label": "",
                              "language": None, "properties": {}, "originId": identity, "endpoints": {end: endpoints[end]}})
        else:
            edges.append({"id": identity, "source": source, "target": target, "kind": "connection",
                          "type": type_of(cell) or "__unknown__", "directed": directed, "label": label_of(cell),
                          "language": reference, "properties": scalar_properties(cell), "endpoints": endpoints})

    for identity in sorted(nodes):
        parent = cells[identity].get("parent")
        # Technical root/layer cells are transparent, never semantic containers.
        while parent in retained and parent not in nodes:
            parent = retained[parent].get("parent")
        if parent in nodes:
            edges.append({"id": derived_id("contains", parent, identity), "source": parent, "target": identity,
                          "kind": "contains", "type": "contains", "directed": True, "label": "",
                          "language": None, "properties": {}, "originId": identity})
        elif parent is not None or cells[identity].get("parent") is None:
            diagnose("missing_parent", identity, "Original containment parent is absent; no parent invented.", originalId=parent)

    diagnostics.sort(key=lambda item: (item["cellId"], item["code"], json.dumps(item["details"], sort_keys=True)))
    graph = {"schemaVersion": 1, "languages": references, "complete": not any(item["severity"] == "error" for item in diagnostics),
             "nodes": list(nodes.values()), "edges": sorted(edges, key=lambda edge: edge["id"])}
    return graph, diagnostics
