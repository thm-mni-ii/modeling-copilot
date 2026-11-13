#!/usr/bin/env python3
"""Build and publish analytical feedback from a frozen, validated artifact set."""

import os
import sys

from artifacts import read_artifacts
import comparison_report
from workflow_io import Workspace, workspace, write_output
import analysis
from analysis_contract import SCHEMA, analysis_key, analysis_path, content_hash, require, validate_analysis

SERVICE = "analytical-feedback"


def run(store: Workspace, reference_key: str) -> dict:
    bundle, graphs, indices, candidates = read_artifacts(store, reference_key)
    comparison = comparison_report.read_comparison(store, reference_key)
    expected = {"graphHashes": {side: graph["graphHash"] for side, graph in graphs.items()},
                "inventoryHashes": candidates["inventoryHashes"], "candidateHash": candidates["candidateHash"],
                "languageResources": {side: graph["languageResources"] for side, graph in graphs.items()}}
    require(all(comparison.get(key) == value for key, value in expected.items()),
            "comparison does not match its source artifact chain")
    thresholds = bundle["comparisonConfig"].get("graphMatching", {}).get("minimumSimilarity", {})
    require(comparison["semanticRefinement"]["minimumSimilarity"] == thresholds,
            "comparison thresholds differ from frozen configuration")
    compact = comparison_report.build_report(comparison)["result"]
    report = analysis.build(store, bundle, indices, candidates, comparison, compact)
    require(report["schema"] == SCHEMA, "invalid analysis schema")
    report["analysisKey"] = analysis_key(report)
    report["analysisHash"] = content_hash(report)
    validate_analysis(report, store)
    path = analysis_path(report)
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "aggregate",
            "capability": SERVICE, "summary": "Vorläufige elementbezogene Hinweise",
            "analysisPath": path, "analysisKey": report["analysisKey"],
            "metadata": {"analysisPath": path, "analysisKey": report["analysisKey"]}, "result": report}


def main() -> int:
    try:
        store = workspace()
        result = run(store, os.environ.get("REFERENCE_KEY"))
        store.write(result["analysisPath"], result)
        write_output(result)
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
