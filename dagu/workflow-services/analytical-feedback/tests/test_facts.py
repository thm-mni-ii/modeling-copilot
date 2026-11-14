"""Check exact matcher-fact projection and conservative consistency claims."""

from copy import deepcopy
import unittest

from test_analysis import build, case, contains, endpoints, node, rehash
from analysis_contract import validate_analysis
from facts import evaluate_facts
from initial_recognition import evaluate_connections


def with_facts(store):
    store.comparison["provisionalConnectionStructure"] = evaluate_connections(
        store.indices, store.comparison["mapping"]["provisionalElements"])
    store.comparison["propertyFacts"] = evaluate_facts(store.indices, store.comparison,
        {side: {"completeness": {"interpretation": "complete"}} for side in store.indices}, {"synonymMatrix": []})
    return store


class FactProjectionTests(unittest.TestCase):
    def test_complete_local_properties_are_explicit_under_provisional_identity(self):
        store = with_facts(case([node("parent", label="Parent"), node("child", label="Child")],
                                reference_edges=[contains("child", "parent")]))
        report = build(store)
        validate_analysis(report, store)
        self.assertEqual(report["contractVersion"], "1.2")
        for annotation in report["annotations"]:
            self.assertEqual(annotation["match"]["status"], "provisional")
            self.assertEqual(annotation["consistency"], "fully_consistent")
            self.assertEqual(annotation["checks"]["label"], "satisfied")
            self.assertEqual(annotation["facts"], [item for item in store.comparison["propertyFacts"]["items"]
                                                 if annotation["target"]["id"] in item["submissionIds"]])

    def test_equal_properties_remain_visible_with_wrong_owner_and_open_containment(self):
        nodes = [node("parent", label="Parent"), node("other"), node("child", label="Child")]
        store = with_facts(case(nodes, reference_edges=[contains("child", "parent")],
                                submission_edges=[contains("child", "other")]))
        report = build(store)
        child = next(item for item in report["annotations"] if item["target"]["id"] == "child")
        self.assertEqual(child["checks"]["label"], "satisfied")
        self.assertEqual(child["checks"]["owner"], "violated")
        self.assertEqual(child["status"], "different")
        self.assertEqual(child["consistency"], "different")
        validate_analysis(report, store)
        store = with_facts(case([node("parent"), node("box", "structuralElement"), node("child", label="Child")],
            reference_edges=[contains("box", "parent"), contains("child", "box")]))
        report = build(store)
        child = next(item for item in report["annotations"] if item["target"]["id"] == "child")
        self.assertEqual(child["checks"]["label"], "satisfied")
        self.assertEqual(child["checks"]["owner"], "satisfied")
        self.assertEqual(child["checks"]["containment"], "unresolved")
        self.assertEqual(child["consistency"], "partial")

    def test_missing_reference_connection_uses_reference_hints(self):
        store = with_facts(case([node("a"), node("b"), node("e", "connection", directed=True)],
                                [node("a"), node("b")], endpoints("e", "a", "b"), [], pairs=[("a", "a"), ("b", "b")]))
        report = build(store)
        hint = report["referenceHints"][0]
        self.assertEqual(hint["code"], "reference.missing")
        self.assertEqual(hint["target"]["id"], "a")
        self.assertTrue(any(item["code"] == "counterpart.missing" for item in hint["facts"]))
        self.assertNotIn("facts", hint["parameters"])
        validate_analysis(report, store)

    def test_rejects_invented_fact_and_unsupported_complete_claim(self):
        store = with_facts(case([node("a"), node("b")], pairs=[("a", "a")]))
        original = build(store)
        for mutate in (lambda report: report["annotations"][0]["facts"][0].update(status="violated"),
                       lambda report: report["annotations"][1].update(consistency="fully_consistent")):
            report = deepcopy(original)
            mutate(report)
            rehash(report)
            with self.assertRaises(ValueError):
                validate_analysis(report, store)


if __name__ == "__main__":
    unittest.main()
