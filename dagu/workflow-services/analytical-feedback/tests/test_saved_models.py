"""Retain observations from repository snapshots without fabricating matcher evidence."""

import json
from pathlib import Path
import sys
import unittest

from test_analysis import SERVICES, build, case
from analysis_contract import validate_analysis
from artifacts import _key
from correspondence_state import build_provisional_state
from initial_structure import evaluate_containment_relations
from test_facts import with_facts
from test_identity_feedback import with_identity_facts

sys.path.insert(0, str(SERVICES / "graph-parser/src"))
from parser import parse_model

ROOT = Path(__file__).resolve().parents[4]
VERSIONS = ROOT / "api/src/modeling_api/db/migrations/versions"


def snapshot_graph(relative, key):
    model = json.loads((VERSIONS / relative).read_text(encoding="utf-8"))["model"]
    version = model["version"]
    pin = version["workspaceLanguages"][0]
    releases = json.loads((VERSIONS / "v01_connection_rule_aliases/releases.json").read_text(encoding="utf-8"))
    declaration = next(item for item in releases["languages"] if item["languageId"] == pin["languageId"])
    # This is a repository-declaration fixture, not the unavailable frozen evaluation chain.
    data = json.loads((VERSIONS / "v01_connection_rule_aliases/serm_v2.json").read_text(encoding="utf-8"))
    language = {"languageId": declaration["languageId"], "versionId": declaration["initialVersionId"], "data": data}
    return parse_model({"source": {"key": key, "role": "submission" if key == "submission" else "reference",
                        "label": model["name"], "modelId": model["id"], "versionId": version["id"]},
                        "model": version["data"], "languages": [language]})["graph"], language


class SavedSnapshotTests(unittest.TestCase):
    def test_saved_models_use_actual_correspondences_and_matcher_facts(self):
        reference, language = snapshot_graph("v12_laboratory_management/sample_solution.json", "ref")
        for relative in ("v12_laboratory_management/sample_solution.json", "v14_laboratory_structure_models/m03.json",
                         "v14_laboratory_structure_models/m05.json", "v14_laboratory_structure_models/m06b.json"):
            with self.subTest(snapshot=relative):
                submission, _ = snapshot_graph(relative, "submission")
                store = case(reference["nodes"], submission["nodes"], reference["edges"], submission["edges"], pairs=[])
                store.bundle["languages"] = [language]
                # Complete generic compatibility candidates, with no embedding
                # calculation, synonym service, or threshold changes.
                candidates = {"synonymMatrix": [
                    {"referenceElementId": left["id"], "referenceLabel": left["label"], "matches": [
                        {"submissionElementId": right["id"], "submissionLabel": right["label"]}
                        for right in submission["nodes"] if right["kind"] == "modelElement" and _key(left) == _key(right)]}
                    for left in reference["nodes"] if left["kind"] == "modelElement"]}
                state = build_provisional_state(store.indices, candidates)
                store.comparison["mapping"]["provisionalElements"] = state["proposals"]
                store.comparison["provisionalContainmentEvidence"] = evaluate_containment_relations(store.indices, state["proposals"])["relations"]
                with_facts(store)
                report = build(store)
                validate_analysis(report, store)
                equal_labels = [fact for item in report["annotations"] for fact in item["facts"] if fact["code"] == "label.equal"]
                self.assertTrue(any(fact["status"] == "satisfied" for fact in equal_labels))
                self.assertEqual(report, build(store))
                with_identity_facts(store)
                report = build(store)
                validate_analysis(report, store)
                self.assertEqual(report["contractVersion"], "1.3")
                self.assertTrue(any(item.get("identity", {}).get("status") == "uniquely_supported" for item in report["annotations"]))

    def test_baseline_m03_m05_m06b_preserve_ids_and_unchecked_observations(self):
        reference, language = snapshot_graph("v12_laboratory_management/sample_solution.json", "ref")
        for name, relative in (("baseline", "v12_laboratory_management/sample_solution.json"),
                               ("M03", "v14_laboratory_structure_models/m03.json"),
                               ("M05", "v14_laboratory_structure_models/m05.json"),
                               ("M06b", "v14_laboratory_structure_models/m06b.json")):
            with self.subTest(snapshot=name):
                submission, _ = snapshot_graph(relative, "submission")
                store = case(reference["nodes"], submission["nodes"], reference["edges"], submission["edges"], pairs=[])
                store.bundle["languages"] = [language]
                report = build(store)
                validate_analysis(report, store)
                self.assertEqual({item["target"]["id"] for item in report["annotations"]},
                                 {item["id"] for item in submission["nodes"]})
                self.assertFalse(any(item["status"] == "different" or "referenceId" in item for item in report["annotations"]))
                self.assertEqual(len(report["referenceHints"]), len(reference["nodes"]))
                for item in report["annotations"]:
                    original = store.indices["student"].nodes[item["target"]["id"]]
                    if original["kind"] == "connection":
                        self.assertEqual(item["connection"]["submission"]["directed"], original["directed"])
                        self.assertEqual(item["connection"]["submission"]["type"], original["type"])
                        self.assertEqual(item["checks"]["endpoints"], "unresolved")
                    self.assertEqual(item["checks"]["owner"], "not_evaluated")
                self.assertEqual(report, build(store))


if __name__ == "__main__":
    unittest.main()
