"""Need-based help feedback for marked submission objects.

Reads only matcher facts, identities and reference hints of the analytical feedback; it never decides
identity or correctness itself. Each help type has a fixed disclosure level (LEVELS); reference labels
leave this module only at level "labels".
"""

import copy
import re
from xml.etree import ElementTree

from analysis_contract import content_hash, require

# Fixed per help type: how much of the sample solution the answer may reveal.
LEVELS = {"help.clarify": "diagnosis", "help.check": "diagnosis", "help.next_step": "labels",
          "help.example": "labels", "help.solution": "labels"}
AREAS = ("hierarchy", "connection", "type", "children", "connections", "completeness", "label")  # focus priority
AREA_NAMES = {"hierarchy": "Zuordnung zum übergeordneten Element", "connection": "Verbindung (Start, Ziel, Richtung)",
              "type": "Elementtyp", "children": "Untergeordnete Elemente", "connections": "Anzahl der Verbindungen",
              "completeness": "Vollständigkeit", "label": "Beschriftung"}
PREFIX_AREAS = {"label": "label", "type": "type", "owner": "hierarchy", "containment": "hierarchy",
                "children": "children", "direct_children": "children", "connections": "connections",
                "incoming": "connections", "outgoing": "connections", "undirected": "connections",
                "connection": "connection", "connection_group": "connection", "counterpart": "completeness"}
STATUSES = {"satisfied": "matches", "violated": "differs", "unresolved": "unclear"}
PROVEN_BASES = ("direct_observation", "independent_evidence")
IDENTITIES = {"uniquely_supported": "recognized", "supported": "provisional", "unresolved": "unassigned"}

DIFFERS = {
    "label": "Die Beschriftung von {name} passt nicht zur Musterlösung.",
    "type": "{name} hat einen anderen Elementtyp als in der Musterlösung.",
    "hierarchy": "{name} gehört in der Musterlösung zu einem anderen Element.",
    "children": "Die Elemente, die zu {name} gehören, unterscheiden sich von der Musterlösung{counts}.",
    "connections": "Die Verbindungen von {name} unterscheiden sich von der Musterlösung{counts}.",
    "connection": "Bei {name} stimmen Start, Ziel oder Richtung nicht mit der Musterlösung überein.",
    "completeness": "Bei {name} fehlt noch mindestens ein Element{counts}.",
}
NEXT_STEPS = {
    "label": "Vergleiche die Beschriftung von {name} mit den Begriffen aus der Aufgabe.",
    "type": "Überlege, welcher Elementtyp zu {name} passt.",
    "hierarchy": "Überlege, zu welchem Element {name} gehört.",
    "children": "Schau nach, welche Elemente zu {name} gehören: Fehlt etwas oder hängt etwas am falschen Element?",
    "connections": "Überlege, mit welchen Elementen {name} verbunden sein sollte.",
    "connection": "Schau dir Start, Ziel und Richtung von {name} an.",
    "completeness": "Lies in der Aufgabe nach, was bei {name} noch fehlt.",
}


def clean(label: str) -> str:
    """Diagram line breaks are layout: a break before a lowercase letter splits a word, others separate words."""
    return " ".join(re.sub(r"-?\s*\n\s*(?=[a-zäöüß])", "", label).split())


def validate_context(context: dict) -> dict:
    marked, previous = context.get("markedIds"), context.get("previousIssueKeys", [])
    require(set(context) <= {"markedIds", "previousIssueKeys"}, "unsupported help feedback context")
    require(isinstance(marked, list) and 0 < len(marked) <= 200 and len(set(marked)) == len(marked)
            and all(isinstance(item, str) and 0 < len(item) <= 256 for item in marked),
            "help feedback needs 1 to 200 unique markedIds")
    require(isinstance(previous, list) and len(previous) <= 500 and all(isinstance(item, str) for item in previous),
            "previousIssueKeys must be a list of strings")
    return {"markedIds": marked, "previousIssueKeys": set(previous)}


