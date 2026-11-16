"""Verify the frozen artifact boundary and preserved frontend stdout envelope."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
import sys
import subprocess
import unittest
from copy import deepcopy
from unittest.mock import patch

from test_analysis import SERVICES
sys.path.insert(0, str(SERVICES / "one-to-one-graph-matching/tests"))
from test_artifacts import Store
from artifacts import GRAPH_HASH_FIELDS, content_hash
from artifacts import _key
from workflow_io import input_hash


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


feedback = load("feedback", SERVICES / "feedback-generation/src/main.py")
service = load("analytical_service", SERVICES / "analytical-feedback/src/main.py")
matcher = load("matching_fixture", SERVICES / "one-to-one-graph-matching/src/main.py")
sys.path.insert(0, str(SERVICES / "graph-parser/src"))
parser_service = load("acceptance_parser", SERVICES / "graph-parser/src/main.py")
extractor = load("acceptance_extractor", SERVICES / "model-label-extraction/src/main.py")


def declared_pair(language, scenario):
    """Real parser/extractor artifacts with a complete synthetic candidate matrix."""
    store = Store()
    bundle = {"schema": "evaluation-input/v1", "schemaVersion": 1, "evaluationId": "evaluation",
              "task": {"data": {}}, "comparisonConfig": {}, "languages": [deepcopy(language)], "models": []}
    parent_type, child_type = [row["type"] for row in language["data"]["elements"]]
    link_type = language["data"]["connections"][0]["type"]
    if scenario == "caption":
        bundle["languages"][0]["data"]["connections"][0]["additionalLabels"] = [{"type": "role"}]
    for side, key, prefix in (("reference", "ref", "r"), ("student", "submission", "s")):
        source = store.bundle["models"][0 if side == "student" else 1]["source"]
        pin = {field: language[field] for field in ("languageId", "versionId")}
        if scenario == "version_mix" and side == "student":
            pin["versionId"] = "2"
            bundle["languages"].append({**deepcopy(language), "versionId": "2"})
        owner = "b" if scenario == "moved" and side == "student" else "a"
        extra = f'<Cell id="{prefix}-unknown" diagramElementType="unknown" vertex="1" parent="modeling"/>' if scenario == "unknown" else ""
        if scenario == "caption":
            extra = f'<Cell id="{prefix}-caption" connectionLabelId="role" value="Owner" parent="{prefix}-e"/>'
        xml = ('<GraphDataModel><root><Cell id="canvas"/><Cell id="modeling" parent="canvas"/><Cell id="feedback" parent="canvas"/>'
               f'<Cell id="{prefix}-a" value="Alpha" diagramElementType="{parent_type}" vertex="1" parent="modeling"/>'
               f'<Cell id="{prefix}-b" value="Beta" diagramElementType="{parent_type}" vertex="1" parent="modeling"/>'
               f'<Cell id="{prefix}-c" value="Code" diagramElementType="{child_type}" vertex="1" parent="{prefix}-{owner}"/>'
               f'<Cell id="{prefix}-e" value="Owns" connectionId="{link_type}" edge="1" source="{prefix}-a" target="{prefix}-b" parent="modeling"/>'
               f'{extra}</root></GraphDataModel>')
        bundle["models"].append({"source": source, "snapshot": {"modelId": source["modelId"], "versionId": source["versionId"],
                                  "workspaceLanguages": [pin], "data": {"format": "maxgraph-xml", "version": 1, "xml": xml}}})
    bundle["inputHash"] = input_hash(bundle)
    store.bundle = bundle
    for key in ("ref", "submission"):
        parsed = parser_service.run({"input": bundle, "modelKey": key})
        store.files[f"graphs/{key}.json"] = parsed
        store.files[f"labels/{key}.json"] = extractor.run(parsed)
    inventories = {side: store.files[f"labels/{key}.json"]["result"] for side, key in (("reference", "ref"), ("student", "submission"))}
    candidate = store.candidates
    candidate["methods"][0].update(preprocessing=["normalize"], parameters={})
    candidate.update(inputHash=bundle["inputHash"],
        graphHashes={side: data["graphHash"] for side, data in inventories.items()},
        inventoryHashes={side: data["inventoryHash"] for side, data in inventories.items()},
        synonymMatrix=[{"referenceElementId": ref["id"], "referenceLabel": ref["matchText"], "matches": [
            {"submissionElementId": sub["id"], "submissionLabel": sub["matchText"], "comparisonBasis": _key(ref)[2],
             "scoreStatus": "scored", "scores": {"test": 1}}
            for sub in inventories["student"]["elements"] if _key(ref) is not None and _key(ref) == _key(sub)]}
            for ref in inventories["reference"]["elements"]],
        producer={"service": "synthetic-acceptance-evidence", "version": "1.0.0", "resourceHash": content_hash(language), "runtime": {}, "packages": {}},
        completeness={"technical": "complete", "interpretation": "partial" if scenario == "unknown" else "complete"})
    candidate["candidatePairCount"] = candidate["scoredPairCount"] = sum(len(row["matches"]) for row in candidate["synonymMatrix"])
    store.publish_candidates()
    store.files["candidates/ref.json"].update(mode="match", summary="Complete synthetic acceptance evidence")
    return store


class ServiceTests(unittest.TestCase):
    def test_declared_languages_preserve_identity_facts_and_reject_version_mix(self):
        import json
        languages = json.loads((SERVICES / "analytical-feedback/tests/fixtures/declared-languages.json").read_text())
        samples = []
        for language in languages:
            for scenario in ("baseline", "moved", "unknown", "version_mix", "caption"):
                with self.subTest(language=language["languageId"], scenario=scenario):
                    store = declared_pair(language, scenario)
                    comparison = matcher.run(store, "ref")
                    store.files["comparisons/ref.json"] = comparison
                    envelope = service.run(store, "ref")
                    store.files[envelope["analysisPath"]] = envelope
                    result = feedback.run(store, "ref", envelope["analysisPath"])["result"]
                    self.assertEqual(result["recognition"], envelope["result"]["recognition"])
                    recognition = result["recognition"]["overall"]
                    self.assertEqual(recognition["recognized"], 0 if scenario == "version_mix" else 4)
                    self.assertEqual(recognition["expected"], 5 if scenario == "unknown" else 4)
                    annotations = {row["target"]["id"]: row for row in envelope["result"]["annotations"]}
                    extra_ids = {"s-unknown"} if scenario == "unknown" else {"s-caption"} if scenario == "caption" else set()
                    self.assertEqual(set(annotations), {f"s-{suffix}" for suffix in ("a", "b", "c", "e")} | extra_ids)
                    if scenario == "caption":
                        self.assertEqual(envelope["result"]["structuralContainers"], {"referenceCount": 0, "submissionCount": 0})
                    if scenario == "baseline":
                        self.assertTrue(all(fact["status"] in ("satisfied", "not_applicable") for row in annotations.values() for fact in row["facts"]))
                    if scenario == "moved":
                        self.assertEqual(annotations["s-c"]["referenceId"], "r-c")
                        placement = next(fact for fact in annotations["s-c"]["facts"] if fact["code"].startswith("owner."))
                        self.assertEqual(placement["status"], "violated")
                    if scenario == "unknown":
                        self.assertEqual(recognition["evaluationStatus"], "partial")
                        self.assertNotIn("referenceId", annotations["s-unknown"])
                    if scenario == "version_mix":
                        self.assertFalse(comparison["result"]["mapping"]["provisionalElements"])
                        self.assertFalse(comparison["result"]["mapping"]["provisionalConnections"])
                    samples.append({"envelope": envelope, "feedback": result, "candidates": store.files["candidates/ref.json"], "context": {
                        "evaluationId": "evaluation", "referenceKey": "ref", "modelId": "s",
                        "submissionObjects": store.files["graphs/submission.json"]["result"]["graph"]["nodes"],
                        "referenceObjects": store.files["graphs/ref.json"]["result"]["graph"]["nodes"]}})
        from test_contract import CHECK, ROOT
        checked = subprocess.run(["node", "-e", CHECK], input=json.dumps(samples), cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

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
