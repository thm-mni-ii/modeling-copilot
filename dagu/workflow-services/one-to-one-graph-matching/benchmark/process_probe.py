#!/usr/bin/env python3
"""Probe cases for flow-oriented and further diagram types, in the case format of generate.py.

The platform has no BPMN, EPC or UML activity language yet. This module therefore defines minimal
benchmark-only language versions (`benchmark-*`); they declare only what the parser reads: element
and connection types, connection labels and comparison groups. They are test fixtures, not
platform languages. In addition, two probes use the real UML class diagram language: repeated
attribute names across classes and attribute labels with visibility and type (`+ name: Type`).

Usage: python process_probe.py --out CASES_DIR --languages LANGUAGES_OUT
"""

import argparse
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from generate import Diagram, MATCHABLE, clean

HERE = Path(__file__).resolve().parent
MATCHABLE = MATCHABLE | {"reordered", "nominalization", "rephrased", "type_changed", "relocated", "typed"}


def language(key, elements, connections, groups):
    return {"languageId": f"benchmark-{key}", "versionId": f"benchmark-{key}-1", "includedLanguageVersions": [],
            "data": {"elements": [{"type": item, "defaultLabel": "", "children": []} for item in elements],
                     "connections": [{"type": kind, "undirected": undirected, "additionalLabels": [{"type": "condition"}] if labelled else []}
                                     for kind, undirected, labelled in connections],
                     "syntax": {}, "feedback": {}, "evaluation": {"comparisonGroups": groups}}}


LANGUAGES = {
    "bpmn": language("bpmn", ["bpmn-pool", "bpmn-lane", "bpmn-task", "bpmn-start-event", "bpmn-end-event", "bpmn-xor", "bpmn-and", "bpmn-or"],
                     [("bpmn-sequence-flow", False, True)],
                     [{"id": "bpmn-gateway", "name": "Gateway", "elementTypes": ["bpmn-xor", "bpmn-and", "bpmn-or"]}]),
    "epc": language("epc", ["epc-event", "epc-function", "epc-xor", "epc-and", "epc-or", "epc-org-unit", "epc-information"],
                    [("epc-control-flow", False, False), ("epc-assignment", True, False), ("epc-information-flow", False, False)],
                    [{"id": "epc-connector", "name": "Connector", "elementTypes": ["epc-xor", "epc-and", "epc-or"]}]),
    "activity": language("activity", ["uml-initial", "uml-final", "uml-action", "uml-decision", "uml-merge", "uml-fork", "uml-join", "uml-partition"],
                         [("uml-control-flow", False, True)],
                         [{"id": "uml-control-node", "name": "Control node", "elementTypes": ["uml-decision", "uml-merge", "uml-fork", "uml-join"]}]),
}

# One order process, expressed per language. Nodes: id -> (type per language, label, parent); flows: id -> (source, target, condition).
LANES = {"L1": "Vertrieb", "L2": "Lager", "L3": "Buchhaltung"}
NODES = {
    "S": ({"bpmn": "bpmn-start-event", "activity": "uml-initial"}, {"bpmn": "Bestellung eingegangen", "activity": ""}, "L1"),
    "T1": ({"bpmn": "bpmn-task", "activity": "uml-action"}, "Bestellung prüfen", "L1"),
    "T6": ({"bpmn": "bpmn-task", "activity": "uml-action"}, "Daten erfassen", "L1"),
    "G1": ({"bpmn": "bpmn-xor", "activity": "uml-decision"}, {"bpmn": "Ware verfügbar?", "activity": ""}, "L1"),
    "T2": ({"bpmn": "bpmn-task", "activity": "uml-action"}, "Bestellung ablehnen", "L1"),
    "E1": ({"bpmn": "bpmn-end-event", "activity": "uml-final"}, {"bpmn": "Bestellung abgelehnt", "activity": ""}, "L1"),
    "G2": ({"bpmn": "bpmn-and", "activity": "uml-fork"}, "", "L2"),
    "T3": ({"bpmn": "bpmn-task", "activity": "uml-action"}, "Ware kommissionieren", "L2"),
    "T4": ({"bpmn": "bpmn-task", "activity": "uml-action"}, "Ware versenden", "L2"),
    "T7": ({"bpmn": "bpmn-task", "activity": "uml-action"}, "Daten erfassen", "L3"),
    "T5": ({"bpmn": "bpmn-task", "activity": "uml-action"}, "Rechnung erstellen", "L3"),
    "G3": ({"bpmn": "bpmn-and", "activity": "uml-join"}, "", "L3"),
    "E2": ({"bpmn": "bpmn-end-event", "activity": "uml-final"}, {"bpmn": "Bestellung abgeschlossen", "activity": ""}, "L3"),
}
FLOWS = {"f1": ("S", "T1", ""), "f2": ("T1", "T6", ""), "f3": ("T6", "G1", ""), "f4": ("G1", "T2", "nein"), "f5": ("T2", "E1", ""),
         "f6": ("G1", "G2", "ja"), "f7": ("G2", "T3", ""), "f8": ("T3", "T4", ""), "f9": ("G2", "T7", ""), "f10": ("T7", "T5", ""),
         "f11": ("T4", "G3", ""), "f12": ("T5", "G3", ""), "f13": ("G3", "E2", "")}
