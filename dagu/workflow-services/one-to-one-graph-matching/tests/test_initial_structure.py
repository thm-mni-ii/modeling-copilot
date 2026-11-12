import copy
import unittest

from initial_structure import evaluate_provisional_owners
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


if __name__ == "__main__":
    unittest.main()
