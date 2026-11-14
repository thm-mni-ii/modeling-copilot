"""Verify the frozen artifact boundary and preserved frontend stdout envelope."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

from test_analysis import SERVICES
sys.path.insert(0, str(SERVICES / "one-to-one-graph-matching/tests"))
from test_artifacts import Store
from artifacts import GRAPH_HASH_FIELDS, content_hash


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


comparison_report = load("comparison_report", SERVICES / "feedback-generation/src/main.py")
service = load("analytical_service", SERVICES / "analytical-feedback/src/main.py")
matcher = load("matching_fixture", SERVICES / "one-to-one-graph-matching/src/main.py")


class ServiceTests(unittest.TestCase):
    def test_stdout_artifact_and_downstream_feedback_use_same_analysis(self):
        # Reuse the matcher's existing tiny artifact fixture; never start a workflow.
        store = Store()
        store.bundle["languages"][0]["data"]["evaluation"] = {"elementCategories": {"modelElement": "nodes"}}
        for side, key in (("student", "submission"), ("reference", "ref")):
            graph = store.files[f"graphs/{key}.json"]["result"]
            graph["languageResources"][0]["hash"] = content_hash(store.bundle["languages"][0]["data"])
            graph["graphHash"] = content_hash({field: graph[field] for field in GRAPH_HASH_FIELDS})
            inventory = store.files[f"labels/{key}.json"]["result"]
            inventory["graphHash"] = graph["graphHash"]
            inventory["inventoryHash"] = content_hash({field: value for field, value in inventory.items() if field != "inventoryHash"})
            store.candidates["graphHashes"][side] = graph["graphHash"]
            store.candidates["inventoryHashes"][side] = inventory["inventoryHash"]
        store.publish_candidates()
        store.files["comparisons/ref.json"] = matcher.run(store, "ref")
        output = io.StringIO()
        with patch.object(service, "workspace", return_value=store), patch.dict(os.environ, {"REFERENCE_KEY": "ref"}), \
             patch.object(store, "write", side_effect=lambda path, value: store.files.update({path: value}), create=True), \
             redirect_stdout(output):
            self.assertEqual(service.main(), 0)
        envelope = json.loads(output.getvalue())
        self.assertEqual(output.getvalue().count("\n"), 1)
        self.assertEqual(envelope["result"]["contractVersion"], "1.3")
        result = comparison_report.run(store, "ref", envelope["analysisPath"])["result"]
        self.assertEqual(result["analysisHash"], envelope["result"]["analysisHash"])
        self.assertEqual(result["analyticalSummary"], envelope["result"]["summary"])
        self.assertEqual(result["analyticalSummary"]["nodes"]["recognized"], 1)
        self.assertEqual(result["categories"][3]["provisionalRecognizedCount"], 1)


if __name__ == "__main__":
    unittest.main()