EPC_NODES = {
    "V1": ("epc-event", "Bestellung ist eingegangen"), "F1": ("epc-function", "Bestellung prüfen"), "K1": ("epc-xor", ""),
    "V2": ("epc-event", "Bestellung ist abgelehnt"), "V3": ("epc-event", "Bestellung ist angenommen"), "K2": ("epc-and", ""),
    "F2": ("epc-function", "Ware versenden"), "V4": ("epc-event", "Ware ist versendet"), "F3": ("epc-function", "Rechnung erstellen"),
    "V5": ("epc-event", "Rechnung ist erstellt"), "K3": ("epc-and", ""), "V6": ("epc-event", "Auftrag ist abgeschlossen"),
    "O1": ("epc-org-unit", "Vertrieb"), "O2": ("epc-org-unit", "Lager"), "O3": ("epc-org-unit", "Buchhaltung"),
    "I1": ("epc-information", "Bestelldaten"),
}
EPC_FLOWS = {"c1": ("V1", "F1", "epc-control-flow"), "c2": ("F1", "K1", "epc-control-flow"), "c3": ("K1", "V2", "epc-control-flow"),
             "c4": ("K1", "V3", "epc-control-flow"), "c5": ("V3", "K2", "epc-control-flow"), "c6": ("K2", "F2", "epc-control-flow"),
             "c7": ("K2", "F3", "epc-control-flow"), "c8": ("F2", "V4", "epc-control-flow"), "c9": ("F3", "V5", "epc-control-flow"),
             "c10": ("V4", "K3", "epc-control-flow"), "c11": ("V5", "K3", "epc-control-flow"), "c12": ("K3", "V6", "epc-control-flow"),
             "a1": ("O1", "F1", "epc-assignment"), "a2": ("O2", "F2", "epc-assignment"), "a3": ("O3", "F3", "epc-assignment"),
             "i1": ("I1", "F1", "epc-information-flow"), "i2": ("I1", "F3", "epc-information-flow")}

VARIANTS = {
    "reordered": {"Bestellung prüfen": "Prüfe Bestellung", "Daten erfassen": "Erfasse Daten", "Bestellung ablehnen": "Lehne Bestellung ab",
                  "Ware kommissionieren": "Kommissioniere Ware", "Ware versenden": "Versende Ware", "Rechnung erstellen": "Erstelle Rechnung"},
    "nominalization": {"Bestellung prüfen": "Prüfung der Bestellung", "Daten erfassen": "Datenerfassung", "Bestellung ablehnen": "Ablehnung der Bestellung",
                       "Ware kommissionieren": "Kommissionierung", "Ware versenden": "Warenversand", "Rechnung erstellen": "Rechnungserstellung"},
    "rephrased": {"Bestellung eingegangen": "Eingang einer Bestellung", "Bestellung abgelehnt": "Bestellung wurde abgelehnt",
                  "Bestellung abgeschlossen": "Bestellung ist abgeschlossen", "Ware verfügbar?": "Ist die Ware vorrätig?",
                  "Bestellung ist eingegangen": "Bestellung eingegangen", "Bestellung ist abgelehnt": "Bestellung abgelehnt",
                  "Bestellung ist angenommen": "Bestellung angenommen", "Ware ist versendet": "Ware versendet",
                  "Rechnung ist erstellt": "Rechnung erstellt", "Auftrag ist abgeschlossen": "Auftrag abgeschlossen"},
    "translation": {"Bestellung prüfen": "Check order", "Daten erfassen": "Record data", "Bestellung ablehnen": "Reject order",
                    "Ware kommissionieren": "Pick goods", "Ware versenden": "Ship goods", "Rechnung erstellen": "Create invoice",
                    "Bestellung eingegangen": "Order received", "Bestellung abgelehnt": "Order rejected", "Bestellung abgeschlossen": "Order completed",
                    "Ware verfügbar?": "Goods available?", "Vertrieb": "Sales", "Lager": "Warehouse", "Buchhaltung": "Accounting",
                    "Bestellung ist eingegangen": "Order has been received", "Bestellung ist abgelehnt": "Order is rejected",
                    "Bestellung ist angenommen": "Order is accepted", "Ware ist versendet": "Goods are shipped", "Rechnung ist erstellt": "Invoice is created",
                    "Auftrag ist abgeschlossen": "Order is completed", "Bestelldaten": "Order data"},
}


