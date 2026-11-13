import copy
import unittest
from unittest.mock import patch

import correspondence_state
from graph_index import GraphIndex
from initial_evaluation import evaluate_initial_coverage
from initial_structure import evaluate_containment_relations
from test_graph_index import graph, node
from test_matching import make_inputs


def fixture():
    indices, candidates = make_inputs(
        {"r-person": "Person", "r-dept": "Department", "r-p-name": "Name",
         "r-d-name": "Name", "r-other": "Alpha", "r-free": "Free"},
        {"s-person": "Person", "s-dept": "Department", "s-p-name": "Name",
         "s-d-name": "Name", "s-other": "Beta", "s-free": "Free"},
        [(r, s) for r in ("r-person", "r-dept") for s in ("s-person", "s-dept")]
        + [(r, s) for r in ("r-p-name", "r-d-name") for s in ("s-p-name", "s-d-name")]
        + [("r-other", "s-other")],
        [
            {"kind": "contains", "role": "content", "source": "r-p-name", "target": "r-person"},
            {"kind": "contains", "role": "content", "source": "r-d-name", "target": "r-dept"},
        ],
        [
            {"kind": "contains", "role": "content", "source": "s-p-name", "target": "s-person"},
            {"kind": "contains", "role": "content", "source": "s-d-name", "target": "s-dept"},
        ],
    )
    for side in ("reference", "student"):
        old = indices[side]
        nodes = list(old.nodes.values())
        for item in nodes:
            identity = item["id"]
            if identity.endswith(("person", "dept")):
                item["type"] = "owner"
            elif identity.endswith("name"):
                item["type"] = "attribute"
            elif identity.endswith("other"):
                item["type"] = "other"
            else:
                item["type"] = side + "-only"
        nodes.append(node(side + "-container", "structuralElement"))
        edges = [edge for outgoing in old.outgoing.values() for edge in outgoing]
        indices[side] = GraphIndex(graph(nodes, edges))
    for row in candidates["synonymMatrix"]:
        for match in row["matches"]:
            match.update({"comparisonBasis": "type", "scoreStatus": "scored", "scores": {"method": 0.4}})
    return indices, candidates


