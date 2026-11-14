"""Identity support is independent from placement, with explicit dependencies."""

import unittest

from correspondence_state import build_provisional_state
from identity_evidence import evaluate_identity
from facts import evaluate_facts
from test_matching import make_inputs
from test_structural_evidence import contains


def composition_fixture(symmetric=False):
    shapes = [("a", "b"), ("a", "b")] if symmetric else [("a", "b"), ("a", "c"), ("b", "c")]
    labels = {side: {} for side in ("r", "s")}
    edges = {side: [] for side in labels}
    for side in labels:
        for i, shape in enumerate(shapes):
            labels[side][f"{side}p{i}"] = f"{side}-parent-{i}"
            for value in shape:
                child = f"{side}{i}{value}"
                labels[side][child] = value
                edges[side].append(contains(child, f"{side}p{i}"))
    pairs = [(r, s) for r in labels["r"] for s in labels["s"] if ("p" in r) == ("p" in s)]
    return make_inputs(labels["r"], labels["s"], pairs, edges["r"], edges["s"])


class IdentityEvidenceTests(unittest.TestCase):
    def test_incomplete_graph_cannot_prove_closed_combination(self):
        indices, candidates = composition_fixture()
        state = build_provisional_state(indices, candidates, graphs={side: {"completeness": {"interpretation": "partial"}} for side in indices})
        self.assertEqual(state["proposals"], [])
        self.assertFalse(any(item["complete"] for item in state["combinedChildEvidence"]))
    def test_composition_uses_declared_types_language_and_relation_roles(self):
        indices, candidates = composition_fixture()
        for index in indices.values():
            for item in index.nodes.values():
                item["type"] = "custom-node"
                item["language"] = {"languageId": "custom-language", "versionId": "release-19"}
            for edges in index.parents.values():
                for edge in edges:
                    edge["role"] = "custom-slot"
        state = build_provisional_state(indices, candidates)
        self.assertEqual(len(state["proposals"]), 9)
        self.assertEqual(sum(row["reason"] == "combined_child_structure" for row in state["proposals"]), 3)
    def test_jointly_distinct_children_identify_renamed_parents_without_child_anchors(self):
        indices, candidates = composition_fixture()
        state = build_provisional_state(indices, candidates)
        parents = [row for row in state["proposals"] if row["referenceId"].startswith("rp")]
        self.assertEqual(len(parents), 3)
        self.assertTrue(all(row["reason"] == "combined_child_structure" and not row["dependsOn"] for row in parents))
        result = evaluate_identity(indices, candidates, state["proposals"], combined=state["combinedChildEvidence"])
        for i in range(3):
            row = next(row for row in result["pairs"] if (row["referenceId"], row["studentId"]) == (f"rp{i}", f"sp{i}"))
            self.assertEqual(row["status"], "uniquely_supported")
            self.assertEqual(next(item for item in row["criteria"] if item["method"] == "combined_children")["role"], "identity_anchor")
        self.assertEqual(len(state["proposals"]), 9)
        self.assertTrue(all(row["status"] == "uniquely_supported" for row in result["pairs"]
                            if (row["referenceId"], row["studentId"]) in {(item["referenceId"], item["studentId"]) for item in state["proposals"]}))
        facts = evaluate_facts(indices, {"mapping": {"provisionalElements": state["proposals"], "provisionalConnections": []}, "identityEvidence": result},
                               {side: {"completeness": {"interpretation": "complete"}} for side in indices}, candidates)["items"]
        child_placement = next(item for item in facts if item["referenceIds"] == ["r0a"] and item["code"].startswith("owner."))
        self.assertEqual(child_placement["evidence"]["basis"], "conditional_mapping")

    def test_symmetric_parents_do_not_force_identities(self):
        indices, candidates = composition_fixture(symmetric=True)
        state = build_provisional_state(indices, candidates)
        self.assertEqual(state["proposals"], [])
        result = evaluate_identity(indices, candidates, [], combined=state["combinedChildEvidence"])
        self.assertTrue(all(row["status"] == "unresolved" for row in result["pairs"]))

    def test_partial_children_are_support_without_automatic_identity(self):
        from structural_evidence import analyze_combined_children
        indices, candidates = composition_fixture(symmetric=True)
        # Add one expected child without an admissible counterpart.
        indices["reference"].nodes["r-extra"] = {**indices["reference"].nodes["r0a"], "id": "r-extra"}
        edge = contains("r-extra", "rp0")
        indices["reference"].parents["r-extra"].append(edge)
        indices["reference"].children["rp0"].append(edge)
        combined = analyze_combined_children(indices, candidates, [])
        result = evaluate_identity(indices, candidates, [], combined=combined)
        row = next(row for row in result["pairs"] if (row["referenceId"], row["studentId"]) == ("rp0", "sp0"))
        criterion = next(item for item in row["criteria"] if item["method"] == "combined_children")
        self.assertEqual((criterion["matched"], criterion["expected"]), (2, 3))
        self.assertEqual(row["status"], "supported")
    def test_exact_identity_survives_wrong_owner(self):
        indices, candidates = make_inputs({"rp": "Parent", "rq": "Other", "rc": "Child"},
            {"sp": "Parent", "sq": "Other", "sc": "Child"}, [("rp", "sp"), ("rq", "sq"), ("rc", "sc")],
            [contains("rc", "rp")], [contains("sc", "sq")])
        state = build_provisional_state(indices, candidates)
        result = evaluate_identity(indices, candidates, state["proposals"])
        child = next(row for row in result["pairs"] if row["referenceId"] == "rc")
        self.assertEqual(child["status"], "uniquely_supported")
        owner = next(item for item in child["criteria"] if item["method"] == "identified_owner")
        self.assertEqual(owner["result"], "violated")
        self.assertEqual(child["criteria"][0]["role"], "identity_anchor")
        evaluation = {"mapping": {"provisionalElements": state["proposals"], "provisionalConnections": []}, "identityEvidence": result}
        facts = evaluate_facts(indices, evaluation, {side: {"completeness": {"interpretation": "complete"}} for side in indices}, candidates)["items"]
        placement = next(item for item in facts if item["code"].startswith("owner.") and item["referenceIds"] == ["rc"])
        self.assertEqual(placement["evidence"]["placementStatus"], "wrong_placement")
        self.assertEqual(placement["evidence"]["basis"], "independent_evidence")

    def test_child_identity_with_unidentified_parent_keeps_placement_open(self):
        indices, candidates = make_inputs({"rp": "Old", "rc": "Child"}, {"sp": "New", "sc": "Child"},
            [("rp", "sp"), ("rc", "sc")], [contains("rc", "rp")], [contains("sc", "sp")])
        # This step intentionally evaluates the child without inferring its parent.
        proposals = [{"referenceId": "rc", "studentId": "sc", "reason": "unique_exact_label", "dependsOn": []}]
        identity = evaluate_identity(indices, candidates, proposals)
        evaluation = {"mapping": {"provisionalElements": proposals, "provisionalConnections": []}, "identityEvidence": identity}
        facts = evaluate_facts(indices, evaluation, {side: {"completeness": {"interpretation": "complete"}} for side in indices}, candidates)["items"]
        placement = next(item for item in facts if item["code"].startswith("owner.") and item["referenceIds"] == ["rc"])
        self.assertEqual(placement["evidence"]["placementStatus"], "placement_unresolved")
        self.assertEqual(next(row for row in identity["pairs"] if row["referenceId"] == "rc")["status"], "uniquely_supported")

    def test_type_alone_never_identifies(self):
        indices, candidates = make_inputs({"r": "Old"}, {"s": "New"}, [("r", "s")])
        row = evaluate_identity(indices, candidates, [])["pairs"][0]
        self.assertEqual(row["status"], "unresolved")
        self.assertEqual(next(item for item in row["criteria"] if item["method"] == "type_compatibility")["role"], "compatibility")

    def test_circular_owner_child_proposals_are_not_identity_anchors(self):
        indices, candidates = make_inputs({"rp": "Old", "rc": "Same"}, {"sp": "New", "sc": "Same"},
            [("rp", "sp"), ("rc", "sc")], [contains("rc", "rp")], [contains("sc", "sp")])
        proposals = [{"referenceId": "rp", "studentId": "sp", "reason": "independent_child_evidence",
                      "dependsOn": [{"referenceId": "rc", "studentId": "sc"}]},
                     {"referenceId": "rc", "studentId": "sc", "reason": "consistent_owner_anchor",
                      "dependsOn": [{"referenceId": "rp", "studentId": "sp"}]}]
        result = evaluate_identity(indices, candidates, proposals)
        self.assertFalse(any(row["status"] == "uniquely_supported" for row in result["pairs"]))


if __name__ == "__main__":
    unittest.main()