def build_xml(vertices, edges):
    """vertices: id -> (type, label, parent); edges: id -> (type, source, target, undirected, condition)."""
    root = ET.Element("GraphDataModel")
    cells = ET.SubElement(root, "root")
    for identity, parent in (("0", None), ("1", "0"), ("2", "0")):
        cell = ET.SubElement(cells, "Cell", {"id": identity, **({"parent": parent} if parent else {})})
        ET.SubElement(cell, "Object", {"as": "style"})
    for index, (identity, (kind, label, parent)) in enumerate(vertices.items()):
        cell = ET.SubElement(cells, "Cell", {"id": identity, "value": label, "vertex": "1", "parent": parent or "1", "diagramElementType": kind})
        ET.SubElement(cell, "Geometry", {"_x": str(40 + 120 * index), "_y": "40", "_width": "100", "_height": "60", "as": "geometry"})
        ET.SubElement(cell, "Object", {"as": "style"})
    for identity, (kind, source, target, undirected, condition) in edges.items():
        cell = ET.SubElement(cells, "Cell", {"id": identity, "value": "", "edge": "1", "parent": "1", "source": source, "target": target,
                                             "connectionId": kind, "connectionUndirected": "1" if undirected else "0"})
        ET.SubElement(cell, "Geometry", {"relative": "1", "as": "geometry"})
        ET.SubElement(cell, "Object", {"as": "style"})
        if condition:
            label = ET.SubElement(cells, "Cell", {"id": f"{identity}-label", "value": condition, "vertex": "1", "parent": identity, "connectionLabelId": "condition"})
            ET.SubElement(label, "Geometry", {"relative": "1", "as": "geometry"})
            ET.SubElement(label, "Object", {"as": "style"})
    return ET.tostring(root, encoding="unicode")


def flow_model(kind):
    """BPMN or UML activity version of the order process; lanes and partitions place, they never own."""
    container = {"bpmn": "bpmn-lane", "activity": "uml-partition"}[kind]
    flow = {"bpmn": "bpmn-sequence-flow", "activity": "uml-control-flow"}[kind]
    vertices = {lane: (container, label, None) for lane, label in LANES.items()}
    for identity, (types, label, lane) in NODES.items():
        vertices[identity] = (types[kind], label[kind] if isinstance(label, dict) else label, lane)
    guard = (lambda text: f"[{text}]" if text else "") if kind == "activity" else (lambda text: text)
    edges = {identity: (flow, source, target, False, guard(condition)) for identity, (source, target, condition) in FLOWS.items()}
    return vertices, edges


def epc_model():
    vertices = {identity: (kind, label, None) for identity, (kind, label) in EPC_NODES.items()}
    edges = {identity: (kind, source, target, kind == "epc-assignment", "") for identity, (source, target, kind) in EPC_FLOWS.items()}
    return vertices, edges


