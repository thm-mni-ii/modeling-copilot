"""Exercise matcher-produced identity, property and placement evidence together."""

from copy import deepcopy
import unittest

from test_analysis import build, case, contains, node, rehash
from analysis_contract import validate_analysis
from artifacts import _key
from correspondence_state import build_provisional_state
from facts import evaluate_facts
from identity_evidence import evaluate_identity
from initial_recognition import evaluate_connections, propose_connections
from initial_structure import evaluate_containment_relations


def with_identity_facts(store):
    indices = store.indices
    candidates = {"synonymMatrix": [{"referenceElementId": ref, "referenceLabel": left.get("label", ""), "matches": [
        {"submissionElementId": sub, "submissionLabel": right.get("label", "")}
        for sub, right in indices["student"].nodes.items() if right["kind"] == "modelElement" and _key(left) == _key(right)]}
        for ref, left in indices["reference"].nodes.items() if left["kind"] == "modelElement"]}
    state = build_provisional_state(indices, candidates)
    connections = propose_connections(indices, state["proposals"], candidates)
    comparison = store.comparison
    comparison["mapping"] = {"provisionalElements": state["proposals"], "provisionalConnections": connections["proposals"]}
    comparison["identityEvidence"] = evaluate_identity(indices, candidates, state["proposals"], combined=state["combinedChildEvidence"],
        connection_pairs=connections["proposals"], connection_candidates=connections["candidateEvidence"])
    comparison["provisionalContainmentEvidence"] = evaluate_containment_relations(indices, state["proposals"])["relations"]
    comparison["provisionalConnectionStructure"] = evaluate_connections(indices, state["proposals"])
    comparison["propertyFacts"] = evaluate_facts(indices, comparison,
        {side: {"completeness": {"interpretation": "complete"}} for side in indices}, candidates)
    return store


class IdentityFeedbackTests(unittest.TestCase):
    def test_parent_identity_is_preserved_for_complete_missing_extra_and_moved_children(self):
        nodes = [node("parent", label="Parent"), node("other", label="Other"), node("a", native_type="property", label="A"), node("b", native_type="property", label="B")]
        reference_edges = [contains("a", "parent"), contains("b", "parent")]
        for scenario, submission, edges, matched in (
            ("complete", nodes, reference_edges, 2),
            ("missing", nodes[:-1], [contains("a", "parent")], 1),
            ("extra", nodes + [node("unknown", native_type="foreign", label="Unassigned")], reference_edges + [contains("unknown", "parent")], 2),
            ("moved", nodes, [contains("a", "parent"), contains("b", "other")], 1),
        ):
            with self.subTest(scenario=scenario):
                store = with_identity_facts(case(nodes, submission, reference_edges, edges))
                report = build(store)
                validate_analysis(report, store)
                parent = next(item for item in report["annotations"] if item["target"]["id"] == "parent")
                self.assertEqual(parent["identity"]["status"], "uniquely_supported")
                self.assertTrue(any(fact["code"] == "label.equal" and fact["status"] == "satisfied" for fact in parent["facts"]))
                self.assertTrue(any(fact["code"] == "type.equal" and fact["status"] == "satisfied" for fact in parent["facts"]))
                children = next(item for item in parent["facts"] if item["code"] == "children.complete")["evidence"]
                self.assertEqual((children["matched"], children["expected"]), (matched, 2))
                if scenario == "missing":
                    self.assertEqual(children["provenAbsentReferenceIds"], ["b"])
                if scenario == "extra":
                    self.assertEqual(children["unmatchedSubmissionIds"], ["unknown"])

    def test_recognized_parent_and_moved_child_keep_positive_evidence(self):
        nodes = [node("parent", label="Parent"), node("other", label="Other"),
                 node("a", native_type="property", label="A"), node("b", native_type="property", label="B"), node("c", native_type="property", label="C")]
        store = with_identity_facts(case(nodes, reference_edges=[contains(child, "parent") for child in ("a", "b", "c")],
            submission_edges=[contains("a", "parent"), contains("b", "parent"), contains("c", "other")]))
        report = build(store)
        validate_analysis(report, store)
        parent = next(item for item in report["annotations"] if item["target"]["id"] == "parent")
        self.assertEqual(parent["identity"]["status"], "uniquely_supported")
        self.assertTrue(any(fact["code"] == "label.equal" and fact["status"] == "satisfied" for fact in parent["facts"]))
        children = next(item for item in parent["facts"] if item["code"] == "children.complete")["evidence"]
        self.assertEqual((children["matched"], children["expected"], children["movedReferenceIds"]), (2, 3, ["c"]))
        child = next(item for item in report["annotations"] if item["target"]["id"] == "c")
        self.assertEqual(child["identity"]["status"], "uniquely_supported")
        self.assertTrue(any(fact["code"].startswith("owner.") and fact["status"] == "violated" for fact in child["facts"]))
        placement_hints = [hint for hint in child["hints"] if "findingId" in hint]
        self.assertEqual(len(placement_hints), 1)
        self.assertEqual({target["id"] for target in placement_hints[0]["targets"] if target["side"] == "submission"}, {"c", "parent", "other"})

    def test_facts_and_identity_cannot_be_changed_by_projection(self):
        store = with_identity_facts(case([node("parent", label="Parent")]))
        report = build(store)
        validate_analysis(report, store)
        self.assertEqual(report["recognition"]["overall"]["recognized"], 1)
        self.assertFalse({"status", "checks", "consistency", "match"} & report["annotations"][0].keys())
        forged = deepcopy(report)
        forged["annotations"][0]["identity"]["status"] = "supported"
        rehash(forged)
        with self.assertRaises(ValueError):
            validate_analysis(forged, store)


if __name__ == "__main__":
    unittest.main()
