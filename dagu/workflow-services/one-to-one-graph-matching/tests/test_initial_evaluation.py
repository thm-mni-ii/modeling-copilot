import copy
import unittest

from correspondence_state import build_provisional_state
from initial_evaluation import evaluate_initial_coverage, evaluate_type_comparison
from test_correspondence_state import fixture
from test_matching import make_inputs


def evaluate(reference, student, pairs):
    indices, candidates = make_inputs(reference, student, pairs)
    state = build_provisional_state(indices, candidates)
    return indices, state, evaluate_initial_coverage(indices, state)


class InitialCoverageTests(unittest.TestCase):
    def test_two_anchors_cover_two_of_three_references(self):
        indices, state, result = evaluate(
            {"r1": "Person", "r2": "Product", "r3": "Other"},
            {"s1": "Person", "s2": "Product"},
            [(r, s) for r in ("r1", "r2", "r3") for s in ("s1", "s2")],
        )
        self.assertEqual(result["metrics"]["overall"], {
            "referenceCount": 3, "studentCount": 2, "provisionalAnchorCount": 2,
            "maximumAssignableCount": 2, "anchorCoverage": 2 / 3, "capacityUpperBound": 2 / 3,
        })
        self.assertEqual(result["unresolvedReferenceIds"], ["r3"])
        self.assertEqual(result["unresolvedStudentIds"], [])
        self.assertTrue(all(item["status"] == "provisional" for item in result["mapping"]["provisionalElements"]))
        self.assertEqual(result["proposalFeasibility"]["joint"]["status"], "preserved")
        self.assertEqual(evaluate_initial_coverage(indices, state), result)

    def test_repeated_name_does_not_create_arbitrary_anchor(self):
        _indices, _state, result = evaluate(
            {"r1": "Name", "r2": "Name"}, {"s1": "Name"},
            [("r1", "s1"), ("r2", "s1")],
        )
        self.assertEqual(result["mapping"]["provisionalElements"], [])
        self.assertEqual(result["unresolvedReferenceIds"], ["r1", "r2"])
        self.assertEqual(result["unresolvedStudentIds"], ["s1"])
        self.assertEqual(result["metrics"]["overall"]["maximumAssignableCount"], 1)
        self.assertEqual(result["metrics"]["overall"]["anchorCoverage"], 0)
        self.assertEqual(result["metrics"]["overall"]["capacityUpperBound"], 0.5)

    def test_empty_reference_has_null_ratios(self):
        _indices, _state, result = evaluate({}, {"s1": "Name"}, [])
        self.assertEqual(result["metrics"]["overall"], {
            "referenceCount": 0, "studentCount": 1, "provisionalAnchorCount": 0,
            "maximumAssignableCount": 0, "anchorCoverage": None, "capacityUpperBound": None,
        })
        self.assertEqual(result["metrics"]["byReferenceType"], [])
        self.assertEqual(result["metrics"]["byComparisonClass"], [])

    def test_type_views_allow_other_concrete_student_types_in_same_group(self):
        indices, candidates = make_inputs(
            {"r1": "Person", "r2": "Relation", "r3": "Name"},
            {"s1": "Person", "s2": "Relation", "s3": "Name"},
            [(r, s) for r in ("r1", "r2") for s in ("s1", "s2")] + [("r3", "s3")],
        )
        for side, identity, node_type, group in (
            ("reference", "r1", "serm-entity", "serm-entity"),
            ("reference", "r2", "serm-er", "serm-entity"),
            ("reference", "r3", "serm-attribute", None),
            ("student", "s1", "serm-relationship", "serm-entity"),
            ("student", "s2", "serm-entity", "serm-entity"),
            ("student", "s3", "serm-attribute", None),
        ):
            indices[side].nodes[identity]["type"] = node_type
            indices[side].nodes[identity]["comparisonGroup"] = group
            indices[side].nodes[identity]["language"] = {"languageId": "serm", "versionId": "1"}
        state = build_provisional_state(indices, candidates)
        result = evaluate_initial_coverage(indices, state)
        types = {item["category"]["type"]: item for item in result["metrics"]["byReferenceType"]}
        self.assertEqual(types["serm-er"]["studentCount"], 0)
        self.assertEqual(types["serm-er"]["provisionalAnchorCount"], 1)
        self.assertEqual(types["serm-er"]["maximumAssignableCount"], 1)
        self.assertEqual(types["serm-er"]["capacityUpperBound"], 1)
        self.assertEqual(types["serm-attribute"]["maximumAssignableCount"], 1)
        classes = {(item["category"]["basis"], item["category"]["value"]): item
                   for item in result["metrics"]["byComparisonClass"]}
        self.assertEqual(classes["group", "serm-entity"]["referenceCount"], 2)
        self.assertEqual(classes["group", "serm-entity"]["studentCount"], 2)
        self.assertEqual(classes["group", "serm-entity"]["maximumAssignableCount"], 2)
        self.assertEqual(classes["type", "serm-attribute"]["referenceCount"], 1)
        self.assertEqual(classes["group", "serm-entity"]["category"]["language"],
                         {"languageId": "serm", "versionId": "1"})

    def test_language_versions_form_separate_categories(self):
        indices, candidates = make_inputs(
            {"r1": "One", "r2": "Two"}, {"s1": "One", "s2": "Two"}, [("r1", "s1"), ("r2", "s2")],
        )
        for side, identity in (("reference", "r2"), ("student", "s2")):
            indices[side].nodes[identity]["language"]["versionId"] = "v2"
        result = evaluate_initial_coverage(indices, build_provisional_state(indices, candidates))
        views = result["metrics"]["byReferenceType"]
        self.assertEqual([item["category"]["language"]["versionId"] for item in views], ["1", "v2"])
        self.assertEqual([item["referenceCount"] for item in views], [1, 1])

    def test_type_view_capacities_are_alternative_and_not_additive(self):
        indices, candidates = make_inputs(
            {"r1": "One", "r2": "Two"}, {"s1": "Other"}, [("r1", "s1"), ("r2", "s1")],
        )
        for side, identity, node_type in (
            ("reference", "r1", "serm-entity"), ("reference", "r2", "serm-er"),
            ("student", "s1", "serm-relationship"),
        ):
            indices[side].nodes[identity]["type"] = node_type
            indices[side].nodes[identity]["comparisonGroup"] = "serm-entity"
        result = evaluate_initial_coverage(indices, build_provisional_state(indices, candidates))
        self.assertEqual(result["metrics"]["overall"]["maximumAssignableCount"], 1)
        self.assertEqual([item["maximumAssignableCount"] for item in result["metrics"]["byReferenceType"]], [1, 1])
        self.assertEqual(result["metrics"]["byComparisonClass"][0]["maximumAssignableCount"], 1)

    def test_capacity_loss_does_not_remove_provisional_proposal(self):
        indices, state, _result = evaluate(
            {"r1": "One", "r2": "Two"}, {"s1": "Other", "s2": "Other"},
            [("r1", "s1"), ("r1", "s2"), ("r2", "s1")],
        )
        state["proposals"] = [{"referenceId": "r1", "studentId": "s1",
                               "reason": "unique_exact_label", "dependsOn": []}]
        result = evaluate_initial_coverage(indices, state)
        self.assertEqual(result["proposalFeasibility"]["joint"]["status"], "reduced")
        self.assertEqual(result["metrics"]["overall"]["maximumAssignableCount"], 2)
        self.assertEqual(result["metrics"]["overall"]["provisionalAnchorCount"], 1)
        self.assertEqual(result["mapping"]["provisionalElements"][0]["studentId"], "s1")

    def test_excluded_proposals_remain_unresolved(self):
        indices, state, _result = evaluate({"r1": "One"}, {"s1": "One"}, [("r1", "s1")])
        state["blockedProposals"] = copy.deepcopy(state["proposals"])
        result = evaluate_initial_coverage(indices, state)
        self.assertEqual(result["metrics"]["overall"]["provisionalAnchorCount"], 0)
        self.assertEqual(result["unresolvedReferenceIds"], ["r1"])
        self.assertEqual(result["unresolvedStudentIds"], ["s1"])
        self.assertEqual(result["proposalFeasibility"]["individual"], [])

    def test_conflicting_proposals_remain_unresolved(self):
        indices, state, _result = evaluate({"r1": "One"}, {"s1": "One"}, [("r1", "s1")])
        state["conflictingProposals"] = copy.deepcopy(state["proposals"])
        result = evaluate_initial_coverage(indices, state)
        self.assertEqual(result["metrics"]["overall"]["provisionalAnchorCount"], 0)
        self.assertEqual(result["unresolvedReferenceIds"], ["r1"])
        self.assertEqual(result["conflictingProposals"], state["conflictingProposals"])

    def test_owner_anchor_dependencies_remain_in_provisional_mapping(self):
        indices, candidates = fixture()
        result = evaluate_initial_coverage(indices, build_provisional_state(indices, candidates))
        child = next(item for item in result["mapping"]["provisionalElements"] if item["referenceId"] == "r-p-name")
        self.assertEqual(child["dependsOn"], [{"referenceId": "r-person", "studentId": "s-person"}])
        self.assertEqual(child["status"], "provisional")

    def test_invalid_proposals_and_dependencies_are_rejected(self):
        indices, state, _result = evaluate(
            {"r1": "One", "r2": "Two"}, {"s1": "One", "s2": "Two"},
            [(r, s) for r in ("r1", "r2") for s in ("s1", "s2")],
        )
        conflicting = copy.deepcopy(state)
        conflicting["proposals"][1]["studentId"] = "s1"
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            evaluate_initial_coverage(indices, conflicting)
        missing = copy.deepcopy(state)
        missing["proposals"][0]["dependsOn"] = [{"referenceId": "missing", "studentId": "missing"}]
        with self.assertRaisesRegex(ValueError, "used active proposal"):
            evaluate_initial_coverage(indices, missing)
        cyclic = copy.deepcopy(state)
        cyclic["proposals"][0]["dependsOn"] = [
            {"referenceId": cyclic["proposals"][1]["referenceId"],
             "studentId": cyclic["proposals"][1]["studentId"]}]
        cyclic["proposals"][1]["dependsOn"] = [
            {"referenceId": cyclic["proposals"][0]["referenceId"],
             "studentId": cyclic["proposals"][0]["studentId"]}]
        with self.assertRaisesRegex(ValueError, "cycles"):
            evaluate_initial_coverage(indices, cyclic)
        noncandidate = copy.deepcopy(state)
        noncandidate["proposals"][0]["studentId"] = "unknown"
        with self.assertRaisesRegex(ValueError, "not a candidate"):
            evaluate_initial_coverage(indices, noncandidate)

    def test_type_results_keep_unresolved_and_dependent_pairs_separate(self):
        indices, _candidates = make_inputs(
            {"r1": "A", "r2": "B", "r3": "C", "r4": "D"},
            {"s1": "A", "s2": "B", "s4": "D"}, [],
        )
        for side, identity, node_type in (
            ("reference", "r1", "first"), ("student", "s1", "first"),
            ("reference", "r2", "first"), ("student", "s2", "second"),
            ("reference", "r4", None), ("student", "s4", "second"),
        ):
            indices[side].nodes[identity].update({"type": node_type, "comparisonGroup": "group"})
        mapping = [
            {"referenceId": "r1", "studentId": "s1", "reason": "unique_exact_label",
             "status": "provisional", "dependsOn": []},
            {"referenceId": "r2", "studentId": "s2", "reason": "consistent_owner_anchor",
             "status": "provisional", "dependsOn": [{"referenceId": "r1", "studentId": "s1"}]},
            {"referenceId": "r4", "studentId": "s4", "reason": "unique_exact_label",
             "status": "provisional", "dependsOn": []},
        ]
        result = evaluate_type_comparison(indices, mapping, [])
        data = result["elements"]
        self.assertEqual(result["evaluationStatus"], "provisional")
        self.assertEqual((data["referenceCount"], data["mappedCount"], data["evaluatedCount"]), (4, 3, 2))
        self.assertEqual((data["sameTypeCount"], data["compatibleTypeDifferenceCount"], data["unresolvedCount"]),
                         (1, 1, 2))
        self.assertEqual((data["sameTypePercentage"], data["compatibleTypeDifferencePercentage"]), (50, 50))
        self.assertEqual(data["unresolvedReferenceIds"], ["r3", "r4"])
        rows = {item["referenceId"]: item for item in data["pairs"]}
        self.assertEqual(rows["r2"]["status"], "compatible_type_difference")
        self.assertEqual(rows["r2"]["dependsOn"], mapping[1]["dependsOn"])
        self.assertEqual(rows["r3"]["mappingStatus"], "unresolved")
        self.assertEqual(rows["r4"]["mappingStatus"], "provisional")
        self.assertIsNone(result["connections"]["sameTypePercentage"])

    def test_type_results_reject_incompatible_provisional_pairs(self):
        for ref_group, sub_group in ((None, None), ("first-group", "second-group")):
            with self.subTest(referenceGroup=ref_group, studentGroup=sub_group):
                indices, _candidates = make_inputs({"r": "A"}, {"s": "A"}, [])
                indices["reference"].nodes["r"].update({"type": "first", "comparisonGroup": ref_group})
                indices["student"].nodes["s"].update({"type": "second", "comparisonGroup": sub_group})
                mapping = [{"referenceId": "r", "studentId": "s", "reason": "unique_exact_label",
                            "status": "provisional", "dependsOn": []}]
                with self.assertRaisesRegex(ValueError, "incompatible provisional type mapping"):
                    evaluate_type_comparison(indices, mapping, [])


if __name__ == "__main__":
    unittest.main()