def case(reference_key, name, reference_vertices, vertices, edges, categories, removed=()):
    truth = {}
    for identity, (_kind, label, _parent) in reference_vertices.items():
        category = "removed" if identity in removed or identity not in vertices else categories.get(identity, "exact")
        submission = vertices.get(identity, (None, "", None))[1]
        truth[identity] = {"label": clean(label), "category": category, "submissionLabel": clean(submission), "owner": None,
                           "expected": identity if category in MATCHABLE else None}
    return {"reference": reference_key, "case": name, "xml": build_xml(vertices, edges), "truth": truth, "extra": []}


def relabel(vertices, table):
    changed = {}
    for identity, (kind, label, parent) in vertices.items():
        if label in table:
            vertices[identity] = (kind, table[label], parent)
            changed[identity] = True
    return changed


def flow_cases(kind):
    key = f"{kind}-order-process"
    vertices, edges = flow_model(kind)
    reference = {"key": key, "xml": build_xml(vertices, edges),
                 "task": {"taskId": f"benchmark-{key}", "versionId": f"benchmark-{key}-1",
                          "data": {"sampleSolutions": [{"modelId": f"benchmark-{key}", "versionId": f"benchmark-{key}-1"}]},
                          "workspaceLanguages": [{"languageId": LANGUAGES[kind]["languageId"], "versionId": LANGUAGES[kind]["versionId"], "source": "required"}]},
                 "reference": {"modelId": f"benchmark-{key}", "versionId": f"benchmark-{key}-1",
                               "workspaceLanguages": [{"languageId": LANGUAGES[kind]["languageId"], "versionId": LANGUAGES[kind]["versionId"], "source": "required"}]}}
    cases = [case(key, "identical", vertices, vertices, edges, {})]
    for name in ("reordered", "nominalization", "rephrased", "translation"):
        changed = copy.deepcopy(vertices)
        cases.append(case(key, name, vertices, changed, edges, {identity: name for identity in relabel(changed, VARIANTS[name])}))
    # Conditions on the decision branches only.
    renamed = {identity: (*edge[:4], {"ja": "verfügbar", "nein": "nicht verfügbar", "[ja]": "[verfügbar]", "[nein]": "[nicht verfügbar]"}.get(edge[4], edge[4]))
               for identity, edge in edges.items()}
    cases.append(case(key, "condition_labels", vertices, vertices, renamed, {}))
    # Two sequential tasks swapped: same objects, different order.
    swapped = {identity: edge for identity, edge in edges.items() if identity not in ("f7", "f8", "f11")}
    flow = edges["f7"][0]
    swapped.update({"s7": (flow, "G2", "T4", False, ""), "s8": (flow, "T4", "T3", False, ""), "s11": (flow, "T3", "G3", False, "")})
    cases.append(case(key, "swapped_order", vertices, vertices, swapped, {}))
    # Decision node of another kind of the same comparison group.
    typed = copy.deepcopy(vertices)
    typed["G1"] = ({"bpmn": "bpmn-or", "activity": "uml-merge"}[kind], typed["G1"][1], typed["G1"][2])
    cases.append(case(key, "gateway_type_changed", vertices, typed, edges, {"G1": "type_changed"}))
    # Implicit parallelism: split and join omitted, flows connect the tasks directly.
    implicit = {identity: value for identity, value in vertices.items() if identity not in ("G2", "G3")}
    direct = {identity: edge for identity, edge in edges.items() if identity not in ("f6", "f7", "f9", "f11", "f12", "f13")}
    direct.update({"d1": (flow, "G1", "T3", False, edges["f6"][4]), "d2": (flow, "G1", "T7", False, edges["f6"][4]),
                   "d3": (flow, "T4", "E2", False, ""), "d4": (flow, "T5", "E2", False, "")})
    cases.append(case(key, "implicit_parallelism", vertices, implicit, direct, {}, removed=("G2", "G3")))
    # A task placed in another lane or partition.
    moved = copy.deepcopy(vertices)
    moved["T5"] = (moved["T5"][0], moved["T5"][1], "L2")
    cases.append(case(key, "lane_changed", vertices, moved, edges, {"T5": "relocated"}))
    # The first half of the process only.
    keep = {"L1", "S", "T1", "T6", "G1", "T2", "E1"}
    half = {identity: value for identity, value in vertices.items() if identity in keep}
    cases.append(case(key, "subset_half", vertices, half, {identity: edge for identity, edge in edges.items() if edge[1] in keep and edge[2] in keep}, {}))
    return reference, cases


