import importlib.util
import json
from pathlib import Path
import unittest

from artifacts import _key
from correspondence_state import build_provisional_state
from graph_index import GraphIndex
from initial_evaluation import evaluate_initial_coverage, evaluate_type_comparison
from initial_recognition import evaluate_connections, propose_connections
from test_graph_index import graph, node


ROOT = Path(__file__).resolve().parents[4]
PARSER_SRC = ROOT / "dagu" / "workflow-services" / "graph-parser" / "src"
spec = importlib.util.spec_from_file_location("graph_parser", PARSER_SRC / "parser.py")
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


def connection(identity, source, target, *, directed=True, connection_type="link"):
    item = node(identity, "connection")
    item.update({"type": connection_type, "directed": directed})
    return item, [
        {"kind": "endpoint", "role": "source", "source": source, "target": identity},
        {"kind": "endpoint", "role": "target", "source": identity, "target": target},
    ]


def indices_with_connections(reference, student):
    indices = {}
    for side, specifications in (("reference", reference), ("student", student)):
        nodes = [node(name) for name in ("a", "b", "c")]
        edges = []
        for identity, source, target, options in specifications:
            item, relations = connection(identity, source, target, **options)
            nodes.append(item)
            edges.extend(relations)
        indices[side] = GraphIndex(graph(nodes, edges))
    mapping = [{"referenceId": name, "studentId": name} for name in ("a", "b", "c")]
    return indices, mapping


