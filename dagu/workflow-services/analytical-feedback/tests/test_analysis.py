"""Focused projection regressions; no matcher implementation or pipeline execution."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

SERVICES = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SERVICES / "analytical-feedback/src"), str(SERVICES / "one-to-one-graph-matching/src"), str(SERVICES)]

import analysis
from analysis_contract import analysis_key, content_hash, validate_analysis
from graph_index import GraphIndex


def node(identity, kind="modelElement", native_type="entity", **values):
    return {"id": identity, "kind": kind, "type": native_type, "comparisonGroup": None,
            "comparisonRole": "structural" if kind == "structuralElement" else "semantic",
            "language": {"languageId": "generic", "versionId": "1"}, "languageResolution": "resolved",
            "definition": None, **values}


def contains(child, parent, role="content"):
    return {"kind": "contains", "source": child, "target": parent, "role": role}


def endpoints(connection, source, target):
    return [{"kind": "endpoint", "source": source, "target": connection, "role": "source"},
            {"kind": "endpoint", "source": connection, "target": target, "role": "target"}]


class Store:
    def __init__(self, bundle, indices, comparison):
        self.bundle, self.indices, self.comparison = bundle, indices, comparison

    def snapshot(self):
        return self.bundle

    def read(self, path):
        if path.startswith("labels/"):
            return {"result": {"connectionTexts": []}}
        if path.startswith("comparisons/"):
            return {"result": self.comparison}
        index = self.indices["student" if path == "graphs/submission.json" else "reference"]
        return {"result": {"graph": {"nodes": list(index.nodes.values())}}}


def case(reference, submission=None, reference_edges=(), submission_edges=None, pairs=None, **evidence):
    submission = deepcopy(reference) if submission is None else submission
    submission_edges = deepcopy(reference_edges) if submission_edges is None else submission_edges
    indices = {side: GraphIndex({"schemaVersion": 1, "languages": [], "nodes": nodes, "edges": list(edges)})
               for side, nodes, edges in (("reference", reference, reference_edges), ("student", submission, submission_edges))}
    if pairs is None:
        pairs = [(item["id"], item["id"]) for item in reference if item["kind"] in ("modelElement", "connection")]
    mapping = {"provisionalElements": [], "provisionalConnections": []}
    for ref, sub in pairs:
        field = "provisionalConnections" if indices["reference"].nodes[ref]["kind"] == "connection" else "provisionalElements"
        mapping[field].append({"referenceId": ref, "studentId": sub, "reason": "unique_exact_label", "status": "provisional"})
    mapped = {ref for ref, _ in pairs}
    comparison = {"pair": {"studentKey": "submission", "referenceKey": "ref"}, "comparisonHash": "a" * 64,
                  "mapping": mapping, "semanticRefinement": {"candidateEvidence": []},
                  "unresolvedReferenceIds": sorted(item["id"] for item in reference if item["kind"] == "modelElement" and item["id"] not in mapped),
                  "unresolvedReferenceConnectionIds": sorted(item["id"] for item in reference if item["kind"] == "connection" and item["id"] not in mapped), **evidence}
    bundle = {"evaluationId": "evaluation", "comparisonConfig": {},
              "models": [{"source": {"key": "submission", "modelId": "model"}}],
              "languages": [{"languageId": "generic", "versionId": "1", "data": {"evaluation": {
                  "elementCategories": {"entity": "nodes", "property": "attributes"}}}}]}
    return Store(bundle, indices, comparison)


def build(store):
    report = analysis.build(store.bundle, store.indices, store.comparison)
    report["analysisKey"] = analysis_key(report)
    report["analysisHash"] = content_hash(report)
    return report


def rehash(report):
    report["analysisKey"] = analysis_key(report)
    report["analysisHash"] = content_hash({key: value for key, value in report.items() if key != "analysisHash"})


class CompatibilityTests(unittest.TestCase):
    def test_saved_v1_revisions_remain_readable(self):
        import json
        fixtures = json.loads((Path(__file__).parent / "fixtures/legacy-analysis.json").read_text())
        self.assertEqual([item["report"].get("contractVersion") for item in fixtures], [None, "1.1", "1.2", "1.3"])
        for item in fixtures:
            validate_analysis(item["report"])

    def test_legacy_comparisons_require_regeneration(self):
        with self.assertRaisesRegex(ValueError, "regeneration"):
            build(case([node("a")]))


if __name__ == "__main__":
    unittest.main()
