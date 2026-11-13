import copy
import json
import unittest

from artifacts import _key
from correspondence_state import build_provisional_state
from graph_index import GraphIndex
from initial_evaluation import evaluate_initial_coverage
from initial_structure import evaluate_containment_relations, evaluate_provisional_owners
from test_graph_index import graph, node
from test_initial_connections import ROOT, parser
from test_structural_evidence import candidates, contains, index


def proposal(reference, student, reason="unique_exact_label", depends_on=None):
    return {"referenceId": reference, "studentId": student, "reason": reason,
            "dependsOn": depends_on or [], "status": "provisional"}


class ProvisionalOwnerTests(unittest.TestCase):
    def setUp(self):
        self.indices = {
            "reference": index(
                {"r-person": "modelElement", "r-dept": "modelElement",
                 "r-unanchored": "modelElement", "r-box": "structuralElement",
                 "r-good": "modelElement", "r-wrong": "modelElement",
                 "r-unknown": "modelElement", "r-root": "modelElement", "r-alone": "modelElement"},
                [contains("r-good", "r-box"), contains("r-box", "r-person"),
                 contains("r-wrong", "r-person"), contains("r-unknown", "r-unanchored")],
            ),
            "student": index(
                {"s-person": "modelElement", "s-dept": "modelElement",
                 "s-unanchored": "modelElement", "s-box": "structuralElement",
                 "s-good": "modelElement", "s-wrong": "modelElement",
                 "s-unknown": "modelElement", "s-root": "modelElement", "s-alone": "modelElement"},
                [contains("s-good", "s-box"), contains("s-box", "s-person"),
                 contains("s-wrong", "s-dept"), contains("s-unknown", "s-unanchored"),
                 contains("s-root", "s-person")],
            ),
        }
        self.candidates = candidates([
            ("r-person", "Person", [("s-person", "Person")]),
            ("r-dept", "Department", [("s-dept", "Department")]),
            ("r-good", "Good", [("s-good", "Good"), ("s-wrong", "Wrong"), ("s-alone", "Alone")]),
            ("r-wrong", "Wrong", [("s-wrong", "Wrong")]),
            ("r-unknown", "Unknown", [("s-unknown", "Unknown")]),
            ("r-root", "Root", [("s-root", "Root")]),
            ("r-alone", "Alone", [("s-alone", "Alone")]),
            ("r-unanchored", "Other", [("s-unanchored", "Other")]),
        ])
        self.mapping = [
            proposal("r-person", "s-person"), proposal("r-dept", "s-dept"),
            proposal("r-good", "s-good", "consistent_owner_anchor",
                     [{"referenceId": "r-person", "studentId": "s-person"}]),
            proposal("r-wrong", "s-wrong"), proposal("r-unknown", "s-unknown"),
            proposal("r-root", "s-root"), proposal("r-alone", "s-alone"),
        ]

    def test_owner_states_intervals_and_structural_paths(self):
        result = evaluate_provisional_owners(self.indices, self.candidates, self.mapping)
        pairs = {(item["referenceId"], item["studentId"]): item for item in result["pairs"]}
        self.assertEqual(len(pairs), 7)
        self.assertNotIn(("r-good", "s-wrong"), pairs)
        self.assertNotIn(("r-unanchored", "s-unanchored"), pairs)
        self.assertEqual(pairs["r-good", "s-good"]["status"], "satisfied")
        self.assertEqual(pairs["r-wrong", "s-wrong"]["status"], "violated")
        self.assertEqual(pairs["r-root", "s-root"]["status"], "violated")
        self.assertEqual(pairs["r-unknown", "s-unknown"]["status"], "unresolved")
        self.assertEqual(pairs["r-alone", "s-alone"]["status"], "not_applicable")
        self.assertEqual(pairs["r-good", "s-good"]["referenceOwnerId"], "r-person")
        self.assertEqual(pairs["r-good", "s-good"]["studentOwnerId"], "s-person")
        self.assertEqual(pairs["r-good", "s-good"]["referenceParentIds"], ["r-box"])
        self.assertEqual(pairs["r-good", "s-good"]["referenceContainmentPaths"],
                         [["r-good", "r-box", "r-person"]])
        self.assertEqual(pairs["r-good", "s-good"]["studentContainmentPaths"],
                         [["s-good", "s-box", "s-person"]])
        self.assertEqual(result["metrics"], {
            "expected": 4, "satisfied": 1, "violated": 2, "unresolved": 1,
            "agreement": {"lower": 0.25, "upper": 0.5},
        })

    def test_both_root_and_empty_mapping_have_null_interval(self):
        for mapping in ([], [proposal("r-alone", "s-alone")]):
            with self.subTest(mapping=mapping):
                result = evaluate_provisional_owners(self.indices, self.candidates, mapping)
                self.assertEqual(result["metrics"], {
                    "expected": 0, "satisfied": 0, "violated": 0, "unresolved": 0,
                    "agreement": {"lower": None, "upper": None},
                })
                if mapping:
                    self.assertEqual(result["pairs"][0]["status"], "not_applicable")

    def test_reference_contained_student_root_is_violated(self):
        result = evaluate_provisional_owners(
            self.indices, self.candidates, [proposal("r-good", "s-alone")]
        )
        self.assertEqual(result["pairs"][0]["status"], "violated")
        self.assertEqual(result["metrics"]["agreement"], {"lower": 0.0, "upper": 0.0})

    def test_only_independent_exact_proposals_are_owner_context(self):
        mapping = copy.deepcopy(self.mapping)
        mapping[0]["reason"] = "consistent_owner_anchor"
        result = evaluate_provisional_owners(self.indices, self.candidates, mapping)
        good = next(item for item in result["pairs"] if item["referenceId"] == "r-good")
        self.assertEqual(good["status"], "unresolved")
        mapping[0]["reason"] = "unique_exact_label"
        mapping[0]["dependsOn"] = [{"referenceId": "r-dept", "studentId": "s-dept"}]
        result = evaluate_provisional_owners(self.indices, self.candidates, mapping)
        good = next(item for item in result["pairs"] if item["referenceId"] == "r-good")
        self.assertEqual(good["status"], "unresolved")

    def test_ambiguous_and_cyclic_paths_do_not_claim_consistency(self):
        indices = {
            "reference": index(
                {"child": "modelElement", "box": "structuralElement",
                 "a": "modelElement", "b": "modelElement"},
                [contains("child", "box"), contains("box", "a"), contains("box", "b")],
            ),
            "student": index(
                {"child": "modelElement", "box": "structuralElement", "owner": "modelElement"},
                [contains("child", "box"), contains("box", "owner"), contains("owner", "box")],
            ),
        }
        matrix = candidates([("child", "Child", [("child", "Child")]), ("a", "A", [("owner", "A")])])
        result = evaluate_provisional_owners(indices, matrix, [proposal("child", "child"), proposal("a", "owner")])
        child = next(item for item in result["pairs"] if item["referenceId"] == "child")
        self.assertEqual(child["status"], "unresolved")
        self.assertEqual(child["referenceContainmentPaths"], [["child", "box", "a"], ["child", "box", "b"]])
        self.assertEqual(child["studentContainmentPaths"], [["child", "box", "owner", "box"]])

    def test_order_and_inputs_are_preserved(self):
        original_candidates = copy.deepcopy(self.candidates)
        original_mapping = copy.deepcopy(self.mapping)
        original_indices = {side: copy.deepcopy(vars(value)) for side, value in self.indices.items()}
        expected = evaluate_provisional_owners(self.indices, self.candidates, self.mapping)
        reordered = copy.deepcopy(self.candidates)
        reordered["synonymMatrix"].reverse()
        for row in reordered["synonymMatrix"]:
            row["matches"].reverse()
        actual = evaluate_provisional_owners(self.indices, reordered, list(reversed(self.mapping)))
        self.assertEqual(actual, expected)
        self.assertEqual(self.candidates, original_candidates)
        self.assertEqual(self.mapping, original_mapping)
        self.assertEqual({side: vars(value) for side, value in self.indices.items()}, original_indices)

    def test_invalid_or_duplicate_candidate_proposals_are_rejected(self):
        item = proposal("r-good", "s-good")
        with self.assertRaisesRegex(ValueError, "duplicate pairs"):
            evaluate_provisional_owners(self.indices, self.candidates, [item, item])
        with self.assertRaisesRegex(ValueError, "candidate pairs"):
            evaluate_provisional_owners(self.indices, self.candidates, [proposal("r-good", "missing")])


