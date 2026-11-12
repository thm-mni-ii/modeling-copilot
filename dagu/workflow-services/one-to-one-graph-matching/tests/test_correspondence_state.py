import copy
import unittest
from unittest.mock import patch

import correspondence_state
from graph_index import GraphIndex
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


if __name__ == "__main__":
    unittest.main()