class Model:
    """Student-facing names and the reference-to-submission identities the matcher proved."""

    def __init__(self, analysis: dict, store, bundle: dict):
        self.analysis = analysis
        reference_key = analysis["pair"]["referenceKey"]
        submission = store.read("graphs/submission.json")["result"]["graph"]
        reference = store.read(f"graphs/{reference_key}.json")["result"]["graph"]
        self.nodes = {node["id"]: node for node in submission["nodes"]}
        self.reference_nodes = {node["id"]: node for node in reference["nodes"]}
        # Containment (child -> parent) and connection ends (connection -> role -> element) of both graphs.
        self.parents, self.ends, self.reference_ends = {}, {}, {}
        for edges, ends, parents in ((submission["edges"], self.ends, self.parents), (reference["edges"], self.reference_ends, None)):
            for row in edges:
                if row.get("kind") == "endpoint":  # follows the flow: element -> connection (source), connection -> element (target)
                    connection, element = (row["target"], row["source"]) if row.get("role") == "source" else (row["source"], row["target"])
                    ends.setdefault(connection, {})[row.get("role")] = element
                elif row.get("kind") == "contains" and parents is not None:
                    parents[row["source"]] = row["target"]
        self.annotations = {row["target"]["id"]: row for row in analysis["annotations"]}
        self.proven = {row["referenceId"]: sub for sub, row in self.annotations.items()
                       if row.get("referenceId") and row.get("identity", {}).get("status") == "uniquely_supported"}
        self.type_names, self.languages = {}, bundle["languages"]
        def xml(key):
            source = next((row["snapshot"].get("data", {}) for row in bundle.get("models", [])
                           if row.get("source", {}).get("key") == key), {})
            return ElementTree.fromstring(source["xml"]).find("root") if isinstance(source.get("xml"), str) else None
        # Trusted input from the API's frozen evaluation input (stored maxGraph XML of the sample solution).
        self.reference_xml = xml(reference_key)
        for language in bundle["languages"]:
            for item in [*language["data"].get("elements", []), *language["data"].get("connections", [])]:
                if isinstance(item, dict) and item.get("type"):
                    self.type_names.setdefault(item["type"], item.get("defaultLabel") or item.get("label") or item.get("name") or item["type"])

    def type_name(self, native_type) -> str:
        return self.type_names.get(native_type, native_type or "Element")

    def definition(self, node: dict) -> dict | None:
        """Language definition the parser resolved for a node (its `definition.path`), for rendering a preview."""
        ref = node.get("definition") or {}
        language = next((row for row in self.languages if row.get("languageId") == ref.get("languageId")
                         and row.get("versionId") == ref.get("versionId")), None)
        item = language and language["data"]
        for part in (ref.get("path") or "").strip("/").split("/") if item else []:
            if isinstance(item, list) and part.isdigit() and int(part) < len(item):
                item = item[int(part)]
            elif isinstance(item, dict) and part in item:
                item = item[part]
            else:
                return None
        return item if isinstance(item, dict) else None

    def name(self, cell_id: str) -> str:
        node = self.nodes.get(cell_id, {})
        label = clean(node.get("label") or "")
        ends = self.ends.get(cell_id, {})
        if not label and node.get("kind") == "connection" and len(ends) == 2:
            # An unlabeled connection is known by its ends; the arrow shows its direction.
            return f"Verbindung {self.name(ends['source'])} {'→' if node.get('directed', True) else '–'} {self.name(ends['target'])}"
        # Fits every sentence position ("von …", "Verbindung …"), unlike an article phrase.
        return f"„{label}“" if label else f"„{self.type_name(node.get('type'))}“ (unbeschriftet)"


def subject(name: str) -> str:
    """A name at the start of a sentence: an unlabeled connection gets its article."""
    return f"Die {name}" if name.startswith("Verbindung ") else name


def articles(text: str) -> str:
    """Article for an unlabeled connection's name inside a sentence ("bei der Verbindung „A“ → „B“")."""
    return re.sub(r"\b([Bb]ei|von|zu|mit) Verbindung „", r"\1 der Verbindung „", re.sub(r"\b(Lass) Verbindung „", r"\1 die Verbindung „", text))


def area_of(code: str, kind: str) -> str | None:
    prefix = code.split(".")[0]
    if prefix == "type" and kind == "connection":
        return "connection"
    return PREFIX_AREAS.get(prefix)


def counts(evidence: dict, disclosure: str) -> str:
    if disclosure == "diagnosis" or not isinstance(evidence.get("expected"), int) or not isinstance(evidence.get("observed"), int):
        return ""
    if evidence["expected"] == evidence["observed"]:
        return " (die Anzahl stimmt, aber nicht alle passen)"
    return f" (bei dir {evidence['observed']}, in der Musterlösung {evidence['expected']})"


