import copy
import unittest

from graph_index import GraphIndex
from matching import propose_exact_anchors
from structural_evidence import analyze_containment
from test_graph_index import graph, node


def contains(child, parent):
    return {"kind": "contains", "role": "content", "source": child, "target": parent}


def index(kinds, edges):
    return GraphIndex(graph([node(identity, kind) for identity, kind in kinds.items()], edges))


def candidates(rows):
    return {"synonymMatrix": [
        {
            "referenceElementId": reference_id,
            "referenceLabel": label,
            "matches": [
                {"submissionElementId": student_id, "submissionLabel": student_label}
                for student_id, student_label in matches
            ],
        }
        for reference_id, label, matches in rows
    ]}


class ContainmentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.indices = {
            "reference": index(
                {"r-person": "modelElement", "r-dept": "modelElement",
                 "r-person-box": "structuralElement", "r-dept-box": "structuralElement",
                 "r-person-name": "modelElement", "r-dept-name": "modelElement"},
                [contains("r-person-name", "r-person-box"), contains("r-person-box", "r-person"),
                 contains("r-dept-name", "r-dept-box"), contains("r-dept-box", "r-dept")],
            ),
            "student": index(
                {"s-person": "modelElement", "s-dept": "modelElement",
                 "s-person-box": "structuralElement", "s-dept-box": "structuralElement",
                 "s-person-name": "modelElement", "s-dept-name": "modelElement"},
                [contains("s-person-name", "s-person-box"), contains("s-person-box", "s-person"),
                 contains("s-dept-name", "s-dept-box"), contains("s-dept-box", "s-dept")],
            ),
        }
        self.candidates = candidates([
            ("r-person", "Person", [("s-person", "Person"), ("s-dept", "Department")]),
            ("r-dept", "Department", [("s-person", "Person"), ("s-dept", "Department")]),
            ("r-person-name", "Name", [("s-person-name", "Name"), ("s-dept-name", "Name")]),
            ("r-dept-name", "Name", [("s-person-name", "Name"), ("s-dept-name", "Name")]),
        ])
        self.anchors, _ = propose_exact_anchors(self.indices, self.candidates)

    def test_correct_and_conflicting_owners_preserve_all_candidates_and_containers(self):
        original_candidates = copy.deepcopy(self.candidates)
        original_anchors = copy.deepcopy(self.anchors)
        result = analyze_containment(self.indices, self.candidates, self.anchors)
        by_pair = {(item["referenceId"], item["studentId"]): item for item in result}
        self.assertEqual(len(result), 8)
        self.assertEqual(by_pair["r-person-name", "s-person-name"]["ownerAnchorRelation"], "consistent")
        self.assertEqual(by_pair["r-dept-name", "s-dept-name"]["ownerAnchorRelation"], "consistent")
        self.assertEqual(by_pair["r-person-name", "s-dept-name"]["ownerAnchorRelation"], "conflicting")
        self.assertEqual(by_pair["r-dept-name", "s-person-name"]["ownerAnchorRelation"], "conflicting")
        pair = by_pair["r-person-name", "s-person-name"]
        self.assertEqual(pair["referenceParentIds"], ["r-person-box"])
        self.assertEqual(pair["studentParentIds"], ["s-person-box"])
        self.assertEqual(pair["referenceOwnerId"], "r-person")
        self.assertEqual(pair["studentOwnerId"], "s-person")
        self.assertEqual(pair["referenceContainmentPaths"], [["r-person-name", "r-person-box", "r-person"]])
        self.assertEqual(pair["studentContainmentPaths"], [["s-person-name", "s-person-box", "s-person"]])
        self.assertEqual(self.candidates, original_candidates)
        self.assertEqual(self.anchors, original_anchors)

    def test_unknown_when_owner_or_anchor_is_unavailable(self):
        result = analyze_containment(self.indices, self.candidates, [])
        self.assertTrue(all(item["ownerAnchorRelation"] == "unknown" for item in result))
        pair = next(item for item in result if item["referenceId"] == "r-person")
        self.assertIsNone(pair["referenceOwnerId"])
        self.assertEqual(pair["referenceParentIds"], [])
        self.assertEqual(pair["referenceContainmentPaths"], [["r-person"]])

    def test_equal_ids_across_graphs_do_not_imply_an_anchor(self):
        indices = {
            side: index({"child": "modelElement", "owner": "modelElement"}, [contains("child", "owner")])
            for side in ("reference", "student")
        }
        matrix = candidates([("child", "Name", [("child", "Name")])])
        result = analyze_containment(indices, matrix, [])
        self.assertEqual(result[0]["ownerAnchorRelation"], "unknown")
        result = analyze_containment(indices, matrix, [{"referenceId": "owner", "studentId": "owner"}])
        self.assertEqual(result[0]["ownerAnchorRelation"], "consistent")

    def test_anchored_reference_owner_with_missing_student_owner_is_unknown(self):
        indices = {
            "reference": index(
                {"child": "modelElement", "owner": "modelElement"}, [contains("child", "owner")]
            ),
            "student": index({"child": "modelElement", "owner": "modelElement"}, []),
        }
        matrix = candidates([("child", "Name", [("child", "Name")])])
        result = analyze_containment(indices, matrix, [{"referenceId": "owner", "studentId": "owner"}])
        self.assertEqual(result[0]["ownerAnchorRelation"], "unknown")
        self.assertIsNone(result[0]["studentOwnerId"])

    def test_ambiguous_and_cyclic_paths_are_retained_without_claims(self):
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
        matrix = candidates([("child", "Name", [("child", "Name")])])
        result = analyze_containment(indices, matrix, [
            {"referenceId": "a", "studentId": "owner"}, {"referenceId": "b", "studentId": "owner"},
        ])[0]
        self.assertEqual(result["referenceContainmentPaths"], [["child", "box", "a"], ["child", "box", "b"]])
        self.assertEqual(result["studentContainmentPaths"], [["child", "box", "owner", "box"]])
        self.assertIsNone(result["referenceOwnerId"])
        self.assertEqual(result["studentOwnerId"], "owner")
        self.assertEqual(result["ownerAnchorRelation"], "unknown")
        indices["reference"].parents["box"].reverse()
        self.assertEqual(result, analyze_containment(indices, matrix, [
            {"referenceId": "a", "studentId": "owner"}, {"referenceId": "b", "studentId": "owner"},
        ])[0])

    def test_non_unique_anchor_information_is_unknown(self):
        result = analyze_containment(self.indices, self.candidates, [
            {"referenceId": "r-person", "studentId": "s-person"},
            {"referenceId": "r-person", "studentId": "s-dept"},
        ])
        pair = next(item for item in result if item["referenceId"] == "r-person-name"
                    and item["studentId"] == "s-person-name")
        self.assertEqual(pair["ownerAnchorRelation"], "unknown")

    def test_order_does_not_change_results(self):
        expected = analyze_containment(self.indices, self.candidates, self.anchors)
        reversed_candidates = copy.deepcopy(self.candidates)
        reversed_candidates["synonymMatrix"].reverse()
        for row in reversed_candidates["synonymMatrix"]:
            row["matches"].reverse()
        result = analyze_containment(self.indices, reversed_candidates, list(reversed(self.anchors)))
        self.assertEqual(result, expected)
        self.assertEqual(
            [(item["referenceId"], item["studentId"]) for item in result],
            sorted((item["referenceId"], item["studentId"]) for item in result),
        )


if __name__ == "__main__":
    unittest.main()
