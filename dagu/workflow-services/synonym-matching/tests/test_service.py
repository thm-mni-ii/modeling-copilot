import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import jsonschema
import numpy as np

from synonym_matching import service, workflow
from synonym_matching.config import resolve_config
from synonym_matching.methods.multilingual import MultilingualMethod
from synonym_matching.methods.registry import METHOD_REGISTRY, MethodDefinition
from synonym_matching.provenance import content_hash

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def element(identity, element_type, group, text=None, version="v1", status=None):
    return {
        "id": identity,
        "type": element_type,
        "comparisonGroup": group,
        "language": {"languageId": "serm", "versionId": version},
        "matchText": text or "",
        "labelStatus": status or ("present" if text else "missing"),
        "textLanguage": "de",
    }


def connection_text(identity, kind="self", text=None, label_id=None, owner=None, status=None):
    return {
        "id": identity,
        "ownerConnectionId": owner or f"owner-{identity}",
        "kind": kind,
        "connectionLabelId": label_id,
        "matchText": text or "",
        "labelStatus": status or ("present" if text else "missing"),
        "textLanguage": "de",
    }


def inventories(reference_elements, student_elements, reference_connections=None, student_connections=None):
    return {
        "reference": {"elements": reference_elements, "connectionTexts": reference_connections or []},
        "student": {"elements": student_elements, "connectionTexts": student_connections or []},
    }


def score_ones(_state, left, right):
    return np.ones((len(left), len(right)))


def score_method_registry(compute=score_ones):
    return {
        name: MethodDefinition(
            name, original.score_range, compute, original.preprocessing,
            parameters=original.parameters,
        )
        for name, original in METHOD_REGISTRY.items()
    }


