import copy
import unittest

from graph_index import GraphIndex
from matching import propose_containment_anchors, propose_exact_anchors
from structural_evidence import analyze_containment
from test_graph_index import graph, node


def make_inputs(reference_labels, student_labels, pairs, reference_edges=(), student_edges=()):
    indices = {
        "reference": GraphIndex(graph([node(identity) for identity in reference_labels], list(reference_edges))),
        "student": GraphIndex(graph([node(identity) for identity in student_labels], list(student_edges))),
    }
    candidates = {"synonymMatrix": [
        {
            "referenceElementId": reference_id,
            "referenceLabel": label,
            "matches": [
                {"submissionElementId": student_id, "submissionLabel": student_labels[student_id]}
                for left_id, student_id in pairs if left_id == reference_id
            ],
        }
        for reference_id, label in reference_labels.items()
    ]}
    return indices, candidates


class ExactAnchorTests(unittest.TestCase):
    def test_exact_label_normalizes_unicode_and_whitespace(self):
        indices, candidates = make_inputs(
            {"r": "  Cafe\u0301\n  Projekt\t"}, {"s": "Café Projekt"}, [("r", "s")],
        )
        self.assertEqual(propose_exact_anchors(indices, candidates), (
            [{"referenceId": "r", "studentId": "s", "reason": "unique_exact_label"}], [],
        ))

    def test_duplicate_labels_on_either_or_both_sides_remain_unresolved(self):
        for references, students, pairs in (
            ({"r1": "Name", "r2": "Name"}, {"s1": "Name"}, [("r1", "s1"), ("r2", "s1")]),
            ({"r1": "Name"}, {"s1": "Name", "s2": "Name"}, [("r1", "s1"), ("r1", "s2")]),
            ({"r1": "Name", "r2": "Name"}, {"s1": "Name", "s2": "Name"},
             [("r1", "s1"), ("r1", "s2"), ("r2", "s1"), ("r2", "s2")]),
        ):
            with self.subTest(pairs=pairs):
                anchors, unresolved = propose_exact_anchors(*make_inputs(references, students, pairs))
                self.assertEqual(anchors, [])
                self.assertEqual(unresolved, [
                    {"referenceId": reference_id, "studentId": student_id}
                    for reference_id, student_id in sorted(pairs)
                ])

    def test_duplicate_label_in_disjoint_candidate_groups_is_still_ambiguous(self):
        indices, candidates = make_inputs(
            {"r1": "Name", "r2": "Name"}, {"s1": "Name", "s2": "Name"},
            [("r1", "s1"), ("r2", "s2")],
        )
        self.assertEqual(propose_exact_anchors(indices, candidates), ([], [
            {"referenceId": "r1", "studentId": "s1"},
            {"referenceId": "r2", "studentId": "s2"},
        ]))

    def test_different_and_empty_labels_do_not_create_exact_pairs(self):
        indices, candidates = make_inputs(
            {"r1": "Name", "r2": " \n ", "r3": "Name"},
            {"s1": "name", "s2": "\t", "s3": "Other"},
            [("r1", "s1"), ("r2", "s2"), ("r3", "s3")],
        )
        self.assertEqual(propose_exact_anchors(indices, candidates), ([], []))

    def test_no_anchor_for_pairs_not_in_candidate_matrix(self):
        indices, candidates = make_inputs(
            {"r-type": "Name", "r-group": "Address"},
            {"s-type": "Name", "s-group": "Address"}, [],
        )
        indices["reference"].nodes["r-type"]["type"] = "type-a"
        indices["student"].nodes["s-type"]["type"] = "type-b"
        indices["reference"].nodes["r-group"]["comparisonGroup"] = "group-a"
        indices["student"].nodes["s-group"]["comparisonGroup"] = "group-b"
        self.assertEqual(propose_exact_anchors(indices, candidates), ([], []))

    def test_duplicate_label_outside_exact_candidate_pairs_does_not_block_anchor(self):
        indices, candidates = make_inputs(
            {"r1": "Name", "r2": "Name"}, {"s": "Name"}, [("r1", "s")],
        )
        self.assertEqual(propose_exact_anchors(indices, candidates), (
            [{"referenceId": "r1", "studentId": "s", "reason": "unique_exact_label"}], [],
        ))

    def test_different_parent_positions_do_not_block_anchor(self):
        indices, candidates = make_inputs(
            {"r": "Name", "r-parent": "Reference owner"},
            {"s": "Name", "s-parent": "Student owner"}, [("r", "s")],
            [{"kind": "contains", "role": "content", "source": "r", "target": "r-parent"}],
            [{"kind": "contains", "role": "content", "source": "s", "target": "s-parent"}],
        )
        self.assertEqual(propose_exact_anchors(indices, candidates), (
            [{"referenceId": "r", "studentId": "s", "reason": "unique_exact_label"}], [],
        ))

    def test_results_are_sorted_and_independent_of_input_order(self):
        pairs = [("r3", "s3"), ("r2", "s1"), ("r1", "s2"), ("r1", "s1"), ("r0", "s0")]
        indices, candidates = make_inputs(
            {"r3": "Other", "r2": "Name", "r1": "Name", "r0": "First"},
            {"s3": "Other", "s2": "Name", "s1": "Name", "s0": "First"}, pairs,
        )
        original = copy.deepcopy(candidates)
        first = propose_exact_anchors(indices, candidates)
        reversed_candidates = copy.deepcopy(candidates)
        reversed_candidates["synonymMatrix"].reverse()
        for row in reversed_candidates["synonymMatrix"]:
            row["matches"].reverse()
        self.assertEqual(first, propose_exact_anchors(indices, reversed_candidates))
        anchors, unresolved = first
        self.assertEqual(anchors, [
            {"referenceId": "r0", "studentId": "s0", "reason": "unique_exact_label"},
            {"referenceId": "r3", "studentId": "s3", "reason": "unique_exact_label"},
        ])
        self.assertEqual(unresolved, [
            {"referenceId": "r1", "studentId": "s1"},
            {"referenceId": "r1", "studentId": "s2"},
            {"referenceId": "r2", "studentId": "s1"},
        ])
        self.assertEqual(len({pair["referenceId"] for pair in anchors}), len(anchors))
        self.assertEqual(len({pair["studentId"] for pair in anchors}), len(anchors))
        self.assertEqual(candidates, original)


