"""Focused projection regressions; no matcher implementation or pipeline execution."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

SERVICES = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SERVICES / "analytical-feedback/src"), str(SERVICES / "one-to-one-graph-matching/src"), str(SERVICES)]

import analysis
from analysis_contract import analysis_key, content_hash, validate_analysis
from graph_index import GraphIndex


def node(identity, kind="modelElement", native_type="entity", **values):
    return {"id": identity, "kind": kind, "type": native_type, "comparisonGroup": None,
            "comparisonRole": "structural" if kind == "structuralElement" else "semantic",
            "language": {"languageId": "generic", "versionId": "1"}, "languageResolution": "resolved",
            "definition": None, **values}


def contains(child, parent, role="content"):
    return {"kind": "contains", "source": child, "target": parent, "role": role}


def endpoints(connection, source, target):
    return [{"kind": "endpoint", "source": source, "target": connection, "role": "source"},
            {"kind": "endpoint", "source": connection, "target": target, "role": "target"}]


class Store:
    def __init__(self, bundle, indices, comparison):
        self.bundle, self.indices, self.comparison = bundle, indices, comparison

    def snapshot(self):
        return self.bundle

    def read(self, path):
        if path.startswith("labels/"):
            return {"result": {"connectionTexts": []}}
        if path.startswith("comparisons/"):
            return {"result": self.comparison}
        index = self.indices["student" if path == "graphs/submission.json" else "reference"]
        return {"result": {"graph": {"nodes": list(index.nodes.values())}}}


def case(reference, submission=None, reference_edges=(), submission_edges=None, pairs=None, **evidence):
    submission = deepcopy(reference) if submission is None else submission
    submission_edges = deepcopy(reference_edges) if submission_edges is None else submission_edges
    indices = {side: GraphIndex({"schemaVersion": 1, "languages": [], "nodes": nodes, "edges": list(edges)})
               for side, nodes, edges in (("reference", reference, reference_edges), ("student", submission, submission_edges))}
    if pairs is None:
        pairs = [(item["id"], item["id"]) for item in reference if item["kind"] in ("modelElement", "connection")]
    mapping = {"provisionalElements": [], "provisionalConnections": []}
    for ref, sub in pairs:
        field = "provisionalConnections" if indices["reference"].nodes[ref]["kind"] == "connection" else "provisionalElements"
        mapping[field].append({"referenceId": ref, "studentId": sub, "reason": "unique_exact_label", "status": "provisional"})
    mapped = {ref for ref, _ in pairs}
    comparison = {"pair": {"studentKey": "submission", "referenceKey": "ref"}, "comparisonHash": "a" * 64,
                  "mapping": mapping, "semanticRefinement": {"candidateEvidence": []},
                  "unresolvedReferenceIds": sorted(item["id"] for item in reference if item["kind"] == "modelElement" and item["id"] not in mapped),
                  "unresolvedReferenceConnectionIds": sorted(item["id"] for item in reference if item["kind"] == "connection" and item["id"] not in mapped), **evidence}
    bundle = {"evaluationId": "evaluation", "comparisonConfig": {},
              "models": [{"source": {"key": "submission", "modelId": "model"}}],
              "languages": [{"languageId": "generic", "versionId": "1", "data": {"evaluation": {
                  "elementCategories": {"entity": "nodes", "property": "attributes"}}}}]}
    return Store(bundle, indices, comparison)


def build(store):
    report = analysis.build(store, store.bundle, store.indices, {"synonymMatrix": []}, store.comparison, {})
    report["analysisKey"] = analysis_key(report)
    report["analysisHash"] = content_hash(report)
    return report


class CategoryTests(unittest.TestCase):
    def test_declared_categories_and_separate_containers(self):
        store = case([node("n"), node("a", native_type="property"), node("c", "connection"),
                      node("box", "structuralElement"), node("unknown", native_type="new-type"),
                      node("label", "connectionLabel")])
        report = build(store)
        self.assertEqual({key: value["expected"] for key, value in report["summary"].items()},
                         {"nodes": 1, "attributes": 1, "connections": 1, "other": 2})
        self.assertEqual(report["structuralContainers"]["referenceCount"], 1)
        self.assertEqual(report["summary"]["other"]["evaluationStatus"], "partial")

    def test_missing_metadata_never_guesses_category(self):
        store = case([node("n")])
        store.bundle["languages"][0]["data"] = {}
        report = build(store)
        self.assertEqual(report["summary"]["nodes"]["expected"], 0)
        self.assertIsNone(report["summary"]["nodes"]["percent"])
        self.assertEqual(report["summary"]["other"]["expected"], 1)
        store.indices["reference"].nodes["n"]["languageResolution"] = "unresolved"
        self.assertEqual(build(store)["summary"]["other"]["evaluationStatus"], "not_evaluated")

    def test_connection_evaluability_comes_from_existing_matcher_statement(self):
        store = case([node("e", "connection", directed=True)], pairs=[])
        self.assertEqual(build(store)["summary"]["connections"]["evaluationStatus"], "not_evaluated")
        store.comparison["metrics"] = {"provisionalRecognition": {"categoryTypes": [{
            "category": "connections", "language": {"languageId": "generic", "versionId": "1"},
            "type": "entity", "evaluableReferenceCount": 1}]}}
        self.assertEqual(build(store)["summary"]["connections"]["percent"], 0)


class ConnectionTests(unittest.TestCase):
    def test_source_and_directedness_can_be_checked_with_unresolved_target(self):
        nodes = [node("a"), node("b"), node("e", "connection", directed=True)]
        changed = deepcopy(nodes)
        changed[-1]["directed"] = False
        report = build(case(nodes, changed, endpoints("e", "a", "b"), endpoints("e", "a", None), pairs=[("a", "a"), ("e", "e")]))
        checks = next(item["checks"] for item in report["annotations"] if item["target"]["id"] == "e")
        self.assertEqual(checks["source"], "equal")
        self.assertEqual(checks["target"], "unresolved")
        self.assertEqual(checks["endpoints"], "unresolved")
        self.assertEqual(checks["direction"], "different")

    def test_individual_direction_endpoints_and_type_are_separate(self):
        nodes = [node("a"), node("b"), node("c"), node("e", "connection", "line", directed=True)]
        changed = deepcopy(nodes)
        changed[-1]["type"] = "variant"
        report = build(case(nodes, changed, endpoints("e", "a", "b"), endpoints("e", "b", "c")))
        item = next(item for item in report["annotations"] if item["target"]["id"] == "e")
        self.assertEqual({key: item["checks"][key] for key in ("source", "target", "endpoints", "connectionType")},
                         dict.fromkeys(("source", "target", "endpoints", "connectionType"), "different"))
        self.assertEqual(item["checks"]["direction"], "unresolved")
        self.assertEqual(item["connection"]["reference"]["sourceId"], "a")
        self.assertEqual(item["connection"]["submission"]["targetId"], "c")

    def test_reversed_mapped_connection_has_equal_endpoints_and_different_direction(self):
        nodes = [node("a"), node("b"), node("e", "connection", directed=True)]
        report = build(case(nodes, reference_edges=endpoints("e", "a", "b"), submission_edges=endpoints("e", "b", "a")))
        checks = next(item["checks"] for item in report["annotations"] if item["target"]["id"] == "e")
        self.assertEqual(checks["endpoints"], "equal")
        self.assertEqual(checks["direction"], "different")

    def test_group_difference_does_not_change_individual_checks(self):
        nodes = [node("a"), node("b"), node("e", "connection", directed=True), node("parallel", "connection", directed=True)]
        group = {"referenceConnections": [{"id": "e"}, {"id": "parallel"}],
                 "studentConnections": [{"id": "e"}, {"id": "parallel"}],
                 "referenceEndpointIds": ["a", "b"], "studentEndpointIds": ["a", "b"],
                 "directionStatus": "different", "typeStatus": "equal", "configurationStatus": "different",
                 "referenceOnlyCount": 0, "studentOnlyCount": 0}
        report = build(case(nodes, reference_edges=endpoints("e", "a", "b") + endpoints("parallel", "a", "b"),
                            pairs=[("a", "a"), ("b", "b"), ("e", "e")],
                            provisionalConnectionStructure={"byEndpoints": [group]}))
        items = {item["target"]["id"]: item for item in report["annotations"]}
        self.assertEqual(items["e"]["checks"]["direction"], "equal")
        self.assertEqual(items["parallel"]["checks"]["direction"], "unresolved")
        self.assertFalse(any(hint["code"] == "connection.group_difference" for item in items.values() for hint in item["hints"]))
        self.assertEqual(report["connectionGroups"][0]["checks"]["direction"], "different")

    def test_local_roles_undirected_self_loop_and_unknown_direction(self):
        nodes = [node("a"), node("b"), node("out", "connection", directed=True),
                 node("in", "connection", directed=True), node("loop", "connection", directed=False),
                 node("unknown", "connection", directed=None)]
        edges = endpoints("out", "a", "b") + endpoints("in", "b", "a") + endpoints("loop", "a", "a") + endpoints("unknown", "a", None)
        report = build(case(nodes, reference_edges=edges))
        local = next(item for item in report["annotations"] if item["target"]["id"] == "a")["local"]
        self.assertEqual({key: local[key]["observed"] for key in ("incoming", "outgoing", "undirected", "unresolved")},
                         {"incoming": 1, "outgoing": 1, "undirected": 1, "unresolved": 1})
        self.assertEqual(local["connections"]["observed"], 4)
        self.assertEqual(local["connections"]["unresolvedChecks"], 1)


def containment_evidence(child, parent, sub_child=None, sub_parent=None, status="satisfied", **values):
    return {"referenceSourceId": child, "referenceTargetId": parent, "referenceRole": "content",
            "studentSourceId": sub_child or child, "studentTargetId": sub_parent or parent,
            "studentParentIds": [sub_parent or parent], "status": status,
            "sourceMappingBasis": "unique_exact_label", "targetMappingBasis": "unique_exact_label",
            "decisionBasis": "same_parent" if status == "satisfied" else "source_mapping_not_independent", **values}


class ContainmentTests(unittest.TestCase):
    def test_moved_attribute_preserves_owner_and_immediate_parent(self):
        nodes = [node("a"), node("b"), node("box", "structuralElement"), node("attr", native_type="property")]
        reference_edges = [contains("box", "a", "component"), contains("attr", "box")]
        submission_edges = [contains("box", "a", "component"), contains("attr", "b")]
        row = containment_evidence("attr", "box", status="violated", studentParentIds=["b"], decisionBasis="different_parent",
                                   targetMappingBasis="structural_child_of_mapped_parent")
        report = build(case(nodes, reference_edges=reference_edges, submission_edges=submission_edges,
                            provisionalContainmentEvidence=[row]))
        items = {item["target"]["id"]: item for item in report["annotations"]}
        self.assertEqual(items["attr"]["owner"]["referenceOwnerId"], "a")
        self.assertEqual(items["attr"]["owner"]["submissionOwnerId"], "b")
        self.assertEqual(items["attr"]["containment"]["referenceParents"], [{"parentId": "box", "role": "content"}])
        self.assertEqual(report["containmentRelations"][0]["observedParents"], [{"parentId": "b", "role": "content"}])
        self.assertTrue(all(items[key]["relationIds"] for key in ("attr", "box", "b")))

    def test_dependent_child_stays_unresolved_and_roles_are_retained(self):
        nodes = [node("a"), node("child", native_type="property")]
        row = containment_evidence("child", "a", status="unresolved")
        report = build(case(nodes, reference_edges=[contains("child", "a")], provisionalContainmentEvidence=[row]))
        parent = next(item for item in report["annotations"] if item["target"]["id"] == "a")
        self.assertEqual(parent["local"]["containmentRelations"]["unresolvedReference"], 1)
        self.assertEqual(parent["local"]["childRoles"][0]["unresolvedReference"], 1)
        self.assertEqual(parent["local"]["containmentRelations"]["recognized"], 0)
        self.assertEqual(parent["checks"]["containment"], "unresolved")

    def test_unmatched_child_is_open_reference_not_confirmed_missing(self):
        nodes = [node("a"), node("child", native_type="property")]
        report = build(case(nodes, [node("a")], [contains("child", "a")], [], pairs=[("a", "a")]))
        parent = report["annotations"][0]
        self.assertEqual(parent["local"]["directChildren"]["expected"], 1)
        self.assertEqual(parent["local"]["containmentRelations"]["unresolvedReference"], 1)
        self.assertEqual(report["referenceHints"][0]["referenceId"], "child")
        self.assertFalse(any(word in str(report) for word in ("incorrect", "missing")))

    def test_relation_role_difference_only_with_independent_evidence(self):
        nodes = [node("a"), node("child")]
        store = case(nodes, reference_edges=[contains("child", "a")], submission_edges=[contains("child", "a", "component")],
                     provisionalContainmentEvidence=[containment_evidence("child", "a")])
        self.assertEqual(build(store)["containmentRelations"][0]["roleStatus"], "different")
        store.comparison["provisionalContainmentEvidence"][0]["status"] = "unresolved"
        self.assertEqual(build(store)["containmentRelations"][0]["roleStatus"], "unresolved")


def rehash(report):
    report["analysisKey"] = analysis_key(report)
    report["analysisHash"] = content_hash({key: value for key, value in report.items() if key != "analysisHash"})


class ContractTests(unittest.TestCase):
    def test_legacy_v1_stays_readable(self):
        store = case([node("a")])
        report = build(store)
        for key in ("contractVersion", "producer", "structuralContainers", "connectionGroups", "containmentRelations", "limitations"):
            report.pop(key)
        for item in report["annotations"]:
            for key in ("status", "category", "owner", "containment"):
                item.pop(key)
        rehash(report)
        validate_analysis(report, store)

    def test_baseline_is_deterministic_and_has_no_invented_differences(self):
        nodes = [node("a"), node("child", native_type="property"), node("box", "structuralElement")]
        store = case(nodes, reference_edges=[contains("child", "a")],
                     provisionalContainmentEvidence=[containment_evidence("child", "a")])
        report = build(store)
        validate_analysis(report, store)
        self.assertFalse(any(item["status"] == "different" for item in report["annotations"]))
        self.assertEqual(report, build(store))
        store.indices["student"].nodes = dict(reversed(list(store.indices["student"].nodes.items())))
        self.assertEqual(report, build(store))
        self.assertEqual(len(report["annotations"]), len(nodes))
        self.assertEqual(report["referenceHints"][0]["code"], "reference.not_evaluated")

    def test_structured_codes_scopes_and_original_ids(self):
        store = case([node("a"), node("child")], reference_edges=[contains("child", "a")],
                     submission_edges=[contains("child", "a", "component")],
                     provisionalContainmentEvidence=[containment_evidence("child", "a")])
        report = build(store)
        validate_analysis(report, store)
        hint = report["annotations"][0]["hints"][0]
        self.assertEqual(hint["scope"], "relation")
        self.assertEqual(hint["status"], "different")
        self.assertEqual(hint["parameters"]["submissionId"], "child")
        self.assertIn({"side": "reference", "kind": "modelElement", "id": "child"}, hint["targets"])

    def test_rejects_invalid_counts_ids_codes_and_schema_revision(self):
        store = case([node("a"), node("child")], [node("a")], [contains("child", "a")], [], pairs=[("a", "a")])
        original = build(store)
        mutations = [lambda report: report["summary"]["nodes"].update(recognized=99),
                     lambda report: report["referenceHints"][0].update(code="invented.error"),
                     lambda report: report["referenceHints"][0]["targets"].append({"side": "reference", "kind": "modelElement", "id": "unknown"}),
                     lambda report: report.update(contractVersion="999")]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                report = deepcopy(original)
                mutate(report)
                rehash(report)
                with self.assertRaises(ValueError):
                    validate_analysis(report, store)


if __name__ == "__main__":
    unittest.main()
