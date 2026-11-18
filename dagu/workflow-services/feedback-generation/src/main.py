#!/usr/bin/env python3
"""Generate exactly the feedback types requested in the frozen evaluation input."""

import os
from pathlib import Path
import sys

from analysis_contract import SCHEMA, content_hash, read_analysis, read_comparison, require
import help_feedback
import workflow_io
from workflow_io import Workspace, workspace, write_output

SERVICE = "feedback-generation"
# Runs without a request keep the previous behavior: the recognition overview only.
DEFAULT_REQUEST = {"types": ["recognition"], "context": {}}


def recognition(analysis: dict, context: dict, store: Workspace, bundle: dict) -> dict:
    """Validated identity recognition of the analytical feedback, without recalculation."""
    return {"recognition": analysis["recognition"]}


def help_builder(kind: str):
    return lambda analysis, context, store, bundle: help_feedback.build(kind, analysis, context, store, bundle)


# Every builder returns one feedback entry; only the types named in the input are produced.
BUILDERS = {"recognition": recognition,
            **{kind: help_builder(kind) for kind in ("help.clarify", "help.check", "help.next_step", "help.example", "help.solution")},
            # Staff-only analysis view; the API never forwards it to learners.
            "help.catalog": lambda analysis, context, store, bundle: help_feedback.catalog(analysis, store, bundle)}


def feedback_request(bundle: dict) -> tuple[list[str], dict]:
    request = bundle.get("feedbackRequest", DEFAULT_REQUEST)
    require(isinstance(request, dict) and set(request) <= {"types", "context"},
            "feedbackRequest must be an object with types and context")
    types, context = request.get("types"), request.get("context", {})
    require(isinstance(types, list) and types and all(isinstance(kind, str) for kind in types)
            and len(set(types)) == len(types), "feedbackRequest.types must be a non-empty list of unique names")
    unknown = sorted(set(types) - BUILDERS.keys())
    require(not unknown, f"unsupported feedback types: {', '.join(unknown)}")
    require(isinstance(context, dict), "feedbackRequest.context must be an object")
    return types, context


def run(store: Workspace, reference_key: str, analysis_path: str | None = None) -> dict:
    require(analysis_path is not None,
            "analytical feedback path is required; regenerate legacy analysis instead of counting provisional mappings")
    bundle = store.snapshot()
    types, context = feedback_request(bundle)
    comparison = read_comparison(store, reference_key)
    analysis = read_analysis(store, analysis_path, reference_key, comparison)
    require(analysis["schema"] == SCHEMA and "recognition" in analysis,
            "legacy analysis has no authoritative identity recognition; regenerate analytical feedback")
    resources = {"src/main.py": Path(__file__), "src/workflow_io.py": Path(workflow_io.__file__),
                 "src/help_feedback.py": Path(help_feedback.__file__),
                 "src/analysis_contract.py": Path(sys.modules["analysis_contract"].__file__)}
    report = {
        "schema": "feedback-report/v4", "status": "partial", "assessmentAvailable": False,
        "evaluationId": comparison["evaluationId"], "inputHash": comparison["inputHash"],
        "pair": comparison["pair"], "comparisonHash": comparison["comparisonHash"],
        "analysisHash": analysis["analysisHash"], "analysisPath": analysis_path,
        "requested": types,
        "feedback": [{"type": kind, **BUILDERS[kind](analysis, context, store, bundle)} for kind in types],
        "producer": {"service": SERVICE, "version": "4.9.1",
                     "resourceHash": content_hash({name: path.read_text(encoding="utf-8") for name, path in resources.items()})},
    }
    report["feedbackHash"] = content_hash(report)
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "aggregate",
            "capability": SERVICE, "summary": f"Feedback: {', '.join(types)}; keine Korrektheitsquote oder Note", "result": report}


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