def findings(model: Model, cell_id: str, index: int, disclosure: str) -> tuple[dict, list[dict]]:
    """One learner object plus its distinct findings; equal finding IDs are reported once."""
    node = model.nodes.get(cell_id)
    entry = {"cellId": cell_id, "label": (node or {}).get("label") or "", "kind": (node or {}).get("kind"),
             "identity": "not_evaluated", "checks": [], "notEvaluated": 0}
    if node is None:
        return entry, []
    annotation = model.annotations.get(cell_id)
    if annotation is None or node.get("kind") == "structuralElement":  # containers are layout, never matched
        return entry, []
    identity = annotation.get("identity", {}).get("status")
    entry["identity"] = IDENTITIES.get(identity, "provisional" if annotation.get("referenceId") else "unassigned")
    name, items, seen = model.name(cell_id), [], set()
    facts = list(annotation["facts"])
    facts += [fact for group in model.analysis["connectionGroups"] if cell_id in group["submissionIds"] for fact in group["facts"]]
    for fact in facts:
        area = area_of(fact["code"], node["kind"])
        status = STATUSES.get(fact["status"])
        values = fact["evidence"]
        if fact["code"] == "label.different" and isinstance(values.get("referenceValue"), str) and isinstance(values.get("submissionValue"), str) \
                and "".join(values["referenceValue"].split()).casefold() == "".join(values["submissionValue"].split()).casefold():
            status = "matches"  # differs only by layout line breaks, spaces or case
        key = fact["evidence"].get("findingId", fact["id"])
        if area is None or key in seen:
            continue
        seen.add(key)
        if status is None:
            entry["notEvaluated"] += 1
            continue
        proven = fact["evidence"].get("basis") in PROVEN_BASES or identity == "uniquely_supported"
        items.append({"area": area, "status": status, "certainty": "proven" if proven else "conditional",
                      "fact": fact, "cellId": cell_id, "index": index, "name": name,
                      "issueKey": content_hash({"code": fact["code"], "submissionIds": sorted(fact["submissionIds"])})})
    missing = [hint for hint in model.analysis["referenceHints"]
               if hint["target"]["id"] == cell_id and hint["code"] == "reference.missing"]
    for hint in missing:
        fact = next((item for item in hint["facts"] if item["code"] == "counterpart.missing"), None)
        proven = fact is not None and fact["evidence"].get("basis") in PROVEN_BASES
        items.append({"area": "completeness", "status": "differs", "certainty": "proven" if proven else "conditional",
                      "fact": fact or {"id": hint["referenceId"], "code": "reference.missing", "evidence": {}},
                      "hint": hint, "cellId": cell_id, "index": index, "name": name,
                      "issueKey": content_hash({"code": "reference.missing", "referenceId": hint["referenceId"]})})
    unresolved = sum(hint["target"]["id"] == cell_id and hint["code"] == "reference.unresolved" for hint in model.analysis["referenceHints"])
    if unresolved:
        items.append({"area": "completeness", "status": "unclear", "certainty": "conditional", "fact": {"id": "", "evidence": {}},
                      "cellId": cell_id, "index": index, "name": name, "unresolved": unresolved,
                      "issueKey": content_hash({"code": "reference.unresolved", "cellId": cell_id})})
    # Related findings (e.g. incoming/outgoing/all connections) form one check per area.
    for area in AREAS:
        related = [item for item in items if item["area"] == area]
        if not related:
            continue
        status = next(value for value in ("differs", "unclear", "matches") if any(item["status"] == value for item in related))
        chosen = [item for item in related if item["status"] == status]
        best = next((item for item in chosen if isinstance(item["fact"]["evidence"].get("expected"), int)), chosen[0])
        certainty = "proven" if any(item["certainty"] == "proven" for item in chosen) else "conditional"
        text = check_text({**best, "certainty": certainty}, disclosure)
        if area == "completeness" and status == "differs" and disclosure != "diagnosis":
            text = f"Bei {name} fehlen noch Elemente oder Verbindungen ({len(chosen)})."
        entry["checks"].append({"area": area, "status": status, "certainty": certainty,
                                "messageCode": f"{area}.{status}", "text": articles(text)})
    return entry, items


def check_text(item: dict, disclosure: str) -> str:
    area, name = item["area"], item["name"]
    if item["status"] == "matches":
        return f"{AREA_NAMES[area]}: passt."
    if item["status"] == "unclear":
        if item.get("unresolved"):
            return f"Bei {name} ist unklar, ob noch etwas fehlt oder ob es nur anders modelliert ist."
        return f"{AREA_NAMES[area]}: lässt sich nicht sicher bewerten."
    text = subject(DIFFERS[area].format(name=name, counts="" if area == "completeness" else counts(item["fact"]["evidence"], disclosure)))
    if item["certainty"] == "conditional":
        text += " Das ist noch nicht ganz sicher, weil die Zuordnung vorläufig ist."
    return text


def verdict_of(checks: list[dict]) -> str:
    statuses = {check["status"] for check in checks}
    return next((status for status in ("differs", "unclear", "matches") if status in statuses), "not_evaluated")


# Countable parts of one object: (label, fact codes in preference order); the first present code counts.
SCORE_PARTS = (("Elementtyp", ("type.equal", "type.different")),
               ("Untergeordnete Elemente", ("children.complete", "direct_children.complete")),
               ("Eingehende Verbindungen", ("incoming.complete",)),
               ("Ausgehende Verbindungen", ("outgoing.complete",)),
               ("Ungerichtete Verbindungen", ("undirected.complete",)),
               ("Quelle", ("connection.source",)), ("Ziel", ("connection.target",)), ("Richtung", ("connection.direction",)))


