import copy
import unittest

from artifacts import GRAPH_HASH_FIELDS, content_hash, read_artifacts
from test_graph_index import graph, node


class Store:
    def __init__(self):
        language = {"languageId": "test", "versionId": "1", "data": {"elements": []}}
        student = {"key": "submission", "role": "submission", "label": "S", "modelId": "s", "versionId": "1"}
        reference = {"key": "ref", "role": "reference", "label": "R", "modelId": "r", "versionId": "1"}
        self.bundle = {
            "evaluationId": "evaluation", "inputHash": "a" * 64, "comparisonConfig": {},
            "models": [{"source": student}, {"source": reference}], "languages": [language],
        }
        self.files = {}
        graphs = {}
        inventory_hashes = {}
        for side, source, identity in (("student", student, "s1"), ("reference", reference, "r1")):
            data = {
                "schema": "graph-result/v1", "evaluationId": "evaluation", "inputHash": "a" * 64,
                "source": source, "languageResources": [
                    {"languageId": "test", "versionId": "1", "hash": content_hash(language["data"])},
                ], "producer": {}, "graph": graph([node(identity)], []),
                "completeness": {"interpretation": "complete"}, "diagnostics": [],
            }
            data["graph"]["languages"] = [{"languageId": "test", "versionId": "1"}]
            data["graphHash"] = content_hash({field: data[field] for field in GRAPH_HASH_FIELDS})
            graphs[side] = data
            self.files[f"graphs/{source['key']}.json"] = self.wrap("graph-parser", data)
            element = data["graph"]["nodes"][0]
            inventory = {
                "schema": "element-inventory/v1", "evaluationId": "evaluation", "inputHash": "a" * 64,
                "source": source, "graphHash": data["graphHash"], "graphPath": f"graphs/{source['key']}.json",
                "elements": [{"id": identity, "type": element["type"], "comparisonGroup": None,
                              "language": element["language"], "matchText": "Name",
                              "labelStatus": "present", "textLanguage": "de"}],
                "connectionTexts": [], "producer": {}, "completeness": {"interpretation": "complete"},
                "diagnostics": [],
            }
            inventory["inventoryHash"] = content_hash(inventory)
            inventory_hashes[side] = inventory["inventoryHash"]
            self.files[f"labels/{source['key']}.json"] = self.wrap("model-label-extraction", inventory)
        config = {"methods": ["test"], "preprocessing": {"test": ["normalize"]}}
        self.candidates = {
            "schema": "semantic-candidates/v1", "evaluationId": "evaluation", "inputHash": "a" * 64,
            "pair": {"studentKey": "submission", "referenceKey": "ref"},
            "graphHashes": {side: value["graphHash"] for side, value in graphs.items()},
            "semanticConfig": config, "semanticConfigHash": content_hash(config),
            "methods": [{"name": "test", "scoreRange": [0, 1]}],
            "inventoryHashes": inventory_hashes,
            "inventoryPaths": {"student": "labels/submission.json", "reference": "labels/ref.json"},
            "producer": {}, "processedTexts": {"student": [], "reference": []},
            "connectionTextMatrix": [], "unscoredElements": [], "diagnostics": [],
            "completeness": {"technical": "complete", "interpretation": "complete"},
            "candidatePairCount": 1, "scoredPairCount": 1, "unavailablePairCount": 0,
            "synonymMatrix": [{
                "referenceElementId": "r1", "referenceLabel": "Name",
                "matches": [{"submissionElementId": "s1", "submissionLabel": "Name",
                             "comparisonBasis": "type", "scoreStatus": "scored", "scores": {"test": 1}}],
            }],
        }
        self.publish_candidates()

    @staticmethod
    def wrap(capability, data):
        return {"schema": "workflow-result/v1", "schemaVersion": 1, "status": "ok",
                "capability": capability, "result": data}

    def publish_candidates(self):
        self.candidates["candidateHash"] = content_hash(
            {key: value for key, value in self.candidates.items() if key != "candidateHash"}
        )
        self.files["candidates/ref.json"] = self.wrap("synonym-matching", self.candidates)

    def snapshot(self):
        return self.bundle

    def read(self, path):
        return self.files[path]


class ArtifactTests(unittest.TestCase):
    def test_complete_candidate_matrix_and_matching_provenance(self):
        bundle, graphs, indices, candidates = read_artifacts(Store(), "ref")
        self.assertEqual(bundle["evaluationId"], "evaluation")
        self.assertEqual(indices["reference"].nodes["r1"]["id"], "r1")
        self.assertEqual(candidates["graphHashes"]["student"], graphs["student"]["graphHash"])

    def test_rejects_filtered_matrix_even_with_recomputed_hash(self):
        store = Store()
        store.candidates["synonymMatrix"][0]["matches"] = []
        store.candidates["candidatePairCount"] = 0
        store.candidates["scoredPairCount"] = 0
        store.publish_candidates()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            read_artifacts(store, "ref")

    def test_rejects_corrupted_graph_and_candidate_hashes(self):
        store = Store()
        store.files["graphs/ref.json"]["result"]["graph"]["nodes"][0]["type"] = "tampered"
        with self.assertRaisesRegex(ValueError, "graph hash mismatch"):
            read_artifacts(store, "ref")
        store = Store()
        store.candidates["synonymMatrix"][0]["referenceLabel"] = "tampered"
        with self.assertRaisesRegex(ValueError, "candidate hash mismatch"):
            read_artifacts(store, "ref")

    def test_rejects_other_model_source_and_language_version(self):
        store = Store()
        store.bundle = copy.deepcopy(store.bundle)
        store.bundle["models"][1]["source"]["versionId"] = "other"
        with self.assertRaisesRegex(ValueError, "frozen model"):
            read_artifacts(store, "ref")
        store = Store()
        store.bundle["languages"][0]["data"]["elements"].append({"type": "different"})
        with self.assertRaisesRegex(ValueError, "language resource mismatch"):
            read_artifacts(store, "ref")

    def test_rejects_inventory_mismatch_and_changed_label_with_valid_candidate_hash(self):
        store = Store()
        store.files["labels/ref.json"]["result"]["elements"][0]["matchText"] = "changed"
        with self.assertRaisesRegex(ValueError, "inventory hash mismatch"):
            read_artifacts(store, "ref")
        store = Store()
        store.candidates["synonymMatrix"][0]["referenceLabel"] = "changed"
        store.publish_candidates()
        with self.assertRaisesRegex(ValueError, "candidate matrix row"):
            read_artifacts(store, "ref")


if __name__ == "__main__":
    unittest.main()