def epc_cases():
    key = "epc-order-process"
    vertices, edges = epc_model()
    workspace = [{"languageId": LANGUAGES["epc"]["languageId"], "versionId": LANGUAGES["epc"]["versionId"], "source": "required"}]
    reference = {"key": key, "xml": build_xml(vertices, edges),
                 "task": {"taskId": f"benchmark-{key}", "versionId": f"benchmark-{key}-1",
                          "data": {"sampleSolutions": [{"modelId": f"benchmark-{key}", "versionId": f"benchmark-{key}-1"}]}, "workspaceLanguages": workspace},
                 "reference": {"modelId": f"benchmark-{key}", "versionId": f"benchmark-{key}-1", "workspaceLanguages": workspace}}
    cases = [case(key, "identical", vertices, vertices, edges, {})]
    for name, table in (("rephrased", VARIANTS["rephrased"]), ("nominalization", VARIANTS["nominalization"]), ("translation", VARIANTS["translation"])):
        changed = copy.deepcopy(vertices)
        cases.append(case(key, name, vertices, changed, edges, {identity: name for identity in relabel(changed, table)}))
    typed = copy.deepcopy(vertices)
    typed["K1"] = ("epc-or", "", None)
    cases.append(case(key, "connector_type_changed", vertices, typed, edges, {"K1": "type_changed"}))
    reassigned = dict(edges)
    reassigned["a1"] = ("epc-assignment", "O2", "F1", True, "")
    cases.append(case(key, "org_unit_changed", vertices, vertices, reassigned, {}))
    keep = {"V1", "F1", "K1", "V2", "V3", "O1", "I1"}
    half = {identity: value for identity, value in vertices.items() if identity in keep}
    cases.append(case(key, "subset_half", vertices, half, {identity: edge for identity, edge in edges.items() if edge[1] in keep and edge[2] in keep}, {}))
    return reference, cases


def uml_cases():
    """Real UML class language: shared attribute names across classes, and visibility/type in attribute labels."""
    source = json.loads((HERE / "references/uml-order-management.json").read_text(encoding="utf-8"))
    diagram = Diagram(source["xml"])
    classes = [identity for identity in diagram.top() if diagram.kind(diagram.cells[identity]) == "uml-class"]
    like = diagram.attributes(classes[0])[0]
    for index, owner in enumerate(classes):
        diagram.add_attribute(like, owner, "id", f"id-{index}")
        diagram.add_attribute(like, owner, "name", f"name-{index}")
    reference = {**source, "key": "uml-shared-attributes", "xml": diagram.xml()}
    truth = {cell.get("id"): {"label": clean(cell.get("value")), "category": "exact", "submissionLabel": clean(cell.get("value")),
                              "owner": diagram.owner(cell.get("id")), "expected": cell.get("id")} for cell in diagram.elements()}
    cases = [{"reference": "uml-shared-attributes", "case": "identical", "xml": diagram.xml(), "truth": copy.deepcopy(truth), "extra": []}]
    typed = Diagram(diagram.xml())
    types = {"customerNumber": "int", "orderNumber": "int", "quantity": "int", "productNumber": "String", "id": "int", "name": "String"}
    typed_truth = copy.deepcopy(truth)
    for identity in typed.attributes():
        label = clean(typed.label(identity))
        typed.set_label(identity, f"+ {label}: {types.get(label, 'String')}")
        typed_truth[identity].update(category="typed", submissionLabel=typed.label(identity))
    cases.append({"reference": "uml-shared-attributes", "case": "typed_attributes", "xml": typed.xml(), "truth": typed_truth, "extra": []})
    return reference, cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--languages", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for reference, cases in (flow_cases("bpmn"), flow_cases("activity"), epc_cases(), uml_cases()):
        (out / f"{reference['key']}.reference.json").write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
        for item in cases:
            (out / f"{reference['key']}__{item['case']}.json").write_text(json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")
            count += 1
    platform = json.loads((HERE / "references/languages.json").read_text(encoding="utf-8"))
    Path(args.languages).write_text(json.dumps(platform + list(LANGUAGES.values()), ensure_ascii=False), encoding="utf-8")
    print(f"{count} probe cases -> {out}")


if __name__ == "__main__":
    main()
