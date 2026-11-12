import copy
import unittest

from assignment_capacity import analyze_assignment_capacity, analyze_proposal_feasibility
from correspondence_state import build_provisional_state
from test_matching import make_inputs


def state(components=(), isolated_references=(), isolated_students=()):
    return {
        "candidatePairs": [
            {"referenceId": reference, "studentId": student}
            for _references, _students, pairs in components for reference, student in pairs
        ],
        "candidateComponents": [
            {"referenceIds": list(references), "studentIds": list(students), "pairCount": len(pairs)}
            for references, students, pairs in components
        ],
        "noCandidateReferenceIds": list(isolated_references),
        "noCandidateStudentIds": list(isolated_students),
    }


class AssignmentCapacityTests(unittest.TestCase):
    def test_one_candidate_has_capacity_one(self):
        result = analyze_assignment_capacity(state([(["r"], ["s"], [("r", "s")])]))
        self.assertEqual(result, {
            "referenceCount": 1, "studentCount": 1, "maximumMatches": 1,
            "minimumUnmatchedReference": 0, "minimumUnmatchedStudent": 0,
            "components": [{"referenceIds": ["r"], "studentIds": ["s"], "maximumMatches": 1}],
        })

    def test_two_references_compete_for_one_student(self):
        result = analyze_assignment_capacity(state([
            (["r1", "r2"], ["s1"], [("r1", "s1"), ("r2", "s1")]),
        ]))
        self.assertEqual(result["maximumMatches"], 1)
        self.assertEqual(result["minimumUnmatchedReference"], 1)
        self.assertEqual(result["minimumUnmatchedStudent"], 0)

    def test_complete_two_by_two_graph_has_capacity_two(self):
        result = analyze_assignment_capacity(state([
            (["r1", "r2"], ["s1", "s2"], [(r, s) for r in ("r1", "r2") for s in ("s1", "s2")]),
        ]))
        self.assertEqual(result["maximumMatches"], 2)
        self.assertEqual(result["minimumUnmatchedReference"], 0)
        self.assertEqual(result["minimumUnmatchedStudent"], 0)

    def test_augmenting_path_ignores_provisional_anchors(self):
        data = state([
            (["r1", "r2"], ["s1", "s2"], [("r1", "s1"), ("r1", "s2"), ("r2", "s1")]),
        ])
        baseline = analyze_assignment_capacity(data)
        data["proposals"] = [{"referenceId": "r1", "studentId": "s1"}]
        data["candidatePairs"][0]["scores"] = {"method": 1}
        self.assertEqual(analyze_assignment_capacity(data), baseline)
        self.assertEqual(baseline["maximumMatches"], 2)

    def test_hall_deficit_with_equal_side_counts(self):
        data = state([
            (["r1", "r2", "r3"], ["s1", "s2", "s3"],
             [("r1", "s1"), ("r2", "s1"), ("r3", "s1"), ("r3", "s2"), ("r3", "s3")]),
        ])
        result = analyze_assignment_capacity(data)
        self.assertEqual(result["maximumMatches"], 2)
        self.assertEqual(result["minimumUnmatchedReference"], 1)
        self.assertEqual(result["minimumUnmatchedStudent"], 1)

    def test_components_and_isolated_instances_are_counted(self):
        data = state([
            (["r2", "r1"], ["s1"], [("r1", "s1"), ("r2", "s1")]),
            (["r3"], ["s3", "s2"], [("r3", "s2"), ("r3", "s3")]),
        ], isolated_references=["r4"], isolated_students=["s4", "s5"])
        result = analyze_assignment_capacity(data)
        self.assertEqual(result, {
            "referenceCount": 4, "studentCount": 5, "maximumMatches": 2,
            "minimumUnmatchedReference": 2, "minimumUnmatchedStudent": 3,
            "components": [
                {"referenceIds": ["r1", "r2"], "studentIds": ["s1"], "maximumMatches": 1},
                {"referenceIds": ["r3"], "studentIds": ["s2", "s3"], "maximumMatches": 1},
            ],
        })

    def test_identical_ids_in_different_models_are_separate(self):
        indices, candidates = make_inputs(
            {"a": "One", "b": "Two"}, {"a": "Two", "b": "One"}, [("a", "b"), ("b", "a")],
        )
        result = analyze_assignment_capacity(build_provisional_state(indices, candidates))
        self.assertEqual(result["maximumMatches"], 2)
        self.assertEqual(result["components"], [
            {"referenceIds": ["a"], "studentIds": ["b"], "maximumMatches": 1},
            {"referenceIds": ["b"], "studentIds": ["a"], "maximumMatches": 1},
        ])

    def test_input_order_is_irrelevant_and_input_is_not_modified(self):
        data = state([
            (["r2", "r1"], ["s1", "s2"], [("r2", "s1"), ("r1", "s1"), ("r1", "s2")]),
            (["r3"], ["s3"], [("r3", "s3")]),
        ], isolated_references=["r5", "r4"], isolated_students=["s5", "s4"])
        original = copy.deepcopy(data)
        expected = analyze_assignment_capacity(data)
        self.assertEqual(data, original)
        reordered = copy.deepcopy(data)
        reordered["candidatePairs"].reverse()
        reordered["candidateComponents"].reverse()
        reordered["noCandidateReferenceIds"].reverse()
        reordered["noCandidateStudentIds"].reverse()
        for component in reordered["candidateComponents"]:
            component["referenceIds"].reverse()
            component["studentIds"].reverse()
        self.assertEqual(analyze_assignment_capacity(reordered), expected)

    def test_empty_graph_and_isolated_instances(self):
        result = analyze_assignment_capacity(state(isolated_references=["r1", "r2"], isolated_students=["s1"]))
        self.assertEqual(result, {
            "referenceCount": 2, "studentCount": 1, "maximumMatches": 0,
            "minimumUnmatchedReference": 2, "minimumUnmatchedStudent": 1, "components": [],
        })
        self.assertEqual(analyze_assignment_capacity(state())["maximumMatches"], 0)

    def test_inconsistent_component_is_rejected(self):
        data = state([(["r"], ["s"], [("r", "s")])])
        data["candidateComponents"][0]["pairCount"] = 0
        with self.assertRaisesRegex(ValueError, "does not match"):
            analyze_assignment_capacity(data)