def score(model: Model, cell_id: str, identity: str) -> dict | None:
    """Quantitative completeness of one object: present versus expected per part, without naming the targets."""
    annotation = model.annotations.get(cell_id)
    if annotation is None or identity == "not_evaluated":
        return None
    facts = {}
    for fact in annotation["facts"]:
        facts.setdefault(fact["code"], fact)
    found = identity in ("recognized", "provisional")
    # A label the matcher assigned counts as recognized; the closest text similarity shows how close it is.
    criteria = annotation.get("identity", {}).get("criteria", [])
    exact = any(row.get("method") == "exact_label" and row.get("result") == "satisfied" for row in criteria)
    scores = [value for row in criteria if row.get("method") == "text_similarity"
              for value in row.get("scores", {}).values() if isinstance(value, (int, float))]
    label_text = "nicht erkannt" if not found else "erkannt (exakt)" if exact else \
        f"erkannt (Ähnlichkeit {round(100 * max(scores))} %)" if scores else "erkannt"
    parts = [{"label": "Beschriftung", "present": int(found), "expected": 1, "text": label_text}]
    # Explanation only: why the object is not assigned, never what to do about it.
    hint = None if found else (f"{model.name(cell_id)} konnte keinem Element der Musterlösung zugeordnet werden."
                               if clean(model.nodes[cell_id].get("label") or "") else
                               "Das Element hat keine Beschriftung und konnte deshalb keinem Element der Musterlösung zugeordnet werden.")
    for label, codes in SCORE_PARTS:
        fact = next((facts[code] for code in codes if code in facts), None)
        if fact is None or fact["status"] not in STATUSES:
            continue
        expected, observed = fact["evidence"].get("expected"), fact["evidence"].get("observed")
        if isinstance(expected, int) and isinstance(observed, int):
            if expected:  # nothing expected: no measurable part
                parts.append({"label": label, "present": min(observed, expected), "expected": expected})
        else:
            ok = fact["status"] == "satisfied"
            parts.append({"label": label, "present": int(ok), "expected": 1,
                          "text": ("korrekt" if ok else "abweichend") if fact["status"] != "unresolved" else "unklar"})
    total = sum(part["expected"] for part in parts)
    return {"percent": round(100 * sum(part["present"] for part in parts) / total, 1), "parts": parts, "hint": hint}


def clarify_feedback(model: Model, context: dict) -> dict:
    """Status and quantitative completeness per marked object; the diagram marking shows the status."""
    objects = []
    for index, cell_id in enumerate(context["markedIds"]):
        entry = findings(model, cell_id, index, "diagnosis")[0]
        objects.append({**entry, "verdict": verdict_of(entry["checks"]), "checks": [], "score": score(model, cell_id, entry["identity"])})
    return {"objects": objects}


def check_feedback(model: Model) -> dict:
    """Whole-model check without marking: the recognition overview plus every object it counts as recognized."""
    objects = []
    for index, cell_id in enumerate(model.nodes):
        entry = findings(model, cell_id, index, "diagnosis")[0]
        if entry["identity"] == "recognized":
            objects.append({**entry, "verdict": "matches", "checks": []})
    return {"objects": objects}


PLACEHOLDER = "#9E9E9E"  # light grey: the pattern recedes behind recognized cells


def excerpt(root, reference_id: str, neighbours: bool = False, relabel=None) -> str | None:
    """One-hop neighbourhood of a model cell as stand-alone maxGraph XML, independent of the language.

    A connection brings its two end elements (without their children); an element brings everything nested in it
    (structural containers and their children, e.g. attributes) plus every connection at it, whose far end stays
    open and only points towards the hidden element. Ancestors keep nested cells in place.
    `neighbours` also brings the far ends with everything nested in them instead of open ends. `relabel(cell_id)`
    turns it into a structure pattern: it returns (label, is_placeholder) or None to keep the cell as it is.
    """
    cells = {cell.get("id"): cell for cell in root.findall("Cell")} if root is not None else {}
    if reference_id not in cells:
        return None
    layers = {cell_id for cell_id, cell in cells.items() if cell.get("parent") in (None, "0")}
    children = {}
    for cell_id, cell in cells.items():
        children.setdefault(cell.get("parent"), []).append(cell_id)

    def ancestors(cell_id):
        chain, parent = [], cells[cell_id].get("parent")
        while parent in cells and parent not in layers:
            chain.append(parent)
            parent = cells[parent].get("parent")
        return chain

    def nested(cell_id):
        return [cell_id, *[item for child in children.get(cell_id, []) for item in nested(child)]]

    def edge(cell_id):
        return cells[cell_id].get("edge") in ("1", "true")

    def center(cell_id):
        """Absolute center of a vertex; relative (e.g. edge-label) geometries are not summed."""
        x = y = 0.0
        for item in (cell_id, *ancestors(cell_id)):
            geometry = cells[item].find("Geometry")
            if geometry is not None and geometry.get("relative") not in ("1", "true"):
                x, y = x + float(geometry.get("_x", 0)), y + float(geometry.get("_y", 0))
        geometry = cells[cell_id].find("Geometry")
        width, height = (float(geometry.get(key, 0)) for key in ("_width", "_height")) if geometry is not None else (0.0, 0.0)
        return x + width / 2, y + height / 2, width / 2, height / 2

    keep, open_edges, core = {reference_id, *ancestors(reference_id)}, {}, {reference_id}
    if edge(reference_id):
        ends = [cells[reference_id].get(role) for role in ("source", "target")]
        for end in (end for end in ends if end in cells):
            keep |= {*(nested(end) if neighbours else [end]), *ancestors(end)}
    else:
        core = set(nested(reference_id))
        keep |= core
        for cell_id in cells:
            ends = {cells[cell_id].get("source"), cells[cell_id].get("target")}
            if edge(cell_id) and ends & core and ends <= set(cells):
                keep |= {cell_id, *ancestors(cell_id)}
                if neighbours:
                    keep |= {item for end in ends - core for item in (*nested(end), *ancestors(end))}
                else:
                    open_edges[cell_id] = [role for role in ("source", "target") if cells[cell_id].get(role) not in core]
    # Schematic open ends: each leaves the visible end on the side facing the hidden element, at a fixed length,
    # parallel to its neighbours on that side and evenly spread so no two ends meet.
    sides = {}
    for cell_id, roles in open_edges.items():
        for role in roles:
            visible = cells[cell_id].get("target" if role == "source" else "source")
            hx, hy, _, _ = center(cells[cell_id].get(role))
            cx, cy, _, _ = center(visible)
            side = ("right" if hx >= cx else "left") if abs(hx - cx) >= abs(hy - cy) else ("bottom" if hy >= cy else "top")
            sides.setdefault((visible, side), []).append((hy if side in ("left", "right") else hx, cell_id, role))
    points = {}
    for (visible, side), ends in sides.items():
        cx, cy, half_width, half_height = center(visible)
        for index, (_, cell_id, role) in enumerate(sorted(ends)):
            spread = (index - (len(ends) - 1) / 2) * 30
            points[cell_id, role] = {"right": (cx + half_width + 80, cy + spread), "left": (cx - half_width - 80, cy + spread),
                                     "bottom": (cx + spread, cy + half_height + 80), "top": (cx + spread, cy - half_height - 80)}[side]
    result = ElementTree.Element("GraphDataModel")
    target = ElementTree.SubElement(result, "root")
    for cell_id, cell in cells.items():  # document order keeps parents before children
        if cell_id in open_edges:
            cell = open_end(cell, {role: points[cell_id, role] for role in open_edges[cell_id]})
        label = relabel(cell_id) if relabel is not None and cell_id in keep else None
        if label is not None:
            cell, (text, placeholder) = copy.deepcopy(cell), label  # the parsed model is shared by every help type
            if cell.get("value"):
                cell.set("value", text)
            style = cell.find("Object[@as='style']")
            if placeholder and style is not None and cell.get("vertex") in ("1", "true"):
                style.attrib.update({"dashed": "1", "fontStyle": "2", "fontColor": PLACEHOLDER})  # italic and dashed: a placeholder
            if placeholder and style is not None and cell.get("value") is not None:
                style.set("strokeColor", PLACEHOLDER)
        if cell_id in keep or cell_id in layers or cell.get("id") == "0":
            target.append(cell)
    return ElementTree.tostring(result, encoding="unicode")