class ConnectionStructureTests(unittest.TestCase):
    def test_type_comparison_uses_only_compatible_connection_proposals(self):
        indices, _mapping = indices_with_connections(
            [("r1", "a", "b", {"connection_type": "first"}),
             ("r2", "a", "c", {"connection_type": "first"})],
            [("s1", "a", "b", {"connection_type": "second"}),
             ("s2", "a", "c", {"connection_type": "second"})],
        )
        indices["reference"].nodes["r1"]["comparisonGroup"] = "links"
        indices["student"].nodes["s1"]["comparisonGroup"] = "links"
        elements = [{"referenceId": name, "studentId": name, "reason": "unique_exact_label",
                     "dependsOn": [], "status": "provisional"} for name in ("a", "b", "c")]
        connections = propose_connections(indices, elements)
        data = evaluate_type_comparison(indices, elements, connections["proposals"])["connections"]
        self.assertEqual((data["referenceCount"], data["mappedCount"], data["evaluatedCount"]), (2, 1, 1))
        self.assertEqual((data["sameTypeCount"], data["compatibleTypeDifferenceCount"], data["unresolvedCount"]),
                         (0, 1, 1))
        self.assertEqual(data["compatibleTypeDifferencePercentage"], 100)
        self.assertEqual(data["unresolvedReferenceIds"], ["r2"])
        first, second = data["pairs"]
        self.assertEqual((first["referenceType"], first["studentType"], first["comparisonGroup"]),
                         ("first", "second", "links"))
        self.assertEqual(first["dependsOn"], [{"referenceId": "a", "studentId": "a"},
                                              {"referenceId": "b", "studentId": "b"}])
        self.assertEqual(second["status"], "unresolved")

    def test_ambiguous_parallel_connections_have_no_invented_type_differences(self):
        indices, _mapping = indices_with_connections(
            [("r1", "a", "b", {}), ("r2", "a", "b", {})],
            [("s1", "a", "b", {}), ("s2", "a", "b", {})],
        )
        elements = [{"referenceId": name, "studentId": name, "reason": "unique_exact_label",
                     "dependsOn": [], "status": "provisional"} for name in ("a", "b", "c")]
        connections = propose_connections(indices, elements)
        data = evaluate_type_comparison(indices, elements, connections["proposals"])["connections"]
        self.assertEqual((data["mappedCount"], data["unresolvedCount"]), (0, 2))
        self.assertEqual(data["compatibleTypeDifferenceCount"], 0)
        self.assertIsNone(data["compatibleTypeDifferencePercentage"])

    def test_parallel_edges_are_counted_without_forcing_identity(self):
        indices, mapping = indices_with_connections(
            [("r1", "a", "b", {}), ("r2", "a", "b", {})],
            [("s1", "a", "b", {})],
        )
        result = evaluate_connections(indices, mapping)
        row = result["byEndpoints"][0]
        self.assertEqual((row["referenceCount"], row["studentCount"]), (2, 1))
        self.assertEqual((row["referenceOnlyCount"], row["studentOnlyCount"]), (1, 0))
        self.assertEqual(row["directionStatus"], "not_evaluated")
        self.assertEqual(row["typeStatus"], "not_evaluated")
        self.assertNotIn("pairs", row)

    def test_direction_type_and_undirected_orientation(self):
        indices, mapping = indices_with_connections(
            [("r1", "a", "b", {"directed": True, "connection_type": "first"}),
             ("r2", "a", "c", {"directed": False})],
            [("s1", "b", "a", {"directed": True, "connection_type": "second"}),
             ("s2", "c", "a", {"directed": False})],
        )
        rows = {tuple(row["referenceEndpointIds"]): row for row in
                evaluate_connections(indices, mapping)["byEndpoints"]}
        self.assertEqual(rows["a", "b"]["directionStatus"], "different")
        self.assertEqual(rows["a", "b"]["typeStatus"], "different")
        self.assertEqual(rows["a", "c"]["directionStatus"], "equal")
        self.assertEqual(rows["a", "c"]["typeStatus"], "equal")

    def test_open_or_unmapped_endpoints_remain_unresolved(self):
        indices, mapping = indices_with_connections(
            [("r1", "a", "b", {})],
            [("s1", "a", None, {}), ("s2", "a", "c", {})],
        )
        result = evaluate_connections(indices, mapping[:2])
        self.assertEqual(result["completeness"], "partial")
        self.assertEqual(result["unresolvedReferenceConnectionIds"], [])
        self.assertEqual(result["unresolvedStudentConnectionIds"], ["s1", "s2"])
        self.assertEqual(result["byEndpoints"][0]["referenceOnlyCount"], 1)

    def test_unknown_direction_or_language_does_not_claim_difference(self):
        indices, mapping = indices_with_connections(
            [("r1", "a", "b", {"directed": None})],
            [("s1", "a", "b", {})],
        )
        indices["student"].nodes["s1"]["language"] = None
        indices["student"].nodes["s1"]["languageResolution"] = "unresolved"
        row = evaluate_connections(indices, mapping)["byEndpoints"][0]
        self.assertEqual(row["directionStatus"], "not_evaluated")
        self.assertEqual(row["typeStatus"], "not_evaluated")

    def test_parallel_direction_and_type_combinations_are_compared_together(self):
        indices, mapping = indices_with_connections(
            [("r1", "a", "b", {"connection_type": "first"}),
             ("r2", "b", "a", {"connection_type": "second"})],
            [("s1", "a", "b", {"connection_type": "second"}),
             ("s2", "b", "a", {"connection_type": "first"})],
        )
        row = evaluate_connections(indices, mapping)["byEndpoints"][0]
        self.assertEqual(row["directionStatus"], "equal")
        self.assertEqual(row["typeStatus"], "equal")
        self.assertEqual(row["configurationStatus"], "different")

    def test_different_element_ids_use_the_provisional_mapping(self):
        reference_link, reference_edges = connection("reference-link", "r-a", "r-b")
        student_link, student_edges = connection("student-link", "s-z", "s-a")
        indices = {
            "reference": GraphIndex(graph([node("r-a"), node("r-b"), reference_link], reference_edges)),
            "student": GraphIndex(graph([node("s-z"), node("s-a"), student_link], student_edges)),
        }
        mapping = [{"referenceId": "r-a", "studentId": "s-z"},
                   {"referenceId": "r-b", "studentId": "s-a"}]
        result = evaluate_connections(indices, mapping)
        row = result["byEndpoints"][0]
        self.assertEqual(row["referenceEndpointIds"], ["r-a", "r-b"])
        self.assertEqual(row["studentEndpointIds"], ["s-a", "s-z"])
        self.assertEqual(row["configurationStatus"], "equal")
        self.assertEqual(evaluate_connections(indices, list(reversed(mapping))), result)


class LaboratoryConnectionRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        versions = ROOT / "api" / "src" / "modeling_api" / "db" / "migrations" / "versions"
        language_data = json.loads((versions / "v00_initial_data" / "serm.json").read_text(encoding="utf-8"))
        language_data["evaluation"] = {"comparisonGroups": [
            {"id": "serm-entity", "name": "Entity",
             "elementTypes": ["serm-entity", "serm-er", "serm-relationship"]},
            {"id": "serm-attribute", "name": "Attribute",
             "elementTypes": ["serm-attribute", "serm-key-attribute"]},
            {"id": "serm-connection", "name": "Relationship",
             "connectionTypes": ["serm-0-1", "serm-0-n", "serm-1-1", "serm-1-n"]},
        ]}
        language_id = "a09ff8fb-5a26-4621-91e7-003cee10c555"
        version_id = "4b748971-57b5-575f-a744-8617241d081f"
        cls.graphs = {}
        for name, path in (
            ("reference", versions / "v12_laboratory_management" / "sample_solution.json"),
            ("m06a", versions / "v14_laboratory_structure_models" / "m06a.json"),
            ("m06b", versions / "v14_laboratory_structure_models" / "m06b.json"),
        ):
            model = json.loads(path.read_text(encoding="utf-8"))["model"]
            parsed = parser.parse_model({
                "source": {"key": name},
                "model": model["version"]["data"],
                "languages": [{"languageId": language_id, "versionId": version_id, "data": language_data}],
            })
            if parsed["diagnostics"]:
                raise AssertionError(parsed["diagnostics"])
            cls.graphs[name] = GraphIndex(parsed["graph"])

    def evaluate_model(self, name, include_type_comparison=False):
        reference, student = self.graphs["reference"], self.graphs[name]
        reference_elements = {key: value for key, value in reference.nodes.items() if value["kind"] == "modelElement"}
        student_elements = {key: value for key, value in student.nodes.items() if value["kind"] == "modelElement"}
        candidates = {"synonymMatrix": [
            {"referenceElementId": reference_id, "referenceLabel": reference_node["label"],
             "matches": [
                 {"submissionElementId": student_id, "submissionLabel": student_node["label"]}
                 for student_id, student_node in student_elements.items()
                 if _key(reference_node) is not None and _key(reference_node) == _key(student_node)
             ]}
            for reference_id, reference_node in reference_elements.items()
        ]}
        indices = {"reference": reference, "student": student}
        state = build_provisional_state(indices, candidates)
        evaluation = evaluate_initial_coverage(indices, state)
        self.assertEqual(evaluation["metrics"]["overall"]["anchorCoverage"], 1.0)
        self.assertEqual(evaluation["unresolvedReferenceIds"], [])
        self.assertEqual(evaluation["unresolvedStudentIds"], [])
        result = evaluate_connections(indices, evaluation["mapping"]["provisionalElements"])
        self.assertEqual(result["completeness"], "complete")
        rows = {
            tuple(sorted(reference.nodes[identity]["label"] for identity in row["referenceEndpointIds"])): row
            for row in result["byEndpoints"]
        }
        if include_type_comparison:
            elements = evaluation["mapping"]["provisionalElements"]
            proposals = propose_connections(indices, elements)["proposals"]
            return rows, evaluate_type_comparison(indices, elements, proposals)
        return rows

    def test_m06a_removed_added_and_changed_endpoint(self):
        rows = self.evaluate_model("m06a")
        self.assertEqual(rows["Arbeitseinsatz", "Wissen\nschaftler"]["referenceOnlyCount"], 1)
        self.assertEqual(rows["Geräte", "Versuch"]["studentOnlyCount"], 1)
        self.assertEqual(rows["Etage", "Gebäude"]["referenceOnlyCount"], 1)
        self.assertEqual(rows["Etage", "Forschungs\nprojekt"]["studentOnlyCount"], 1)

    def test_m06b_endpoint_reversal_and_concrete_type(self):
        rows, types = self.evaluate_model("m06b", include_type_comparison=True)
        self.assertEqual(rows["Arbeitseinsatz", "Laborraum"]["referenceOnlyCount"], 1)
        self.assertEqual(rows["Laborraum", "Projekt\nbeteiligung"]["studentOnlyCount"], 1)
        self.assertEqual(rows["Arbeitseinsatz", "Versuch"]["directionStatus"], "different")
        self.assertEqual(rows["Etage", "Gebäude"]["typeStatus"], "different")
        changed_id = rows["Etage", "Gebäude"]["referenceConnections"][0]["id"]
        changed = next(item for item in types["connections"]["pairs"] if item["referenceId"] == changed_id)
        self.assertEqual((changed["referenceType"], changed["studentType"], changed["comparisonGroup"]),
                         ("serm-1-n", "serm-0-1", "serm-connection"))
        self.assertEqual(changed["status"], "compatible_type_difference")
        self.assertEqual(changed["mappingStatus"], "provisional")

    def test_reference_has_no_connection_differences(self):
        rows = self.evaluate_model("reference")
        for row in rows.values():
            self.assertEqual(row["referenceOnlyCount"], 0)
            self.assertEqual(row["studentOnlyCount"], 0)
            self.assertEqual(row["configurationStatus"], "equal")


if __name__ == "__main__":
    unittest.main()