class ContainmentRelationTests(unittest.TestCase):
    @staticmethod
    def make_index(prefix, child_owner="box", extra_edges=()):
        elements = [node(f"{prefix}-{identity}") for identity in ("owner", "other", "child")]
        for identity in ("outer", "box", "other-box"):
            item = node(f"{prefix}-{identity}", "structuralElement")
            item["type"] = "box" if identity in ("box", "other-box") else "outer"
            item["definition"] = {"languageId": "test", "versionId": "1", "path": item["type"]}
            elements.append(item)
        edges = [
            contains(f"{prefix}-outer", f"{prefix}-owner"),
            contains(f"{prefix}-box", f"{prefix}-outer"),
            contains(f"{prefix}-other-box", f"{prefix}-other"),
            contains(f"{prefix}-child", f"{prefix}-{child_owner}"),
            *extra_edges,
        ]
        return GraphIndex(graph(elements, edges))

    def setUp(self):
        self.indices = {"reference": self.make_index("r"), "student": self.make_index("s")}
        self.mapping = [proposal("r-owner", "s-owner"), proposal("r-other", "s-other"),
                        proposal("r-child", "s-child")]

    def test_nested_relations_keep_paths_and_do_not_self_confirm_containers(self):
        result = evaluate_containment_relations(self.indices, self.mapping)
        rows = {item["referenceSourceId"]: item for item in result["relations"]}
        self.assertEqual(result["metrics"], {
            "referenceRelationCount": 4, "satisfied": 1, "violated": 0, "unresolved": 3,
            "agreement": {"lower": 0.25, "upper": 1.0},
        })
        self.assertEqual(rows["r-child"]["status"], "satisfied")
        self.assertEqual(rows["r-child"]["referenceContainmentPaths"],
                         [["r-child", "r-box", "r-outer", "r-owner"]])
        self.assertEqual(rows["r-child"]["studentContainmentPaths"],
                         [["s-child", "s-box", "s-outer", "s-owner"]])
        self.assertEqual(rows["r-child"]["targetMappingDependencies"], [
            {"referenceId": "r-outer", "studentId": "s-outer"},
            {"referenceId": "r-owner", "studentId": "s-owner"},
        ])
        self.assertEqual(rows["r-box"]["status"], "unresolved")
        self.assertEqual(rows["r-box"]["decisionBasis"], "structural_source_depends_on_relation")

    def test_moved_independent_child_is_violated(self):
        self.indices["student"] = self.make_index("s", child_owner="other-box")
        result = evaluate_containment_relations(self.indices, self.mapping)
        row = next(item for item in result["relations"] if item["referenceSourceId"] == "r-child")
        self.assertEqual(row["status"], "violated")
        self.assertEqual(row["referenceTargetId"], "r-box")
        self.assertEqual(row["studentSourceId"], "s-child")
        self.assertEqual(row["studentTargetId"], "s-box")
        self.assertEqual(row["decisionBasis"], "different_parent")

    def test_missing_and_owner_dependent_child_remain_unresolved(self):
        for mapping in (self.mapping[:2], [
            *self.mapping[:2],
            proposal("r-child", "s-child", "consistent_owner_anchor",
                     [{"referenceId": "r-owner", "studentId": "s-owner"}]),
        ], [
            *self.mapping[:2], proposal("r-child", "s-child", "supported_semantic_evidence"),
        ]):
            with self.subTest(mapping=mapping):
                result = evaluate_containment_relations(self.indices, mapping)
                row = next(item for item in result["relations"] if item["referenceSourceId"] == "r-child")
                self.assertEqual(row["status"], "unresolved")
                self.assertEqual(result["metrics"]["referenceRelationCount"], 4)

    def test_dependent_parent_does_not_confirm_a_direct_relation(self):
        indices = {
            "reference": index({"r-child": "modelElement", "r-owner": "modelElement"},
                               [contains("r-child", "r-owner")]),
            "student": index({"s-child": "modelElement", "s-owner": "modelElement"},
                             [contains("s-child", "s-owner")]),
        }
        mapping = [proposal("r-child", "s-child"), proposal("r-owner", "s-owner", "supported_semantic_evidence")]
        row = evaluate_containment_relations(indices, mapping)["relations"][0]
        self.assertEqual(row["status"], "unresolved")
        self.assertEqual(row["decisionBasis"], "target_mapping_not_independent")

    def test_ambiguous_and_cyclic_paths_are_unresolved(self):
        self.indices["student"] = self.make_index(
            "s", extra_edges=[contains("s-child", "s-other-box"), contains("s-owner", "s-outer")]
        )
        result = evaluate_containment_relations(self.indices, self.mapping)
        row = next(item for item in result["relations"] if item["referenceSourceId"] == "r-child")
        self.assertEqual(row["status"], "unresolved")
        self.assertEqual(len(row["studentContainmentPaths"]), 2)

    def test_multiple_containers_with_same_definition_remain_unresolved(self):
        student = self.make_index("s")
        duplicate = node("s-duplicate", "structuralElement")
        duplicate["type"] = student.nodes["s-box"]["type"]
        duplicate["definition"] = student.nodes["s-box"]["definition"]
        nodes = list(student.nodes.values()) + [duplicate]
        edges = [edge for values in student.parents.values() for edge in values]
        edges.append(contains("s-duplicate", "s-outer"))
        self.indices["student"] = GraphIndex(graph(nodes, edges))
        result = evaluate_containment_relations(self.indices, self.mapping)
        row = next(item for item in result["relations"] if item["referenceSourceId"] == "r-child")
        self.assertEqual(row["status"], "unresolved")
        self.assertEqual(row["decisionBasis"], "target_mapping_missing")

    def test_empty_reference_and_unmapped_non_model_relations(self):
        reference = GraphIndex(graph([node("label", "connectionLabel"), node("link", "connection")],
                                     [contains("label", "link")]))
        student = GraphIndex(graph([], []))
        result = evaluate_containment_relations({"reference": reference, "student": student}, [])
        self.assertEqual(result["metrics"]["referenceRelationCount"], 1)
        self.assertEqual(result["metrics"]["unresolved"], 1)
        self.assertEqual(result["relations"][0]["referenceContainmentPaths"], [["label", "link"]])
        empty = evaluate_containment_relations({"reference": student, "student": student}, [])
        self.assertEqual(empty["metrics"]["agreement"], {"lower": None, "upper": None})

    def test_duplicate_mapping_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            evaluate_containment_relations(self.indices, [self.mapping[0], self.mapping[0]])

    def test_order_and_inputs_are_preserved(self):
        before = {side: copy.deepcopy(vars(value)) for side, value in self.indices.items()}
        mapping = copy.deepcopy(self.mapping)
        expected = evaluate_containment_relations(self.indices, self.mapping)
        self.assertEqual(evaluate_containment_relations(self.indices, list(reversed(self.mapping))), expected)
        self.assertEqual(self.mapping, mapping)
        self.assertEqual({side: vars(value) for side, value in self.indices.items()}, before)


class LaboratoryContainmentRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        versions = ROOT / "api" / "src" / "modeling_api" / "db" / "migrations" / "versions"
        language = json.loads((versions / "v00_initial_data" / "serm.json").read_text(encoding="utf-8"))
        language["evaluation"] = {"comparisonGroups": [
            {"id": "serm-entity", "name": "Entity",
             "elementTypes": ["serm-entity", "serm-er", "serm-relationship"]},
            {"id": "serm-attribute", "name": "Attribute",
             "elementTypes": ["serm-attribute", "serm-key-attribute"]},
        ]}
        language_ref = {"languageId": "a09ff8fb-5a26-4621-91e7-003cee10c555",
                        "versionId": "4b748971-57b5-575f-a744-8617241d081f", "data": language}
        cls.graphs = {}
        for name, path in (
            ("reference", versions / "v12_laboratory_management" / "sample_solution.json"),
            ("m02", versions / "v14_laboratory_structure_models" / "m02.json"),
            ("m03", versions / "v14_laboratory_structure_models" / "m03.json"),
            ("m05", versions / "v14_laboratory_structure_models" / "m05.json"),
            ("m08", versions / "v14_laboratory_structure_models" / "m08.json"),
        ):
            model = json.loads(path.read_text(encoding="utf-8"))["model"]
            parsed = parser.parse_model({"source": {"key": name}, "model": model["version"]["data"],
                                         "languages": [language_ref]})
            if parsed["diagnostics"]:
                raise AssertionError(parsed["diagnostics"])
            cls.graphs[name] = GraphIndex(parsed["graph"])

    def evaluate_model(self, name):
        indices = {"reference": self.graphs["reference"], "student": self.graphs[name]}
        elements = {
            side: {identity: item for identity, item in index.nodes.items()
                   if item["kind"] == "modelElement" and item["comparisonRole"] == "semantic"}
            for side, index in indices.items()
        }
        matrix = {"synonymMatrix": [
            {"referenceElementId": ref_id, "referenceLabel": ref["label"], "matches": [
                {"submissionElementId": sub_id, "submissionLabel": sub["label"]}
                for sub_id, sub in elements["student"].items()
                if _key(ref) is not None and _key(ref) == _key(sub)
            ]}
            for ref_id, ref in elements["reference"].items()
        ]}
        state = build_provisional_state(indices, matrix)
        mapping = evaluate_initial_coverage(indices, state)["mapping"]["provisionalElements"]
        old = evaluate_provisional_owners(indices, matrix, mapping)
        result = evaluate_containment_relations(indices, mapping)
        self.assertEqual(result["metrics"]["referenceRelationCount"], 48)
        self.assertEqual(sum(result["metrics"][status] for status in ("satisfied", "violated", "unresolved")), 48)
        return indices["reference"], old, result

    def test_m03_moved_attribute_is_violated(self):
        reference, old, result = self.evaluate_model("m03")
        self.assertEqual((old["metrics"]["satisfied"], old["metrics"]["violated"]), (36, 1))
        moved = [row for row in result["relations"]
                 if "Größe" in reference.nodes[row["referenceSourceId"]].get("label", "")]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["status"], "violated")

    def test_reference_has_no_violations(self):
        _reference, old, result = self.evaluate_model("reference")
        self.assertEqual((old["metrics"]["satisfied"], old["metrics"]["expected"]), (38, 38))
        self.assertEqual(result["metrics"]["violated"], 0)
        self.assertEqual(result["metrics"]["agreement"]["upper"], 1.0)

    def test_m05_swapped_containers_do_not_confirm_dependent_matches(self):
        reference, old, result = self.evaluate_model("m05")
        self.assertEqual((old["metrics"]["satisfied"], old["metrics"]["expected"]), (36, 36))
        self.assertLess(result["metrics"]["agreement"]["lower"], 1)
        moved = [row for row in result["relations"] if any(
            name in reference.nodes[row["referenceSourceId"]].get("label", "")
            for name in ("GebäudeNr.", "GeräteNr."))
            and row["decisionBasis"] == "source_mapping_missing"]
        self.assertEqual(len(moved), 2)
        self.assertTrue(all(row["status"] == "unresolved" for row in moved))
        self.assertEqual({reference.nodes[reference.owner(row["referenceSourceId"])]["label"] for row in moved},
                         {"Gebäude", "Geräte"})
        names = [row for row in result["relations"]
                 if "Bezeichnung" in reference.nodes[row["referenceSourceId"]].get("label", "")
                 and reference.nodes[reference.owner(row["referenceSourceId"])]["label"] in ("Gebäude", "Geräte")]
        self.assertEqual(len(names), 2)
        self.assertTrue(all(row["sourceMappingBasis"] == "consistent_owner_anchor"
                            and row["referenceSourceId"] != row["studentSourceId"] for row in names))
        self.assertTrue(all(row["status"] == "unresolved" for row in names))

    def test_m08_unresolved_moved_attribute_is_in_denominator(self):
        reference, old, result = self.evaluate_model("m08")
        self.assertEqual((old["metrics"]["satisfied"], old["metrics"]["expected"]), (35, 36))
        project_numbers = [row for row in result["relations"]
                           if "ProjektNr." in reference.nodes[row["referenceSourceId"]].get("label", "")
                           and reference.nodes[reference.owner(row["referenceSourceId"])]["label"]
                           == "Forschungs\nprojekt"]
        self.assertTrue(any(row["status"] == "unresolved"
                            and row["decisionBasis"] == "source_mapping_missing" for row in project_numbers))

    def test_m02_renamed_owners_are_supported_by_children(self):
        reference, old, result = self.evaluate_model("m02")
        owner_rows = [row for row in result["relations"]
                      if row["targetMappingBasis"] == "independent_child_evidence"]
        owners = {reference.nodes[row["referenceTargetId"]]["label"]:
                  self.graphs["m02"].nodes[row["studentTargetId"]]["label"] for row in owner_rows}
        self.assertEqual(owners, {"Gebäude": "Bauwerk", "Geräte": "Apparate"})
        self.assertTrue(all(row["status"] == "unresolved" for row in owner_rows))
        self.assertEqual((old["metrics"]["satisfied"], old["metrics"]["unresolved"]), (32, 4))


if __name__ == "__main__":
    unittest.main()
