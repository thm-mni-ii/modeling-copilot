"""The selected identity status is the only recognition counting rule."""
from copy import deepcopy
import unittest

from test_analysis import case, node
from test_identity_feedback import with_identity_facts
from analysis_contract import recognized_reference_ids, recognition_summary


class RecognitionDefinitionTests(unittest.TestCase):
    def test_duplicate_selected_correspondences_are_rejected(self):
        store = with_identity_facts(case([node("known", label="Known")]))
        store.comparison["mapping"]["provisionalElements"] *= 2
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            recognized_reference_ids(store.comparison)

    def test_recognition_category_belongs_to_reference_despite_compatible_type_difference(self):
        from test_analysis import build
        from analysis_contract import validate_analysis
        store = with_identity_facts(case([node("r", label="Known", comparisonGroup="compatible")],
            [node("s", native_type="property", label="Known", comparisonGroup="compatible")], pairs=[]))
        report = build(store)
        validate_analysis(report, store)
        self.assertEqual(len(report["recognition"]["buckets"]), 1)
        self.assertTrue(report["recognition"]["buckets"][0]["grouped"])
        self.assertEqual(report["recognition"]["buckets"][0]["recognized"], 1)

    def test_partially_evaluable_category_keeps_complete_reference_denominator(self):
        store = with_identity_facts(case([node("known", label="Known"), node("open", label="Open")]))
        identity = next(fact for fact in store.comparison["propertyFacts"]["items"] if fact["code"].startswith("identity.") and fact["referenceIds"] == ["open"])
        identity["evidence"].update(identityStatus="not_evaluated", evaluationStatus="not_evaluated")
        self.assertEqual({key: recognition_summary(store.bundle, store.indices, store.comparison)["buckets"][0][key] for key in ("recognized", "expected", "percent", "evaluationStatus")},
                         {"recognized": 1, "expected": 2, "percent": 50.0, "evaluationStatus": "partial"})

    def test_category_totals_count_only_unique_identities_and_keep_unmatched_submission(self):
        from test_analysis import contains
        reference = [node("parent", label="Parent"), node("child", native_type="property", label="Child"), node("container", "structuralElement")]
        store = with_identity_facts(case(reference, reference + [node("extra", label="Extra")],
            reference_edges=[contains("child", "parent")], submission_edges=[contains("child", "parent")]))
        child = next(item for item in store.comparison["propertyFacts"]["items"] if item["code"].startswith("identity.") and item["referenceIds"] == ["child"])
        child["evidence"]["identityStatus"] = "supported"
        result = recognition_summary(store.bundle, store.indices, store.comparison)
        self.assertEqual([(row["label"], row["recognized"], row["expected"]) for row in result["buckets"]], [("entity", 1, 1), ("property", 0, 1)])
        self.assertEqual(result["overall"], {"recognized": 1, "expected": 2, "percent": 50.0, "evaluationStatus": "evaluated"})
        self.assertEqual([item["id"] for item in result["unmatchedSubmission"]], ["extra"])

    def test_empty_and_not_evaluable_categories_do_not_show_zero_percent(self):
        store = with_identity_facts(case([node("opaque", languageResolution="unresolved", label="")]))
        report = recognition_summary(store.bundle, store.indices, store.comparison)
        self.assertEqual(len(report["buckets"]), 1)
        self.assertIsNone(report["buckets"][0]["percent"])
        self.assertEqual(report["buckets"][0]["evaluationStatus"], "not_evaluated")
        empty = with_identity_facts(case([]))
        result = recognition_summary(empty.bundle, empty.indices, empty.comparison)
        self.assertEqual(result["buckets"], [])
        self.assertIsNone(result["overall"]["percent"])

    def test_groups_merge_types_but_submission_only_types_do_not_add_rows(self):
        reference = [node("a", native_type="first", comparisonGroup="g", label="A"),
                     node("b", native_type="second", comparisonGroup="g", label="B"), node("c", label="C")]
        store = with_identity_facts(case(reference, reference + [node("extra", native_type="foreign", label="Extra")]))
        store.bundle["languages"][0]["data"] = {"evaluation": {"comparisonGroups": [{"id":"g", "name":"My group", "elementTypes":["first","second"]}]}}
        result = recognition_summary(store.bundle, store.indices, store.comparison)
        self.assertEqual([(row["label"], row["recognized"], row["expected"]) for row in result["buckets"]], [("My group", 2, 2), ("entity", 1, 1)])
        self.assertEqual(result["unmatchedSubmission"], [{"id":"extra", "kind":"modelElement"}])

    def test_supported_and_unresolved_do_not_count_as_recognized(self):
        store = with_identity_facts(case([node("known", label="Known"), node("open", label="Open")]))
        comparison = store.comparison
        self.assertEqual(recognized_reference_ids(comparison), {"known", "open"})
        identity = next(item for item in comparison["propertyFacts"]["items"] if item["code"].startswith("identity.") and item["referenceIds"] == ["open"])
        for status in ("supported", "unresolved", "not_evaluated"):
            identity["evidence"]["identityStatus"] = status
            self.assertEqual(recognized_reference_ids(comparison), {"known"})

    def test_group_ids_are_scoped_by_language_and_object_kind(self):
        from test_analysis import endpoints
        nodes = [node("a", label="A", comparisonGroup="g"),
                 node("b", label="B", comparisonGroup="g", language={"languageId": "different", "versionId": "1"}),
                 node("link", "connection", comparisonGroup="g", directed=True)]
        store = with_identity_facts(case(nodes, reference_edges=endpoints("link", "a", "b")))
        result = recognition_summary(store.bundle, store.indices, store.comparison)
        self.assertEqual(len(result["buckets"]), 3)
        self.assertEqual(sum(row["expected"] for row in result["buckets"]), 3)

    def test_compatibility_and_cyclic_dependencies_cannot_support_recognition(self):
        store = with_identity_facts(case([node("a", label="A"), node("b", label="B")]))
        comparison = deepcopy(store.comparison)
        identity = next(item for item in comparison["propertyFacts"]["items"] if item["code"].startswith("identity."))
        for criterion in identity["evidence"]["criteria"]:
            criterion["role"] = "compatibility"
        with self.assertRaisesRegex(ValueError, "sufficient evidence"):
            recognized_reference_ids(comparison)
        comparison = deepcopy(store.comparison)
        for row, dependency in zip(comparison["mapping"]["provisionalElements"], ("b", "a")):
            row["dependsOn"] = [{"referenceId": dependency, "studentId": dependency}]
        with self.assertRaisesRegex(ValueError, "cyclic"):
            recognized_reference_ids(comparison)


if __name__ == "__main__":
    unittest.main()