def open_end(cell, points: dict) -> ElementTree.Element:
    """Copy of an edge whose hidden terminals become the given free points."""
    cell = copy.deepcopy(cell)
    geometry = cell.find("Geometry")
    if geometry is None:
        geometry = ElementTree.SubElement(cell, "Geometry", {"relative": "1", "as": "geometry"})
    for waypoints in geometry.findall("Array[@as='points']"):  # the original route would bend the schematic line
        geometry.remove(waypoints)
    for role, (x, y) in points.items():
        ElementTree.SubElement(geometry, "Point", {"_x": str(x), "_y": str(y), "as": f"{role}Point"})
        del cell.attrib[role]
    return cell


def example_of(model: Model, cell_id: str) -> dict | None:
    """The matching sample-solution element: label, type, its one-hop excerpt and the language definition as fallback."""
    reference_id = (model.annotations.get(cell_id) or {}).get("referenceId") or ""
    reference = model.reference_nodes.get(reference_id)
    return reference and {"kind": reference.get("kind"), "label": clean(reference.get("label") or ""),
                          "typeName": model.type_name(reference.get("type")), "definition": model.definition(reference),
                          "xml": excerpt(model.reference_xml, reference_id)} or None


def pattern_of(model: Model, cell_id: str) -> dict | None:
    """Structure pattern for help.example: the sample-solution neighbourhood two levels deep (neighbours with their
    nested elements); recognized cells carry the learner's label, all others only their type as a placeholder."""
    anchor = cell_id
    if not any(cell_id in ends.values() for ends in model.ends.values()):  # e.g. an attribute: compare its owner
        parent = model.parents.get(cell_id)
        while parent in model.nodes and model.nodes[parent].get("kind") == "structuralElement":
            parent = model.parents.get(parent)
        anchor = parent if parent in model.nodes else cell_id
    reference_id = (model.annotations.get(anchor) or {}).get("referenceId")
    if not reference_id:
        return None
    def relabel(cell_id):
        """Recognized cells show the learner's own label; the rest only their language type as a placeholder."""
        own = anchor if cell_id == reference_id else model.proven.get(cell_id)
        node = model.reference_nodes.get(cell_id, {})
        if own:
            return clean(model.nodes.get(own, {}).get("label") or ""), False
        if not node:
            return "", False  # e.g. a label cell outside the parsed graph: its text stays hidden
        return model.type_name(node.get("type")), node.get("kind") != "structuralElement"

    expected = excerpt(model.reference_xml, reference_id, neighbours=True, relabel=relabel)
    return {"cellId": anchor, "expected": expected} if expected else None


def example_feedback(model: Model, context: dict) -> dict:
    """Per marked object the structure pattern of the sample solution; finding the differences is left to the learner."""
    objects = [{**findings(model, cell_id, index, "diagnosis")[0], "checks": [], "pattern": pattern_of(model, cell_id)}
               for index, cell_id in enumerate(context["markedIds"])]
    return {"objects": objects, "notices": []}


