"""Verify the frozen artifact boundary and preserved frontend stdout envelope."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
import sys
import subprocess
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


feedback = load("feedback", SERVICES / "feedback-generation/src/main.py")
service = load("analytical_service", SERVICES / "analytical-feedback/src/main.py")
matcher = load("matching_fixture", SERVICES / "one-to-one-graph-matching/src/main.py")


class ServiceTests(unittest.TestCase):
    def test_stdout_artifact_and_downstream_feedback_use_same_analysis(self):
        # Reuse the matcher's existing tiny artifact fixture; never start a workflow.
        store = Store()
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
        self.assertEqual(envelope["result"]["schema"], "analysis-feedback/v3")
        result = feedback.run(store, "ref", envelope["analysisPath"])["result"]
        self.assertEqual(result["analysisHash"], envelope["result"]["analysisHash"])
        self.assertEqual(result["recognition"], envelope["result"]["recognition"])
        self.assertEqual(result["recognition"]["buckets"][0]["recognized"], 1)
        self.assertFalse({"categories", "totals", "analyticalSummary", "metrics"} & result.keys())
        from test_contract import CHECK, ROOT
        payload = [{"envelope": envelope, "feedback": result, "context": {
            "evaluationId": "evaluation", "referenceKey": "ref", "modelId": "s",
            "submissionObjects": store.files["graphs/submission.json"]["result"]["graph"]["nodes"],
            "referenceObjects": store.files["graphs/ref.json"]["result"]["graph"]["nodes"]}}]
        check = subprocess.run(["node", "-e", CHECK], input=json.dumps(payload), cwd=ROOT,
                               text=True, capture_output=True, check=False)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        with self.assertRaisesRegex(ValueError, "feedback path"):
            feedback.run(store, "ref")


if __name__ == "__main__":
    unittest.main()
