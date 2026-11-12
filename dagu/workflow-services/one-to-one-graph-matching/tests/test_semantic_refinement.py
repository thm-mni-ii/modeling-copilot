import copy
import unittest

from correspondence_state import build_provisional_state
from semantic_refinement import refine_semantic_proposals
from test_matching import make_inputs


def contains(child, parent):
    return {"kind": "contains", "role": "content", "source": child, "target": parent}


def fixture(references, students, entries, reference_edges=(), student_edges=()):
    indices, candidates = make_inputs(
        references, students, [(reference, student) for reference, student, _ in entries],
        reference_edges, student_edges,
    )
    candidates["methods"] = [{"name": name, "scoreRange": [0, 1]} for name in ("alpha", "beta")]
    scores = {(reference, student): value for reference, student, value in entries}
    for row in candidates["synonymMatrix"]:
        for match in row["matches"]:
            value = scores[row["referenceElementId"], match["submissionElementId"]]
            match.update({"scoreStatus": "scored" if value is not None else "unavailable", "scores": value})
    return indices, candidates, build_provisional_state(indices, candidates)


class SemanticRefinementTests(unittest.TestCase):
    def test_thresholds_and_unconfigured_methods(self):
        indices, candidates, state = fixture({"r": "A"}, {"s": "B"}, [("r", "s", {"alpha": 0.8})])
        result = refine_semantic_proposals(indices, candidates, state, {})
        self.assertEqual(result["configurationStatus"], "not_configured")
        self.assertEqual(result["candidateEvidence"][0]["status"], "unavailable")
        self.assertEqual(result["proposals"], [])
        result = refine_semantic_proposals(indices, candidates, state, {"alpha": 0.8})
        self.assertEqual(result["candidateEvidence"][0]["status"], "supported")
        self.assertEqual([(p["referenceId"], p["studentId"]) for p in result["proposals"]], [("r", "s")])
        result = refine_semantic_proposals(indices, candidates, state, {"alpha": 0.9})
        self.assertEqual(result["candidateEvidence"][0]["status"], "below_threshold")
        self.assertEqual(result["noSupportedReferenceIds"], ["r"])
        for invalid in ({"alpha": -0.1}, {"alpha": True}, {"unknown": 0.5}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                refine_semantic_proposals(indices, candidates, state, invalid)

    def test_contained_unknown_owner_and_one_sided_containment_remain_unresolved(self):
        for reference_edges, student_edges in (
            ([contains("r", "rp")], [contains("s", "sp")]),
            ([contains("r", "rp")], []),
            ([], [contains("s", "sp")]),
        ):
            indices, candidates, state = fixture(
                {"r": "A", "rp": "Owner A"}, {"s": "B", "sp": "Owner B"},
                [("r", "s", {"alpha": 1})], reference_edges, student_edges,
            )
            result = refine_semantic_proposals(indices, candidates, state, {"alpha": 0.8})
            self.assertEqual(result["proposals"], [])
            self.assertIn("r", result["unresolvedReferenceIds"])

    def test_consistent_owner_disambiguates_but_conflicting_owner_does_not(self):
        indices, candidates, state = fixture(
            {"rp": "Person", "rd": "Department", "r": "A"},
            {"sp": "Person", "sd": "Department", "s1": "B", "s2": "C"},
            [("rp", "sp", {"alpha": 1}), ("rd", "sd", {"alpha": 1}),
             ("r", "s1", {"alpha": 0.9}), ("r", "s2", {"alpha": 0.9})],
            [contains("r", "rp")], [contains("s1", "sp"), contains("s2", "sd")],
        )
        result = refine_semantic_proposals(indices, candidates, state, {"alpha": 0.8})
        self.assertEqual([(p["referenceId"], p["studentId"]) for p in result["proposals"]], [("r", "s1")])
        self.assertEqual(result["proposals"][0]["dependsOn"], [{"referenceId": "rp", "studentId": "sp"}])
        evidence = {item["studentId"]: item["ownerAnchorRelation"] for item in result["candidateEvidence"]
                    if item["referenceId"] == "r"}
        self.assertEqual(evidence, {"s1": "consistent", "s2": "conflicting"})

    def test_either_side_ties_remain_unresolved(self):
        indices, candidates, state = fixture(
            {"r1": "A", "r2": "B"}, {"s": "C"},
            [("r1", "s", {"alpha": 0.9}), ("r2", "s", {"alpha": 0.9})],
        )
        result = refine_semantic_proposals(indices, candidates, state, {"alpha": 0.8})
        self.assertEqual(result["proposals"], [])
        self.assertEqual(result["unresolvedReferenceIds"], ["r1", "r2"])

    def test_disagreeing_methods_and_missing_scores_do_not_choose_winner(self):
        for scores in (
            ({"alpha": 0.9, "beta": 0.8}, {"alpha": 0.8, "beta": 0.9}),
            ({"alpha": 0.9, "beta": 0.9}, None),
        ):
            indices, candidates, state = fixture(
                {"r": "A"}, {"s1": "B", "s2": "C"}, [("r", "s1", scores[0]), ("r", "s2", scores[1])],
            )
            result = refine_semantic_proposals(indices, candidates, state, {"alpha": 0.7, "beta": 0.7})
            self.assertEqual(result["proposals"], [])
            self.assertEqual(result["unresolvedReferenceIds"], ["r"])

    def test_joint_capacity_and_input_order(self):
        references = {"r1": "A", "r2": "B", "r3": "C"}
        students = {"s1": "X", "s2": "Y", "s3": "Z"}
        entries = [("r1", "s1", {"alpha": 0.9}), ("r1", "s2", {"alpha": 0.1}),
                   ("r2", "s2", {"alpha": 0.1}), ("r2", "s3", {"alpha": 0.9}),
                   ("r3", "s3", {"alpha": 0.1}), ("r3", "s1", {"alpha": 0.1})]
        indices, candidates, state = fixture(references, students, entries)
        original = copy.deepcopy(candidates), copy.deepcopy(state)
        result = refine_semantic_proposals(indices, candidates, state, {"alpha": 0.8})
        self.assertEqual(result["proposals"], [])
        self.assertEqual((candidates, state), original)
        reverse = fixture(dict(reversed(list(references.items()))), dict(reversed(list(students.items()))),
                          list(reversed(entries)))
        self.assertEqual(result, refine_semantic_proposals(*reverse, {"alpha": 0.8}))

    def test_renamed_ids_and_additional_method(self):
        for reference, student in (("r", "s"), ("other-r", "other-s")):
            indices, candidates, state = fixture(
                {reference: "A"}, {student: "B"}, [(reference, student, {"beta": 0.9})],
            )
            result = refine_semantic_proposals(indices, candidates, state, {"beta": 0.8})
            self.assertEqual([(p["referenceId"], p["studentId"]) for p in result["proposals"]],
                             [(reference, student)])


if __name__ == "__main__":
    unittest.main()