def solution_feedback(model: Model, context: dict) -> dict:
    """Complete target per marked object: correct, superfluous, and every change incl. sample-solution labels."""
    objects = []
    for index, cell_id in enumerate(context["markedIds"]):
        entry, items = findings(model, cell_id, index, "labels")
        name, steps, seen = model.name(cell_id), [], set()
        differing = {item["area"] for item in items if item["status"] == "differs"}
        if entry["identity"] == "unassigned":
            steps.append({"area": "identity", "status": "differs", "certainty": "conditional", "messageCode": "identity.superfluous",
                          "text": f"{subject(name)} konnte {'keiner Verbindung' if entry['kind'] == 'connection' else 'keinem Element'} "
                                  "der Musterlösung zugeordnet werden und ist wahrscheinlich überflüssig."})
        for item in items:
            # An area with a proven difference needs no extra "unclear" line.
            if item["status"] == "matches" or (item["status"] == "unclear" and item["area"] in differing):
                continue
            answer = solution(model, item, "labels")[0] if item["status"] == "differs" else None
            text = answer or check_text(item, "labels")
            if text not in seen:
                seen.add(text)
                steps.append({"area": item["area"], "status": item["status"], "certainty": item["certainty"],
                              "messageCode": f"{item['area']}.solution", "text": articles(text)})
        if not steps and entry["identity"] == "recognized":
            steps.append({"area": "identity", "status": "matches", "certainty": "proven", "messageCode": "identity.correct",
                          "text": f"{subject(name)} stimmt mit der Musterlösung überein."})
        objects.append({**entry, "checks": steps, "verdict": verdict_of(steps), "example": example_of(model, cell_id)})
    return {"objects": objects}


def solution(model: Model, item: dict, disclosure: str) -> tuple[str | None, list[str], str | None]:
    """Target constellation in the learner's own objects; None plus a notice when not supported."""
    if disclosure == "diagnosis":
        return None, [], "solution_not_released"
    if item["certainty"] != "proven":
        return None, [], "solution_uncertain"
    fact, area, name, cell_id = item["fact"], item["area"], item["name"], item["cellId"]
    code, evidence = fact["code"], fact["evidence"]
    if area == "hierarchy" and code in ("owner.violated", "containment.violated"):
        parents = [model.proven.get(identity) for identity in evidence.get("referenceParentIds", [])]
        if parents and all(parents):
            return f"Ordne {name} {' und '.join(model.name(parent) for parent in parents)} zu.", parents, None
    if area == "connection" and code in ("connection.source", "connection.target", "connection.endpoints"):
        observed = model.annotations[cell_id].get("connection", {}).get("reference") or {}
        ends = [model.proven.get(observed.get(role)) for role in ("sourceId", "targetId")]
        if all(ends):
            return f"Lass {name} bei {model.name(ends[0])} beginnen und bei {model.name(ends[1])} enden.", ends, None
    if code == "connection.direction":
        endpoints = next((other for other in model.annotations[cell_id]["facts"] if other["code"] == "connection.endpoints"), None)
        if endpoints and endpoints["status"] == "satisfied":
            return f"Kehre die Richtung von {name} um.", [], None
    if code == "type.different":
        expected = model.reference_nodes.get(next(iter(fact["referenceIds"]), ""), {}).get("type")
        if expected:
            return f"Ändere den Typ von {name} in „{model.type_name(expected)}“.", [], None
    if code == "label.different":
        if disclosure != "labels":
            return None, [], "solution_not_released"
        expected = model.reference_nodes.get(next(iter(fact["referenceIds"]), ""), {}).get("label")
        if expected:
            return f"Benenne {name} in „{clean(expected)}“ um.", [], None
    if "hint" in item:
        reference = model.reference_nodes.get(item["hint"]["referenceId"], {})
        kind = model.type_name(reference.get("type"))
        noun = "eine Verbindung" if reference.get("kind") == "connection" else "ein Element"
        if disclosure == "labels" and reference.get("label"):
            return f"Bei {name} fehlt noch „{clean(reference['label'])}“ ({kind}).", [], None
        return f"Bei {name} fehlt noch {noun} vom Typ „{kind}“.", [], None
    return None, [], "solution_not_derivable"


def step(cell_ids: list[str], area: str, key: dict, text: str) -> dict:
    return {"cellIds": cell_ids, "area": area, "issueKey": content_hash(key), "text": articles(text)}


def semantic_children(model: Model, cell_id: str) -> list[str]:
    """Nested elements of a cell; structural containers (e.g. attribute lists) are skipped, not reported."""
    result = []
    for child, parent in model.parents.items():
        if parent == cell_id and model.nodes.get(child, {}).get("kind") != "connection":
            result += semantic_children(model, child) if model.nodes[child].get("kind") == "structuralElement" else [child]
    return result


