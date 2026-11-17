#!/usr/bin/env python3
"""Publish the validated analytical recognition overview without recalculation."""

import os
from pathlib import Path
import sys

from analysis_contract import SCHEMA, content_hash, read_analysis, read_comparison, require
import workflow_io
from workflow_io import Workspace, workspace, write_output

SERVICE = "feedback-generation"


def run(store: Workspace, reference_key: str, analysis_path: str | None = None) -> dict:
    require(analysis_path is not None,
            "analytical feedback path is required; regenerate legacy analysis instead of counting provisional mappings")
    comparison = read_comparison(store, reference_key)
    analysis = read_analysis(store, analysis_path, reference_key, comparison)
    require(analysis["schema"] == SCHEMA and "recognition" in analysis,
            "legacy analysis has no authoritative identity recognition; regenerate analytical feedback")
    resources = {"src/main.py": Path(__file__), "src/workflow_io.py": Path(workflow_io.__file__),
                 "src/analysis_contract.py": Path(sys.modules["analysis_contract"].__file__)}
    report = {
        "schema": "feedback-report/v3", "status": "partial", "assessmentAvailable": False,
        "evaluationId": comparison["evaluationId"], "inputHash": comparison["inputHash"],
        "pair": comparison["pair"], "comparisonHash": comparison["comparisonHash"],
        "analysisHash": analysis["analysisHash"], "analysisPath": analysis_path,
        "recognition": analysis["recognition"],
        "producer": {"service": SERVICE, "version": "2.2.1",
                     "resourceHash": content_hash({name: path.read_text(encoding="utf-8") for name, path in resources.items()})},
    }
    report["feedbackHash"] = content_hash(report)
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "aggregate",
            "capability": SERVICE, "summary": "Identitätserkennung; keine Korrektheitsquote oder Note", "result": report}


def main() -> int:
    try:
        store = workspace()
        write_output(run(store, os.environ.get("REFERENCE_KEY"), os.environ.get("ANALYSIS_INPUT_PATH")))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
