import json
from pathlib import Path
import unittest
from unittest.mock import patch

import jsonschema
import numpy as np

from synonym_matching import service, workflow
from synonym_matching.config import DEFAULT_CONFIG

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def element(identity, element_type, group, text=None, version="v1"):
    present = text is not None
    return {
        "id": identity,
        "type": element_type,
        "comparisonGroup": group,
        "language": {"languageId": "serm", "versionId": version},
        "matchText": text or "",
        "labelStatus": "present" if present else "missing",
        "textLanguage": "de",
    }


def inventories(reference_elements, student_elements, reference_connections=None, student_connections=None):
    return {
        "reference": {"elements": reference_elements, "connectionTexts": reference_connections or []},
        "student": {"elements": student_elements, "connectionTexts": student_connections or []},
    }


class ComparePairTests(unittest.TestCase):
    def setUp(self):
        self.scorer_patch = patch.dict(
            service.SCORERS,
            {name: lambda left, right: np.ones((len(left), len(right)))
             for name in service.SCORERS},
        )
        self.scorer_patch.start()
        self.embedding_patch = patch.object(
            service.MultilingualMethod,
            "compute",
            lambda _self, left, right: np.ones((len(left), len(right))),
        )
        self.embedding_patch.start()
        self.addCleanup(self.scorer_patch.stop)
        self.addCleanup(self.embedding_patch.stop)

    def test_serm_pair_filter_produces_exactly_1544_candidates(self):
        reference_elements = [
            element(f"entity-r-{index}", "serm-entity", "serm-entity", f"Reference Entity {index}")
            for index in range(10)
        ] + [
            element(f"attribute-r-{index}", "serm-attribute", None, f"Reference Attribute {index}")
            for index in range(38)
        ]
        student_elements = [
            element(f"entity-s-{index}", "serm-entity", "serm-entity", f"Submission Entity {index}")
            for index in range(10)
        ] + [
            element(f"attribute-s-{index}", "serm-attribute", None, f"Submission Attribute {index}")
            for index in range(38)
        ]

        result = service.compare_pair(inventories(reference_elements, student_elements), DEFAULT_CONFIG)

        candidates = [
            (row["referenceElementId"], match["submissionElementId"], match["comparisonBasis"])
            for row in result["synonymMatrix"] for match in row["matches"]
        ]
        self.assertEqual(len(result["synonymMatrix"]), 48)
        self.assertEqual(result["candidatePairCount"], 1544)
        self.assertEqual(result["scoredPairCount"], 1544)
        self.assertEqual(result["unavailablePairCount"], 0)
        self.assertEqual(len(candidates), 1544)
        reference_types = {item["id"]: item["type"] for item in reference_elements}
        student_types = {item["id"]: item["type"] for item in student_elements}
        self.assertFalse(any(
            reference_types[reference_id] != student_types[student_id]
            for reference_id, student_id, _basis in candidates
        ))
        self.assertEqual(sum(basis == "group" for _, _, basis in candidates), 100)
        self.assertEqual(sum(basis == "type" for _, _, basis in candidates), 1444)

    def test_incompatible_languages_groups_and_mixed_grouping_are_excluded(self):
        reference = [
            element("same-type-r", "uml-class", None, "Class"),
            element("group-r", "type-a", "group-a", "Grouped"),
        ]
        student = [
            element("same-type-s", "uml-class", None, "Class", version="v2"),
            element("group-s", "type-b", "group-b", "Grouped"),
            element("mixed-s", "type-a", None, "Mixed"),
        ]

        result = service.compare_pair(inventories(reference, student), DEFAULT_CONFIG)

        self.assertEqual(result["candidatePairCount"], 0)
        self.assertTrue(all(not row["matches"] for row in result["synonymMatrix"]))

    def test_equal_groups_allow_different_types_even_at_zero_score(self):
        zero = lambda left, right: np.zeros((len(left), len(right)))
        with patch.dict(service.SCORERS, {name: zero for name in service.SCORERS}), \
                patch.object(service.MultilingualMethod, "compute", lambda _self, left, right: zero(left, right)):
            result = service.compare_pair(inventories(
                [element("reference", "type-a", "shared", "Alpha")],
                [element("submission", "type-b", "shared", "Unrelated")],
            ), DEFAULT_CONFIG)

        candidate = result["synonymMatrix"][0]["matches"][0]
        self.assertEqual(candidate["comparisonBasis"], "group")
        self.assertEqual(candidate["scoreStatus"], "scored")
        self.assertEqual(candidate["combinedScore"], 0)
        self.assertEqual(result["candidatePairCount"], 1)

    def test_textless_allowed_pair_is_kept_with_unavailable_scores(self):
        result = service.compare_pair(inventories(
            [element("reference", "serm-attribute", None)],
            [element("submission", "serm-attribute", None, "Name")],
        ), DEFAULT_CONFIG)

        candidate = result["synonymMatrix"][0]["matches"][0]
        self.assertEqual(candidate["scoreStatus"], "unavailable")
        self.assertIsNone(candidate["scores"])
        self.assertIsNone(candidate["combinedScore"])
        self.assertEqual(result["candidatePairCount"], 1)
        self.assertEqual(result["scoredPairCount"], 0)
        self.assertEqual(result["unavailablePairCount"], 1)
        self.assertEqual(result["processedTexts"]["reference"], [])
        self.assertEqual(result["processedTexts"]["student"], [{"id": "submission", "text": "Name"}])

    def test_connection_label_candidates_are_separate_and_retained(self):
        ref_connections = [
            {"id": "r-self", "ownerConnectionId": "r-link", "kind": "self",
             "connectionLabelId": None, "labelStatus": "present", "matchText": "connects",
             "textLanguage": "de"},
            {"id": "r-label", "ownerConnectionId": "r-link", "kind": "additionalLabel",
             "connectionLabelId": "label-id", "labelStatus": "present", "matchText": "relationship",
             "textLanguage": "de"},
        ]
        sub_connections = [
            {"id": "s-self", "ownerConnectionId": "s-link", "kind": "self",
             "connectionLabelId": None, "labelStatus": "present", "matchText": "connects",
             "textLanguage": "de"},
            {"id": "s-label", "ownerConnectionId": "s-link", "kind": "additionalLabel",
             "connectionLabelId": "label-id", "labelStatus": "present", "matchText": "relationship",
             "textLanguage": "de"},
            {"id": "s-other-label", "ownerConnectionId": "s-link", "kind": "additionalLabel",
             "connectionLabelId": "other-id", "labelStatus": "present", "matchText": "other",
             "textLanguage": "de"},
        ]

        result = service.compare_pair(inventories([], [], ref_connections, sub_connections), DEFAULT_CONFIG)

        self.assertEqual(result["connectionTextPairCount"], 2)
        rows = {row["referenceConnectionTextId"]: row for row in result["connectionTextMatrix"]}
        self.assertEqual([len(row["matches"]) for row in rows.values()], [1, 1])
        candidate = rows["r-label"]["matches"][0]
        self.assertEqual(candidate["submissionConnectionTextId"], "s-label")
        self.assertEqual(candidate["scoreStatus"], "unavailable")
        self.assertIsNone(candidate["scores"])
        self.assertEqual(
            candidate["unavailableReason"],
            "connection_owner_compatibility_not_in_inventory",
        )

    def test_workflow_emits_v2_contract_and_valid_schema(self):
        source_data = {
            "student": {"elements": [element("submission", "x", None, "Alpha")],
                        "connectionTexts": [{
                            "id": "submission-connection-text", "ownerConnectionId": "submission-link",
                            "kind": "self", "connectionLabelId": None,
                            "labelStatus": "present", "matchText": "connects", "textLanguage": "de",
                        }], "source": {"key": "submission"},
                        "evaluationId": "evaluation", "inputHash": "a" * 64,
                        "graphHash": "b" * 64, "inventoryHash": "c" * 64,
                        "completeness": {"interpretation": "complete"}},
            "reference": {"elements": [element("reference", "x", None, "Alpha")],
                          "connectionTexts": [{
                              "id": "reference-connection-text", "ownerConnectionId": "reference-link",
                              "kind": "self", "connectionLabelId": None,
                              "labelStatus": "present", "matchText": "connects", "textLanguage": "de",
                          }], "source": {"key": "reference-model"},
                          "evaluationId": "evaluation", "inputHash": "a" * 64,
                          "graphHash": "d" * 64, "inventoryHash": "e" * 64,
                          "completeness": {"interpretation": "complete"}},
        }
        producer = {
            "service": "synonym-matching", "version": "0.1.0", "resourceHash": "f" * 64,
            "runtime": {"python": "3.12", "unicode": "15.0"},
            "packages": {"numpy": "2", "rapidfuzz": "3"},
        }
        with patch.object(workflow, "read_pair", return_value=source_data), \
                patch.object(workflow, "producer_metadata", return_value=producer):
            output = workflow.run({})

        output_schema = json.loads((SERVICE_ROOT / "schemas" / "output.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(output, output_schema)
        self.assertEqual(output["result"]["schema"], "semantic-candidates/v2")
        self.assertEqual(output["result"]["candidatePairCount"], 1)
        self.assertEqual(output["result"]["scoredPairCount"], 1)
        self.assertEqual(output["result"]["unavailablePairCount"], 0)
        self.assertEqual(output["result"]["connectionTextPairCount"], 1)
        self.assertEqual(output["result"]["completeness"]["interpretation"], "partial")
        self.assertEqual(
            output["result"]["connectionTextMatrix"][0]["matches"][0]["scoreStatus"],
            "unavailable",
        )
        self.assertEqual(output["result"]["processedTexts"]["reference"], [
            {"id": "reference", "text": "Alpha"},
        ])


if __name__ == "__main__":
    unittest.main()