class ProposalFeasibilityTests(unittest.TestCase):
    def make_state(self, pairs, proposals=(), conflicting=(), blocked=()):
        return {
            "candidatePairs": [{"referenceId": r, "studentId": s} for r, s in pairs],
            "proposals": [{"referenceId": r, "studentId": s} for r, s in proposals],
            "conflictingProposals": [{"referenceId": r, "studentId": s} for r, s in conflicting],
            "blockedProposals": [{"referenceId": r, "studentId": s} for r, s in blocked],
        }

    def test_one_proposal_preserves_capacity(self):
        data = self.make_state([("r1", "s1"), ("r1", "s2"), ("r2", "s1")], [("r1", "s2")])
        result = analyze_proposal_feasibility(data)
        self.assertEqual(result["baselineMaximumMatches"], 2)
        self.assertEqual(result["individual"], [{
            "referenceId": "r1", "studentId": "s2", "maximumMatchesIfForced": 2, "status": "preserved",
        }])
        self.assertEqual(result["joint"], {
            "pairs": [{"referenceId": "r1", "studentId": "s2"}],
            "maximumMatchesIfForced": 2, "status": "preserved",
        })

    def test_one_proposal_reduces_capacity(self):
        data = self.make_state([("r1", "s1"), ("r1", "s2"), ("r2", "s1")], [("r1", "s1")])
        result = analyze_proposal_feasibility(data)
        self.assertEqual(result["baselineMaximumMatches"], 2)
        self.assertEqual(result["individual"][0]["maximumMatchesIfForced"], 1)
        self.assertEqual(result["individual"][0]["status"], "reduced")
        self.assertEqual(result["joint"]["maximumMatchesIfForced"], 1)
        self.assertEqual(result["joint"]["status"], "reduced")

    def test_individually_compatible_proposals_can_be_jointly_incompatible(self):
        data = self.make_state([
            ("r1", "s1"), ("r1", "s2"), ("r2", "s2"),
            ("r2", "s3"), ("r3", "s3"), ("r3", "s1"),
        ], [("r1", "s1"), ("r2", "s3")])
        result = analyze_proposal_feasibility(data)
        self.assertEqual(result["baselineMaximumMatches"], 3)
        self.assertTrue(all(item["status"] == "preserved" and item["maximumMatchesIfForced"] == 3
                            for item in result["individual"]))
        self.assertEqual(result["joint"], {
            "pairs": [{"referenceId": "r1", "studentId": "s1"}, {"referenceId": "r2", "studentId": "s3"}],
            "maximumMatchesIfForced": 2, "status": "reduced",
        })

    def test_conflicting_and_blocked_proposals_are_reported_without_forcing(self):
        data = self.make_state(
            [("r1", "s1"), ("r1", "s2"), ("r2", "s1")],
            [("r1", "s1")], conflicting=[("r1", "s1")], blocked=[("r2", "s1")],
        )
        result = analyze_proposal_feasibility(data)
        self.assertEqual(result["individual"], [])
        self.assertEqual(result["joint"], {"pairs": [], "maximumMatchesIfForced": 2, "status": "preserved"})
        self.assertEqual(result["conflictingProposals"], [{"referenceId": "r1", "studentId": "s1"}])
        self.assertEqual(result["blockedProposals"], [{"referenceId": "r2", "studentId": "s1"}])

    def test_empty_graph_and_no_proposals(self):
        result = analyze_proposal_feasibility(self.make_state([]))
        self.assertEqual(result, {
            "baselineMaximumMatches": 0, "individual": [],
            "joint": {"pairs": [], "maximumMatchesIfForced": 0, "status": "preserved"},
            "conflictingProposals": [], "blockedProposals": [],
        })

    def test_input_order_is_irrelevant_and_inputs_are_unchanged(self):
        data = self.make_state(
            [("r1", "s1"), ("r1", "s2"), ("r2", "s2"), ("r2", "s3"), ("r3", "s3"), ("r3", "s1")],
            [("r2", "s3"), ("r1", "s1")], conflicting=[("r1", "s2")], blocked=[("r2", "s2")],
        )
        original = copy.deepcopy(data)
        expected = analyze_proposal_feasibility(data)
        self.assertEqual(data, original)
        for items in data.values():
            items.reverse()
        self.assertEqual(analyze_proposal_feasibility(data), expected)

    def test_invalid_active_proposals_are_rejected(self):
        data = self.make_state([("r1", "s1")], [("r1", "s2")])
        with self.assertRaisesRegex(ValueError, "not a candidate"):
            analyze_proposal_feasibility(data)
        data = self.make_state([("r1", "s1"), ("r1", "s2")], [("r1", "s1"), ("r1", "s2")])
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            analyze_proposal_feasibility(data)


if __name__ == "__main__":
    unittest.main()