def element_steps(model: Model, cell_id: str):
    """Element itself, in order: assignable label, type, placement, then its nested elements, then their completeness."""
    annotation, name = model.annotations.get(cell_id), model.name(cell_id)
    identity = (annotation or {}).get("identity", {}).get("status")
    if annotation is None or identity is None:
        return  # not evaluated (e.g. structural or out of scope)
    if identity == "unresolved" and not annotation.get("referenceId"):
        text = (f"{name} konnte keinem Element der Musterlösung zugeordnet werden. Wähle eine Beschriftung, die näher an der Aufgabe ist, "
                "oder lösche das Element, wenn du es nicht brauchst." if clean(model.nodes[cell_id].get("label") or "")
                else f"Beschrifte {name} mit einem Begriff aus der Aufgabe.")
        yield step([cell_id], "identity", {"code": "identity.unassigned", "cellId": cell_id}, text)
        return
    # A recognized label is enough; renaming to the exact sample-solution term is never the next step.
    items = [item for item in findings(model, cell_id, 0, "structure")[1] if item["status"] == "differs" and item["area"] in ("type", "hierarchy")]
    for item in sorted(items, key=lambda row: row["area"] != "type"):  # type before placement
        answer, extra, _ = solution(model, item, "structure")
        yield step([cell_id, *extra], item["area"], {"issueKey": item["issueKey"]}, answer or NEXT_STEPS[item["area"]].format(name=name))
    for child in semantic_children(model, cell_id):
        yield from element_steps(model, child)
    # Transitive completeness decides when present; direct children only as fallback (they include unmatched structural containers).
    facts = {fact["code"]: fact for fact in (annotation or {}).get("facts", [])}
    fact = facts.get("children.complete") or facts.get("direct_children.complete") or {}
    evidence = fact.get("evidence", {}) if fact.get("status") in ("violated", "unresolved") else {}
    for reference_id in evidence.get("movedReferenceIds", []):
        if model.proven.get(reference_id):
            moved = model.proven[reference_id]
            yield step([moved, cell_id], "hierarchy", {"code": "child.moved", "referenceId": reference_id},
                       f"Ordne {model.name(moved)} {name} zu.")
    absent = set(evidence.get("provenAbsentReferenceIds", [])) | {
        hint["referenceId"] for hint in model.analysis["referenceHints"] if hint["code"] == "reference.missing" and hint["target"]["id"] == cell_id}
    missing = [*sorted(absent), *[ref for ref in evidence.get("unmatchedReferenceIds", [])
                                  if ref not in absent and ref not in evidence.get("movedReferenceIds", [])]]
    for reference_id in missing:  # the smallest part of the solution: exactly this one missing element
        if model.reference_nodes.get(reference_id, {}).get("kind") == "structuralElement":
            continue  # containers are layout, not solution content
        yield step([cell_id], "completeness", {"code": "child.missing", "referenceId": reference_id},
                   f"Bei {name} fehlt noch {reference_phrase(model, reference_id)}.")


def reference_phrase(model: Model, reference_id: str) -> str:
    """A sample-solution element by label and type, e.g. „ProjektNr.“ (Attribut); the type alone without a label."""
    node = model.reference_nodes.get(reference_id, {})
    kind, label = model.type_name(node.get("type")), clean(node.get("label") or "")
    return f"„{label}“ ({kind})" if label else f"ein Element vom Typ „{kind}“"


def connection_steps(model: Model, connection_id: str):
    """One existing connection: assignable at all, then endpoints, direction and type."""
    annotation, ends = model.annotations.get(connection_id) or {}, model.ends.get(connection_id, {})
    names = " und ".join(model.name(end) for end in ends.values())
    if annotation.get("identity", {}).get("status") == "unresolved" and not annotation.get("referenceId"):
        yield step([connection_id], "connection", {"code": "connection.unassigned", "cellId": connection_id},
                   f"Die Verbindung zwischen {names} konnte keiner Verbindung der Musterlösung zugeordnet werden. Überlege, ob du sie brauchst.")
        return
    items = [item for item in findings(model, connection_id, 0, "structure")[1] if item["status"] == "differs" and item["area"] == "connection"]
    for item in items:
        answer, extra, _ = solution(model, item, "structure")
        yield step([connection_id, *extra], "connection", {"issueKey": item["issueKey"]},
                   answer or NEXT_STEPS["connection"].format(name=f"der Verbindung zwischen {names}"))


def missing_connections(model: Model, cell_id: str, codes: tuple[str, ...]):
    """Expected connections of the sample solution without a counterpart at this element."""
    name, own = model.name(cell_id), (model.annotations.get(cell_id) or {}).get("referenceId")
    for fact in (model.annotations.get(cell_id) or {}).get("facts", []):
        if fact["code"] not in codes or fact["status"] != "violated":
            continue
        present = {(model.annotations.get(sub) or {}).get("referenceId") for sub in fact["evidence"].get("submissionConnectionIds", [])}
        for reference_id in fact["evidence"].get("referenceConnectionIds", []):
            if reference_id in present or model.proven.get(reference_id):
                continue
            kind = model.type_name(model.reference_nodes.get(reference_id, {}).get("type"))
            reference_ends = model.reference_ends.get(reference_id, {})
            mine = next((role for role, end in reference_ends.items() if end == own), None)
            other = next((end for role, end in reference_ends.items() if role != mine), None)
            towards = {"source": "ausgehende ", "target": "eingehende "}.get(mine, "") if model.reference_nodes.get(reference_id, {}).get("directed", True) else ""
            if other and model.proven.get(other):
                text = f"Bei {name} fehlt noch eine {towards}Verbindung vom Typ „{kind}“ {'von' if mine == 'target' and towards else 'zu'} {model.name(model.proven[other])}."
                extra = [model.proven[other]]
            else:
                text = (f"Bei {name} fehlt noch eine {towards}Verbindung vom Typ „{kind}“. Lege dafür {reference_phrase(model, other or '')} an "
                        f"und verbinde es mit {name}.")
                extra = []
            yield step([cell_id, *extra], "connections", {"code": "connection.missing", "referenceId": reference_id}, text)