class ComparePairTests(unittest.TestCase):
    def setUp(self):
        self.registry_patch = patch.dict(METHOD_REGISTRY, score_method_registry())
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)

    def test_serm_pair_filter_produces_exactly_1544_candidates(self):
        reference_elements = [
            element(f"entity-r-{index}", "serm-entity", "serm-entity", f"Reference Entity {index}")
            for index in range(10)
        ] + [
            element(f"attribute-r-{index}", "serm-attribute", None, "Name")
            for index in range(38)
        ]
        student_elements = [
            element(f"entity-s-{index}", "serm-entity", "serm-entity", f"Submission Entity {index}")
            for index in range(10)
        ] + [
            element(f"attribute-s-{index}", "serm-attribute", None, "Name")
            for index in range(38)
        ]

        result = service.compare_pair(inventories(reference_elements, student_elements), resolve_config({}))

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
        attribute_row = next(row for row in result["synonymMatrix"]
                             if row["referenceElementId"] == "attribute-r-0")
        self.assertEqual(len(attribute_row["matches"]), 38)
        self.assertEqual(len({match["submissionElementId"] for match in attribute_row["matches"]}), 38)

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
        result = service.compare_pair(inventories(reference, student), resolve_config({}))
        self.assertEqual(result["candidatePairCount"], 0)
        self.assertTrue(all(not row["matches"] for row in result["synonymMatrix"]))

    def test_equal_groups_keep_distinct_instances_even_at_zero_score(self):
        zero = lambda _state, left, right: np.zeros((len(left), len(right)))
        with patch.dict(METHOD_REGISTRY, score_method_registry(zero)):
            result = service.compare_pair(inventories(
                [element("reference", "type-a", "shared", "Alpha")],
                [element("submission", "type-b", "shared", "Unrelated")],
            ), resolve_config({"semantics": {"methods": ["levenshtein"]}}))

        candidate = result["synonymMatrix"][0]["matches"][0]
        self.assertEqual(candidate["comparisonBasis"], "group")
        self.assertEqual(candidate["scores"], {"levenshtein": 0.0})
        self.assertEqual(result["candidatePairCount"], 1)

    def test_textless_allowed_pair_is_kept_with_explanation(self):
        result = service.compare_pair(inventories(
            [element("reference", "serm-attribute", None)],
            [element("submission", "serm-attribute", None, "Name")],
        ), resolve_config({}))

        candidate = result["synonymMatrix"][0]["matches"][0]
        self.assertEqual(candidate["scoreStatus"], "unavailable")
        self.assertEqual(candidate["unavailableReason"], "missing_text")
        self.assertIsNone(candidate["scores"])
        self.assertEqual(result["candidatePairCount"], 1)
        self.assertEqual(result["scoredPairCount"], 0)
        self.assertEqual(result["unavailablePairCount"], 1)

    def test_method_registry_activates_a_fifth_method_and_schema_accepts_it(self):
        fifth = MethodDefinition("test_fifth", (0, 1), score_ones, parameters={"variant": "constant"})
        with patch.dict(METHOD_REGISTRY, {"test_fifth": fifth}):
            config = resolve_config({"semantics": {"methods": ["test_fifth"]}})
            result = service.compare_pair(inventories(
                [element("reference", "entity", None, "Alpha")],
                [element("submission", "entity", None, "Alpha")],
            ), config)
            self.assertEqual(result["methods"][0]["name"], "test_fifth")
            self.assertEqual(result["methods"][0]["scoreRange"], [0, 1])
            self.assertEqual(result["synonymMatrix"][0]["matches"][0]["scores"], {"test_fifth": 1.0})

            output = self._workflow_result(config)
            schema = json.loads((SERVICE_ROOT / "schemas" / "output.schema.json").read_text(encoding="utf-8"))
            jsonschema.validate(output, schema)
            self.assertEqual(output["result"]["synonymMatrix"][0]["matches"][0]["scores"], {"test_fifth": 1.0})
            candidate = output["result"]["synonymMatrix"][0]["matches"][0]
            self.assertNotIn("combinedScore", candidate)
            self.assertNotIn("combiner", output["result"])
            self.assertNotIn("weighted_fusion", json.dumps(output))

    def test_unknown_duplicate_and_invalid_method_settings_fail(self):
        for settings, message in (
            ({"methods": ["unknown"]}, "unknown similarity method"),
            ({"methods": ["levenshtein", "levenshtein"]}, "must not contain duplicates"),
            ({"methods": []}, "non-empty array"),
            ({"preprocessing": ["unknown"]}, "unknown text preprocessing"),
        ):
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, message):
                resolve_config({"semantics": settings})

    def test_invalid_method_matrix_values_fail(self):
        bad = MethodDefinition("bad", (0, 1), lambda _state, left, right: np.full((len(left), len(right)), np.nan))
        with patch.dict(METHOD_REGISTRY, {"bad": bad}):
            with self.assertRaisesRegex(ValueError, "invalid score matrix from bad"):
                service.compare_pair(inventories(
                    [element("reference", "entity", None, "Alpha")],
                    [element("submission", "entity", None, "Alpha")],
                ), resolve_config({"semantics": {"methods": ["bad"]}}))

    def test_connection_matrix_contains_only_present_compatible_text_pairs(self):
        ref = [
            connection_text("r-self", text="connects", owner="r-link"),
            connection_text("r-missing"),
            connection_text("r-role", "additionalLabel", "owner", "role", "r-link"),
            connection_text("r-card", "additionalLabel", "1..n", "cardinality", "r-link"),
        ]
        sub = [
            connection_text("s-self", text="connects", owner="s-link"),
            connection_text("s-missing", owner="s-link"),
            connection_text("s-role", "additionalLabel", "owns", "role", "s-link"),
            connection_text("s-card", "additionalLabel", "1..n", "cardinality", "s-link"),
            connection_text("s-other", "additionalLabel", "owner", "other-slot", "s-link"),
        ]
        result = service.compare_pair(inventories([], [], ref, sub), resolve_config({}))

        self.assertEqual(len(result["connectionTextMatrix"]), 3)
        self.assertEqual(
            [(pair["referenceConnectionTextId"], pair["submissionConnectionTextId"])
             for pair in result["connectionTextMatrix"]],
            [("r-card", "s-card"), ("r-role", "s-role"), ("r-self", "s-self")],
        )
        self.assertTrue(all(pair["scores"] == {name: 1.0 for name in METHOD_REGISTRY}
                            for pair in result["connectionTextMatrix"]))

    def test_unlabeled_connections_produce_an_empty_matrix(self):
        result = service.compare_pair(inventories(
            [], [], [connection_text(f"r-{index}") for index in range(10)],
            [connection_text(f"s-{index}") for index in range(10)],
        ), resolve_config({}))
        self.assertEqual(result["connectionTextMatrix"], [])

    def test_one_sided_connection_text_does_not_create_a_candidate(self):
        result = service.compare_pair(inventories(
            [], [], [connection_text("reference-text", text="connects")],
            [connection_text("submission-text")],
        ), resolve_config({}))
        self.assertEqual(result["connectionTextMatrix"], [])

    def test_normalization_and_raw_inventory_text_are_preserved(self):
        original = inventories(
            [element("reference", "entity", None, "  Cafe\u0301\n  Forschungs\tprojekt ")],
            [element("submission", "entity", None, "Café Forschungs projekt")],
        )
        untouched = copy.deepcopy(original)
        result = service.compare_pair(original, resolve_config({}))

        self.assertEqual(original, untouched)
        self.assertEqual(result["processedTexts"]["reference"][0]["text"], "Café Forschungs projekt")
        self.assertEqual(result["processedTexts"]["student"][0]["text"], "Café Forschungs projekt")
        self.assertEqual(result["synonymMatrix"][0]["matches"][0]["submissionElementId"], "submission")

    def test_empty_preprocessing_can_be_selected(self):
        config = resolve_config({"semantics": {"methods": ["levenshtein"], "preprocessing": []}})
        result = service.compare_pair(inventories(
            [element("reference", "entity", None, "A\nB")],
            [element("submission", "entity", None, "A B")],
        ), config)
        self.assertEqual(result["semanticConfig"]["preprocessing"]["levenshtein"], [])
        self.assertEqual(result["processedTexts"]["reference"][0]["text"], "A\nB")

    def test_registry_method_uses_its_declared_preprocessing(self):
        seen = []

        def capture(_state, left, right):
            seen.extend(left + right)
            return np.ones((len(left), len(right)))

        raw_method = MethodDefinition("raw_text", (0, 1), capture, preprocessing=())
        with patch.dict(METHOD_REGISTRY, {"raw_text": raw_method}):
            result = service.compare_pair(inventories(
                [element("reference", "entity", None, "A\nB")],
                [element("submission", "entity", None, "A B")],
            ), resolve_config({"semantics": {"methods": ["raw_text"]}}))
        self.assertIn("A\nB", seen)
        self.assertIn("A B", seen)
        self.assertEqual(result["methods"][0]["preprocessing"], [])

    def test_embedding_model_instance_reuses_embeddings_across_calls(self):
        class FakeTokenizer:
            def encode(self, text):
                return [len(text)]

        class FakeModel:
            tokenizer = FakeTokenizer()
            max_seq_length = 8

            def __init__(self):
                self.encoded = []

            def encode(self, texts, **_kwargs):
                self.encoded.append(list(texts))
                return np.asarray([[1.0, 0.0] for _ in texts])

        method = MultilingualMethod({"batch_size": 32})
        method.model = FakeModel()
        method.compute(["same"], ["same"])
        method.compute(["same"], ["other"])
        self.assertEqual(method.model.encoded, [["same"], ["other"]])

    def test_workflow_emits_v1_contract_validates_and_is_deterministic(self):
        config = resolve_config({"semantics": {"methods": ["levenshtein"]}})
        first = self._workflow_result(config)
        second = self._workflow_result(config)
        schema = json.loads((SERVICE_ROOT / "schemas" / "output.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(first, schema)
        self.assertEqual(first, second)
        self.assertEqual(first["result"]["schema"], "semantic-candidates/v1")
        self.assertEqual(first["result"]["candidateHash"], content_hash({
            key: value for key, value in first["result"].items() if key != "candidateHash"
        }))
        self.assertNotIn("semantic-candidates/v2", json.dumps(first))

    def _workflow_result(self, config):
        source_data = {
            "student": {
                "elements": [element("submission", "x", None, "Alpha")],
                "connectionTexts": [connection_text("submission-text", text="connects")],
                "source": {"key": "submission"}, "evaluationId": "evaluation",
                "inputHash": "a" * 64, "graphHash": "b" * 64, "inventoryHash": "c" * 64,
                "completeness": {"interpretation": "complete"},
            },
            "reference": {
                "elements": [element("reference", "x", None, "Alpha")],
                "connectionTexts": [connection_text("reference-text", text="connects")],
                "source": {"key": "reference-model"}, "evaluationId": "evaluation",
                "inputHash": "a" * 64, "graphHash": "d" * 64, "inventoryHash": "e" * 64,
                "completeness": {"interpretation": "complete"},
            },
        }
        producer = {
            "service": "synonym-matching", "version": "0.1.0", "resourceHash": "f" * 64,
            "runtime": {"python": "3.12", "unicode": "15.0"},
            "packages": {"numpy": "2", "rapidfuzz": "3"},
        }
        with patch.object(workflow, "read_pair", return_value=source_data), \
                patch.object(workflow, "resolve_config", return_value=config), \
                patch.object(workflow, "producer_metadata", return_value=producer):
            return workflow.run({})


if __name__ == "__main__":
    unittest.main()