class ContainmentAnchorTests(unittest.TestCase):
    def test_equal_names_are_distinguished_using_anchored_owners(self):
        indices, candidates = make_inputs(
            {"r-person": "Person", "r-dept": "Department", "r-p-name": "Name", "r-d-name": "Name"},
            {"s-person": "Person", "s-dept": "Department", "s-p-name": "Name", "s-d-name": "Name"},
            [(r, s) for r in ("r-person", "r-dept") for s in ("s-person", "s-dept")]
            + [(r, s) for r in ("r-p-name", "r-d-name") for s in ("s-p-name", "s-d-name")],
            [
                {"kind": "contains", "role": "content", "source": "r-p-name", "target": "r-person"},
                {"kind": "contains", "role": "content", "source": "r-d-name", "target": "r-dept"},
            ],
            [
                {"kind": "contains", "role": "content", "source": "s-p-name", "target": "s-person"},
                {"kind": "contains", "role": "content", "source": "s-d-name", "target": "s-dept"},
            ],
        )
        anchors, unresolved = propose_exact_anchors(indices, candidates)
        evidence = analyze_containment(indices, candidates, anchors)
        self.assertEqual(propose_containment_anchors(unresolved, anchors, evidence), [
            {"referenceId": "r-d-name", "studentId": "s-d-name", "reason": "consistent_owner_anchor"},
            {"referenceId": "r-p-name", "studentId": "s-p-name", "reason": "consistent_owner_anchor"},
        ])
        self.assertEqual(len(unresolved), 4)

    def test_single_name_is_not_assigned_to_wrong_owner(self):
        indices, candidates = make_inputs(
            {"r-person": "Person", "r-dept": "Department", "r-p-name": "Name", "r-d-name": "Name"},
            {"s-person": "Person", "s-dept": "Department", "s-d-name": "Name"},
            [(r, s) for r in ("r-person", "r-dept") for s in ("s-person", "s-dept")]
            + [("r-p-name", "s-d-name"), ("r-d-name", "s-d-name")],
            [
                {"kind": "contains", "role": "content", "source": "r-p-name", "target": "r-person"},
                {"kind": "contains", "role": "content", "source": "r-d-name", "target": "r-dept"},
            ],
            [{"kind": "contains", "role": "content", "source": "s-d-name", "target": "s-dept"}],
        )
        anchors, unresolved = propose_exact_anchors(indices, candidates)
        evidence = analyze_containment(indices, candidates, anchors)
        self.assertEqual(propose_containment_anchors(unresolved, anchors, evidence), [
            {"referenceId": "r-d-name", "studentId": "s-d-name", "reason": "consistent_owner_anchor"},
        ])
        self.assertEqual(len(unresolved), 2)

    def test_identical_names_under_same_owner_remain_ambiguous(self):
        indices, candidates = make_inputs(
            {"r-owner": "Person", "r1": "Name", "r2": "Name"},
            {"s-owner": "Person", "s1": "Name", "s2": "Name"},
            [("r-owner", "s-owner")] + [(r, s) for r in ("r1", "r2") for s in ("s1", "s2")],
            [{"kind": "contains", "role": "content", "source": r, "target": "r-owner"} for r in ("r1", "r2")],
            [{"kind": "contains", "role": "content", "source": s, "target": "s-owner"} for s in ("s1", "s2")],
        )
        anchors, unresolved = propose_exact_anchors(indices, candidates)
        evidence = analyze_containment(indices, candidates, anchors)
        self.assertEqual(propose_containment_anchors(unresolved, anchors, evidence), [])

    def test_unknown_conflicting_missing_and_non_exact_evidence_do_not_propose(self):
        unresolved = [
            {"referenceId": "r1", "studentId": "s1"},
            {"referenceId": "r2", "studentId": "s2"},
            {"referenceId": "r3", "studentId": "s3"},
        ]
        evidence = [
            {"referenceId": "r1", "studentId": "s1", "ownerAnchorRelation": "unknown"},
            {"referenceId": "r2", "studentId": "s2", "ownerAnchorRelation": "conflicting"},
            {"referenceId": "r4", "studentId": "s4", "ownerAnchorRelation": "consistent"},
        ]
        self.assertEqual(propose_containment_anchors(unresolved, [], evidence), [])
        self.assertEqual(len(unresolved), 3)

    def test_existing_anchors_are_excluded_before_checking_one_to_one(self):
        unresolved = [
            {"referenceId": "r-used", "studentId": "s-free"},
            {"referenceId": "r-free", "studentId": "s-used"},
            {"referenceId": "r-free", "studentId": "s-free"},
            {"referenceId": "r-other", "studentId": "s-other"},
        ]
        anchors = [
            {"referenceId": "r-used", "studentId": "s-existing"},
            {"referenceId": "r-existing", "studentId": "s-used"},
        ]
        evidence = [{**pair, "ownerAnchorRelation": "consistent"} for pair in unresolved]
        before = copy.deepcopy((unresolved, anchors, evidence))
        expected = [
            {"referenceId": "r-free", "studentId": "s-free", "reason": "consistent_owner_anchor"},
            {"referenceId": "r-other", "studentId": "s-other", "reason": "consistent_owner_anchor"},
        ]
        self.assertEqual(propose_containment_anchors(unresolved, anchors, evidence), expected)
        self.assertEqual(propose_containment_anchors(
            list(reversed(unresolved)), list(reversed(anchors)), list(reversed(evidence))
        ), expected)
        self.assertEqual((unresolved, anchors, evidence), before)

    def test_competing_consistent_pairs_are_not_greedily_resolved(self):
        unresolved = [
            {"referenceId": "r1", "studentId": "s1"},
            {"referenceId": "r1", "studentId": "s2"},
            {"referenceId": "r2", "studentId": "s2"},
        ]
        evidence = [{**pair, "ownerAnchorRelation": "consistent"} for pair in unresolved]
        self.assertEqual(propose_containment_anchors(unresolved, [], evidence), [])


if __name__ == "__main__":
    unittest.main()