def next_step_feedback(model: Model, context: dict) -> dict:
    """The most obvious next step around the marked objects, by priority.

    1. the marked element itself: assignable label, type, placement, nested elements, missing nested elements;
    2. upstream: incoming connections, missing incoming ones, then each preceding element the same way, transitively;
    3. downstream: outgoing (and undirected) connections, missing ones, then each following element, transitively.
    A marked connection is checked first, then its ends. Missing elements are named with label and type (the smallest part of the solution); nothing else is revealed.
    """
    def connections(cell_id, role):
        return [conn for conn, ends in model.ends.items() if ends.get(role) == cell_id and model.nodes.get(conn, {}).get("directed", True)]

    def undirected(cell_id):
        return [conn for conn, ends in model.ends.items() if cell_id in ends.values() and model.nodes.get(conn, {}).get("directed") is False]

    def walk(start, incoming):
        queue, seen = [start], {start}
        while queue:
            current = queue.pop(0)
            edges = connections(current, "target" if incoming else "source") + ([] if incoming else undirected(current))
            for conn in edges:
                yield from connection_steps(model, conn)
            yield from missing_connections(model, current, ("incoming.complete",) if incoming else ("outgoing.complete", "undirected.complete"))
            for conn in edges:
                for neighbour in model.ends[conn].values():
                    if neighbour not in seen:
                        seen.add(neighbour)
                        yield from element_steps(model, neighbour)
                        queue.append(neighbour)

    def steps():
        for cell_id in context["markedIds"]:
            if model.nodes.get(cell_id, {}).get("kind") == "connection":
                yield from connection_steps(model, cell_id)
                for end in model.ends.get(cell_id, {}).values():
                    yield from element_steps(model, end)
                continue
            yield from element_steps(model, cell_id)
            # A nested element (e.g. an attribute) continues at its owner, skipping structural containers.
            anchor = model.parents.get(cell_id)
            while anchor and model.nodes.get(anchor, {}).get("kind") == "structuralElement":
                anchor = model.parents.get(anchor)
            if anchor in model.nodes:
                yield from element_steps(model, anchor)
            yield from walk(anchor if anchor in model.nodes else cell_id, incoming=True)
            yield from walk(anchor if anchor in model.nodes else cell_id, incoming=False)

    found = next(steps(), None)
    if found is None:
        return {"focus": {"cellIds": list(context["markedIds"]), "area": None, "issueKey": None, "messageCode": "none",
                          "text": "Bei den markierten Elementen und allem, was damit verbunden ist, wurde kein Fehler gefunden.",
                          "repeated": False}, "notices": ["no_deviation"]}
    return {"focus": {**found, "messageCode": f"{found['area']}.next_step",
                      "repeated": found["issueKey"] in context["previousIssueKeys"]}, "notices": []}


def overview(analysis: dict) -> dict:
    overall = analysis["recognition"]["overall"]
    return {"overview": {key: overall[key] for key in ("recognized", "expected", "percent", "evaluationStatus")}}


def catalog(analysis: dict, store, bundle: dict) -> dict:
    """Analysis view: what every submission object would get for each help type.

    Each object is evaluated as if it were the only marking, using the same builders learners get.
    """
    model = Model(analysis, store, bundle)
    check, objects = {**check_feedback(model), "recognition": analysis["recognition"]}, []  # help.check ignores the marking: one result for every object
    patterns = {}  # help.example: nested objects share their owner's pattern, so each is stored once
    for cell_id, node in model.nodes.items():
        context = {"markedIds": [cell_id], "previousIssueKeys": set()}
        help_ = {kind: check if kind == "help.check" else content(model, context, kind) for kind in LEVELS}
        for item in help_["help.example"]["objects"]:
            if item["pattern"]:
                patterns[item["pattern"]["cellId"]] = item["pattern"]
                item["pattern"] = {"cellId": item["pattern"]["cellId"]}
        objects.append({"cellId": cell_id, "label": node.get("label") or "", "typeName": model.type_name(node.get("type")), "help": help_})
    return {**overview(analysis), "catalog": objects, "patterns": patterns}


def content(model: Model, context: dict, kind: str) -> dict:
    if kind == "help.clarify":
        return clarify_feedback(model, context)
    if kind == "help.solution":
        return solution_feedback(model, context)
    if kind == "help.next_step":
        return next_step_feedback(model, context)
    return example_feedback(model, context)


def build(kind: str, analysis: dict, context: dict, store, bundle: dict) -> dict:
    model = Model(analysis, store, bundle)
    if kind == "help.check":
        return {**overview(analysis), **check_feedback(model), "recognition": analysis["recognition"]}
    return {**overview(analysis), **content(model, validate_context(context), kind)}
