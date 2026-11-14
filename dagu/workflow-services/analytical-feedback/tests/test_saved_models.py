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
    def test_saved_models_preserve_ids_positive_facts_and_historical_metadata(self):
        reference, language = snapshot_graph("v12_laboratory_management/sample_solution.json", "ref")
        for name, expected in (("baseline", 58), ("M02", 56), ("M04", 50), ("M08", 55)):
            with self.subTest(snapshot=name):
                relative = "v12_laboratory_management/sample_solution.json" if name == "baseline" else f"v14_laboratory_structure_models/{name.lower()}.json"
                submission, _ = snapshot_graph(relative, "submission")
                store = case(reference["nodes"], submission["nodes"], reference["edges"], submission["edges"], pairs=[])
                store.bundle["languages"] = [language]
                with_identity_facts(store)
                report = build(store)
                validate_analysis(report, store)
                self.assertEqual(report["recognition"]["overall"]["recognized"], expected)
                self.assertEqual(report["recognition"]["overall"]["expected"], 58)
                self.assertTrue(report["recognition"]["buckets"])
                self.assertTrue(all(row["expected"] > 0 for row in report["recognition"]["buckets"]))
                self.assertEqual(sum(row["expected"] for row in report["recognition"]["buckets"]), 58)
                self.assertEqual({item["target"]["id"] for item in report["annotations"]}, {item["id"] for item in submission["nodes"]})
                self.assertTrue(any(fact["code"] == "label.equal" and fact["status"] == "satisfied" for item in report["annotations"] for fact in item["facts"]))
                self.assertEqual(report, build(store))


if __name__ == "__main__":
    unittest.main()
