"""Projection keeps independent positive, negative and open matcher facts."""
from copy import deepcopy
import unittest
from test_analysis import build, case, contains, endpoints, node, rehash
from test_identity_feedback import with_identity_facts
from analysis_contract import compact_fact, validate_analysis


class FactProjectionTests(unittest.TestCase):
    def test_projection_retains_source_facts_without_duplicated_descriptors(self):
        nodes = [node("parent", label="Parent"), node("child", label="Child")]
        store = with_identity_facts(case(nodes, reference_edges=[contains("child", "parent")]))
        original = deepcopy(store.comparison)
        report = build(store)
        validate_analysis(report, store)
        self.assertEqual(store.comparison, original)
        for item in report["annotations"]:
            source = [fact for fact in original["propertyFacts"]["items"] if item["target"]["id"] in fact["submissionIds"]
                      and not fact["code"].startswith(("identity.", "connection_group."))]
            self.assertEqual(item["facts"], [compact_fact(fact) for fact in source])
            self.assertTrue(any(fact["code"] == "label.equal" and fact["status"] == "satisfied" for fact in item["facts"]))
            self.assertFalse({"match", "checks", "consistency", "status"} & item.keys())

    def test_missing_reference_connection_has_original_ids_and_endpoint_target(self):
        store = with_identity_facts(case([node("a", label="A"), node("b", label="B"), node("e", "connection", directed=True)],
            [node("a", label="A"), node("b", label="B")], endpoints("e", "a", "b"), [], pairs=[]))
        report = build(store)
        hint = next(item for item in report["referenceHints"] if item["referenceId"] == "e")
        self.assertEqual(hint["target"]["id"], "a")
        self.assertIn({"side": "reference", "kind": "connection", "id": "e"}, hint["targets"])
        self.assertTrue(any(fact["code"].startswith("counterpart.") for fact in hint["facts"]))
        validate_analysis(report, store)

    def test_forged_facts_recognition_and_display_targets_are_rejected(self):
        nodes = [node("a", label="A"), node("b", label="B"), node("child", label="Child")]
        store = with_identity_facts(case(nodes, reference_edges=[contains("child", "a")], submission_edges=[contains("child", "b")]))
        original = build(store)
        mutations = [lambda report: report["annotations"][0]["facts"][0].update(status="satisfied" if report["annotations"][0]["facts"][0]["status"] != "satisfied" else "violated"),
                     lambda report: report["recognition"]["overall"].update(recognized=99),
                     lambda report: report["annotations"][2]["hints"][0]["targets"].append({"side":"submission", "kind":"modelElement", "id":"unknown"}),
                     lambda report: report["recognition"]["unmatchedSubmission"].append({"id":"unknown", "kind":"modelElement", "category":"nodes"})]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                report = deepcopy(original)
                mutate(report)
                rehash(report)
                with self.assertRaises(ValueError):
                    validate_analysis(report, store)


if __name__ == "__main__":
    unittest.main()