class CorrespondenceStateTests(unittest.TestCase):
    def test_builds_proposals_with_original_owner_dependencies(self):
        indices, candidates = fixture()
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual(state["proposals"], [
            {"referenceId": "r-d-name", "studentId": "s-d-name", "reason": "consistent_owner_anchor",
             "dependsOn": [{"referenceId": "r-dept", "studentId": "s-dept"}]},
            {"referenceId": "r-dept", "studentId": "s-dept", "reason": "unique_exact_label", "dependsOn": []},
            {"referenceId": "r-p-name", "studentId": "s-p-name", "reason": "consistent_owner_anchor",
             "dependsOn": [{"referenceId": "r-person", "studentId": "s-person"}]},
            {"referenceId": "r-person", "studentId": "s-person", "reason": "unique_exact_label", "dependsOn": []},
        ])
        self.assertEqual(state["conflictingProposals"], [])
        self.assertEqual(state["blockedProposals"], [])
        self.assertEqual(len({item["referenceId"] for item in state["proposals"]}), len(state["proposals"]))
        self.assertEqual(len({item["studentId"] for item in state["proposals"]}), len(state["proposals"]))

    def test_components_keep_all_pairs_and_no_candidate_instances(self):
        indices, candidates = fixture()
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual(state["candidateComponents"], [
            {"referenceIds": ["r-d-name", "r-p-name"], "studentIds": ["s-d-name", "s-p-name"], "pairCount": 4},
            {"referenceIds": ["r-dept", "r-person"], "studentIds": ["s-dept", "s-person"], "pairCount": 4},
            {"referenceIds": ["r-other"], "studentIds": ["s-other"], "pairCount": 1},
        ])
        self.assertEqual(state["noCandidateReferenceIds"], ["r-free"])
        self.assertEqual(state["noCandidateStudentIds"], ["s-free"])
        pairs = {(item["referenceId"], item["studentId"]) for item in state["candidatePairs"]}
        self.assertEqual(len(pairs), 9)
        self.assertIn(("r-p-name", "s-d-name"), pairs)
        candidate = next(item for item in state["candidatePairs"]
                         if item["referenceId"] == "r-p-name" and item["studentId"] == "s-d-name")
        self.assertEqual(candidate["referenceLabel"], "Name")
        self.assertEqual(candidate["submissionLabel"], "Name")
        self.assertEqual(candidate["scores"], {"method": 0.4})
        candidate["scores"]["method"] = 0.9
        self.assertEqual(candidates["synonymMatrix"][2]["matches"][1]["scores"]["method"], 0.4)

    def test_inputs_and_order_remain_unchanged(self):
        indices, candidates = fixture()
        original_candidates = copy.deepcopy(candidates)
        original_indices = {side: copy.deepcopy(vars(index)) for side, index in indices.items()}
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual(candidates, original_candidates)
        self.assertEqual({side: vars(index) for side, index in indices.items()}, original_indices)
        reordered = copy.deepcopy(candidates)
        reordered["synonymMatrix"].reverse()
        for row in reordered["synonymMatrix"]:
            row["matches"].reverse()
        self.assertEqual(
            correspondence_state.build_provisional_state(dict(reversed(list(indices.items()))), reordered), state
        )

    def test_equal_ids_from_different_graphs_remain_distinct_vertices(self):
        indices, candidates = make_inputs(
            {"a": "One", "b": "Two"}, {"a": "Two", "b": "One"},
            [("a", "b"), ("b", "a")],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual(state["candidateComponents"], [
            {"referenceIds": ["a"], "studentIds": ["b"], "pairCount": 1},
            {"referenceIds": ["b"], "studentIds": ["a"], "pairCount": 1},
        ])

    def test_conflicting_proposals_are_reported_without_selecting_either(self):
        indices, candidates = fixture()
        anchors = [
            {"referenceId": "r-person", "studentId": "s-person", "reason": "unique_exact_label"},
            {"referenceId": "r-p-name", "studentId": "s-d-name", "reason": "unique_exact_label"},
        ]
        containment = [{"referenceId": "r-p-name", "studentId": "s-p-name",
                        "reason": "consistent_owner_anchor"}]
        with patch.object(correspondence_state, "propose_exact_anchors", return_value=(anchors, [])), \
                patch.object(correspondence_state, "propose_containment_anchors", return_value=containment):
            state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual(state["proposals"], [
            {"referenceId": "r-person", "studentId": "s-person", "reason": "unique_exact_label", "dependsOn": []},
        ])
        self.assertEqual([(item["referenceId"], item["studentId"]) for item in state["conflictingProposals"]],
                         [("r-p-name", "s-d-name"), ("r-p-name", "s-p-name")])
        self.assertEqual(len(state["candidatePairs"]), 9)

    def test_proposal_depending_on_conflicting_owner_is_blocked(self):
        indices, candidates = fixture()
        anchors = [
            {"referenceId": "r-person", "studentId": "s-person", "reason": "unique_exact_label"},
            {"referenceId": "r-person", "studentId": "s-dept", "reason": "unique_exact_label"},
        ]
        containment = [{"referenceId": "r-p-name", "studentId": "s-p-name",
                        "reason": "consistent_owner_anchor"}]
        evidence = [{"referenceId": "r-p-name", "studentId": "s-p-name",
                     "referenceOwnerId": "r-person", "studentOwnerId": "s-person",
                     "ownerAnchorRelation": "consistent"}]
        with patch.object(correspondence_state, "propose_exact_anchors", return_value=(anchors, [])), \
                patch.object(correspondence_state, "analyze_containment", return_value=evidence), \
                patch.object(correspondence_state, "propose_containment_anchors", return_value=containment):
            state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual(state["proposals"], [])
        self.assertEqual(len(state["conflictingProposals"]), 2)
        self.assertEqual(state["blockedProposals"], [{
            "referenceId": "r-p-name", "studentId": "s-p-name", "reason": "consistent_owner_anchor",
            "dependsOn": [{"referenceId": "r-person", "studentId": "s-person"}],
        }])

    def test_independent_child_supports_renamed_owner_across_containers(self):
        indices, candidates = make_inputs(
            {"r-owner": "Old", "r-child": "Unique"},
            {"s-owner": "New", "s-child": "Unique"},
            [("r-owner", "s-owner"), ("r-child", "s-child")],
        )
        for side, prefix in (("reference", "r"), ("student", "s")):
            nodes = list(indices[side].nodes.values()) + [node(prefix + "-box", "structuralElement")]
            edges = [{"kind": "contains", "role": "content", "source": prefix + "-child", "target": prefix + "-box"},
                     {"kind": "contains", "role": "component", "source": prefix + "-box", "target": prefix + "-owner"}]
            indices[side] = GraphIndex(graph(nodes, edges))
        state = correspondence_state.build_provisional_state(indices, candidates)
        owner = next(item for item in state["proposals"] if item["referenceId"] == "r-owner")
        self.assertEqual(owner, {
            "referenceId": "r-owner", "studentId": "s-owner", "reason": "independent_child_evidence",
            "dependsOn": [{"referenceId": "r-child", "studentId": "s-child"}],
        })
        evidence = next(item for item in state["childOwnerEvidence"]
                        if item["referenceId"] == "r-owner" and item["studentId"] == "s-owner")
        self.assertEqual(evidence["proposalStatus"], "proposed")
        self.assertEqual(len(evidence["supportingChildren"]), 1)
        self.assertEqual(evidence["conflictingChildren"], [])

    def test_conflicting_child_pairs_do_not_select_an_owner(self):
        indices, candidates = make_inputs(
            {"r-owner": "Old", "r-one": "One", "r-two": "Two"},
            {"s-owner": "New", "s-other": "Other", "s-one": "One", "s-two": "Two"},
            [("r-owner", "s-owner"), ("r-owner", "s-other"), ("r-one", "s-one"), ("r-two", "s-two")],
            [{"kind": "contains", "role": "content", "source": child, "target": "r-owner"}
             for child in ("r-one", "r-two")],
            [{"kind": "contains", "role": "content", "source": "s-one", "target": "s-owner"},
             {"kind": "contains", "role": "content", "source": "s-two", "target": "s-other"}],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertFalse(any(item["referenceId"] == "r-owner" for item in state["proposals"]))
        for item in state["childOwnerEvidence"]:
            if item["referenceId"] == "r-owner":
                self.assertEqual(len(item["conflictingChildren"]), 1)

    def test_identical_unmapped_children_do_not_prove_owners(self):
        indices, candidates = make_inputs(
            {"r-owner": "Old", "r1": "Name", "r2": "Name"},
            {"s-owner": "New", "s1": "Name", "s2": "Name"},
            [("r-owner", "s-owner")] + [(ref, sub) for ref in ("r1", "r2") for sub in ("s1", "s2")],
            [{"kind": "contains", "role": "content", "source": ref, "target": "r-owner"} for ref in ("r1", "r2")],
            [{"kind": "contains", "role": "content", "source": sub, "target": "s-owner"} for sub in ("s1", "s2")],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual(state["proposals"], [])
        evidence = next(item for item in state["childOwnerEvidence"] if item["referenceId"] == "r-owner")
        self.assertEqual(evidence["supportingChildren"], [])
        self.assertTrue(evidence["unresolvedChildren"])

    def test_reserved_exact_child_enables_owner_without_confirming_structure(self):
        indices, candidates = make_inputs(
            {"r-known": "Known", "r-new": "Old", "r-a": "Name", "r-b": "Name"},
            {"s-known": "Known", "s-new": "New", "s-a": "Name", "s-b": "Name"},
            [("r-known", "s-known"), ("r-new", "s-new")]
            + [(ref, sub) for ref in ("r-a", "r-b") for sub in ("s-a", "s-b")],
            [{"kind": "contains", "role": "content", "source": "r-a", "target": "r-known"},
             {"kind": "contains", "role": "content", "source": "r-b", "target": "r-new"}],
            [{"kind": "contains", "role": "content", "source": "s-a", "target": "s-known"},
             {"kind": "contains", "role": "content", "source": "s-b", "target": "s-new"}],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        pairs = {item["referenceId"]: item for item in state["proposals"]}
        self.assertEqual(pairs["r-b"]["reason"], "unique_exact_after_reservations")
        self.assertEqual(pairs["r-b"]["dependsOn"], [{"referenceId": "r-a", "studentId": "s-a"}])
        self.assertEqual(pairs["r-new"]["dependsOn"], [{"referenceId": "r-b", "studentId": "s-b"}])
        mapping = evaluate_initial_coverage(indices, state)["mapping"]["provisionalElements"]
        rows = evaluate_containment_relations(indices, mapping)["relations"]
        self.assertEqual(next(item for item in rows if item["referenceSourceId"] == "r-b")["status"], "unresolved")

    def test_child_cannot_create_owner_without_candidate_or_global_capacity(self):
        edges = lambda prefix: [
            {"kind": "contains", "role": "content", "source": prefix + "-child", "target": prefix + "-owner"}]
        for owner_pairs in ([], [("r-owner", "s-owner"), ("r-owner", "s-other"), ("r-other", "s-owner")]):
            with self.subTest(owner_pairs=owner_pairs):
                indices, candidates = make_inputs(
                    {"r-owner": "Old", "r-other": "Reference", "r-child": "Unique"},
                    {"s-owner": "New", "s-other": "Submission", "s-child": "Unique"},
                    owner_pairs + [("r-child", "s-child")], edges("r"), edges("s"),
                )
                state = correspondence_state.build_provisional_state(indices, candidates)
                self.assertFalse(any(item["referenceId"] == "r-owner" for item in state["proposals"]))
                if owner_pairs:
                    evidence = next(item for item in state["childOwnerEvidence"]
                                    if item["referenceId"] == "r-owner" and item["studentId"] == "s-owner")
                    self.assertEqual(evidence["proposalStatus"], "capacity_not_preserved")
                self.assertEqual(evaluate_initial_coverage(indices, state)["proposalFeasibility"]["joint"]["status"],
                                 "preserved")

    def test_owner_dependent_child_is_not_independent_evidence(self):
        from structural_evidence import analyze_child_owner_evidence

        indices, candidates = fixture()
        state = correspondence_state.build_provisional_state(indices, candidates)
        evidence = analyze_child_owner_evidence(indices, candidates, state["proposals"])
        owner = next(item for item in evidence
                     if item["referenceId"] == "r-person" and item["studentId"] == "s-person")
        self.assertEqual(owner["supportingChildren"], [])
        self.assertTrue(any(item["decisionBasis"] == "dependent_or_ambiguous"
                            for item in owner["unresolvedChildren"]))
        proposals = copy.deepcopy(state["proposals"])
        child = next(item for item in proposals if item["referenceId"] == "r-p-name")
        child["reason"] = "unique_exact_after_reservations"
        child["dependsOn"] = [{"referenceId": "r-dept", "studentId": "s-dept"}]
        department = next(item for item in proposals if item["referenceId"] == "r-dept")
        department["dependsOn"] = [{"referenceId": "r-person", "studentId": "s-person"}]
        evidence = analyze_child_owner_evidence(indices, candidates, proposals)
        owner = next(item for item in evidence
                     if item["referenceId"] == "r-person" and item["studentId"] == "s-person")
        self.assertEqual(owner["supportingChildren"], [])
        self.assertEqual(owner["unresolvedChildren"][0]["referenceId"], "r-p-name")

    def test_ambiguous_containment_and_competing_owners_stay_open(self):
        indices, candidates = make_inputs(
            {"r-owner": "Old", "r-other": "Reference", "r-child": "Unique"},
            {"s-owner": "New", "s-child": "Unique"},
            [("r-owner", "s-owner"), ("r-other", "s-owner"), ("r-child", "s-child")],
            [{"kind": "contains", "role": "content", "source": "r-child", "target": "r-owner"},
             {"kind": "contains", "role": "content", "source": "r-child", "target": "r-other"}],
            [{"kind": "contains", "role": "content", "source": "s-child", "target": "s-owner"}],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertEqual([item["referenceId"] for item in state["proposals"]], ["r-child"])
        for item in state["childOwnerEvidence"]:
            self.assertEqual(item["supportingChildren"], [])
            self.assertEqual(item["proposalStatus"], "no_independent_support")
            self.assertEqual(item["unresolvedChildren"][0]["decisionBasis"], "dependent_or_ambiguous")

    def test_multiple_reference_owners_competing_for_one_student_owner_stay_open(self):
        indices, candidates = make_inputs(
            {"r-first": "First", "r-second": "Second", "r-one": "One", "r-two": "Two"},
            {"s-owner": "New", "s-one": "One", "s-two": "Two"},
            [("r-first", "s-owner"), ("r-second", "s-owner"), ("r-one", "s-one"), ("r-two", "s-two")],
            [{"kind": "contains", "role": "content", "source": "r-one", "target": "r-first"},
             {"kind": "contains", "role": "content", "source": "r-two", "target": "r-second"}],
            [{"kind": "contains", "role": "content", "source": child, "target": "s-owner"}
             for child in ("s-one", "s-two")],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertFalse(any(item["reason"] == "independent_child_evidence" for item in state["proposals"]))
        self.assertTrue(all(item["proposalStatus"] == "conflicting" for item in state["childOwnerEvidence"]))

    def test_missing_child_is_reported_without_claiming_a_contradiction(self):
        indices, candidates = make_inputs(
            {"r-owner": "Old", "r-found": "Found", "r-missing": "Missing"},
            {"s-owner": "New", "s-found": "Found"},
            [("r-owner", "s-owner"), ("r-found", "s-found")],
            [{"kind": "contains", "role": "content", "source": child, "target": "r-owner"}
             for child in ("r-found", "r-missing")],
            [{"kind": "contains", "role": "content", "source": "s-found", "target": "s-owner"}],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        evidence = next(item for item in state["childOwnerEvidence"] if item["referenceId"] == "r-owner")
        self.assertEqual(evidence["proposalStatus"], "proposed")
        self.assertEqual(evidence["conflictingChildren"], [])
        self.assertEqual(evidence["unresolvedChildren"][0]["referenceId"], "r-missing")
        self.assertEqual(evidence["unresolvedChildren"][0]["decisionBasis"], "child_mapping_missing")

    def test_owner_proposals_must_preserve_capacity_jointly(self):
        indices, candidates = make_inputs(
            {"r1": "Old1", "r2": "Old2", "r3": "Old3", "rc1": "One", "rc2": "Two"},
            {"s1": "New1", "s2": "New2", "s3": "New3", "sc1": "One", "sc2": "Two"},
            [("r1", "s1"), ("r1", "s3"), ("r2", "s2"), ("r2", "s3"),
             ("r3", "s1"), ("r3", "s2"), ("rc1", "sc1"), ("rc2", "sc2")],
            [{"kind": "contains", "role": "content", "source": "rc1", "target": "r1"},
             {"kind": "contains", "role": "content", "source": "rc2", "target": "r2"}],
            [{"kind": "contains", "role": "content", "source": "sc1", "target": "s1"},
             {"kind": "contains", "role": "content", "source": "sc2", "target": "s2"}],
        )
        state = correspondence_state.build_provisional_state(indices, candidates)
        self.assertFalse(any(item["reason"] == "independent_child_evidence" for item in state["proposals"]))
        for pair in (("r1", "s1"), ("r2", "s2")):
            evidence = next(item for item in state["childOwnerEvidence"]
                            if (item["referenceId"], item["studentId"]) == pair)
            self.assertEqual(evidence["proposalStatus"], "capacity_not_preserved")


if __name__ == "__main__":
    unittest.main()
