#!/usr/bin/env python3
"""Demo aggregation of explicitly named result files, without fixed predecessors."""
import os
import sys

from workflow_io import Workspace, read_input, workspace, write_output

SERVICE = "feedback-generation"


def run(payload: dict, store: Workspace | None = None) -> dict:
    paths = payload.get("input", {})
    if not isinstance(paths, dict) or not all(isinstance(path, str) for path in paths.values()):
        raise ValueError("input must map result names to relative JSON file paths")
    if paths and store is None:
        raise ValueError("reading result paths requires WORKFLOW_EVALUATION_ID")
    services = {name: store.read(path) for name, path in paths.items()}
    result = {"status": "not_implemented", "assessmentAvailable": False, "services": services}
    if store is not None:
        result.update(evaluationId=store.evaluation_id, inputSnapshot="inputs/evaluation-input.json")
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "demo",
            "capability": SERVICE, "summary": "Demo-Ergebnisse zusammengeführt; keine fachliche Bewertung", "result": result}


def main() -> int:
    try:
        store = workspace() if os.environ.get("WORKFLOW_EVALUATION_ID") else None
        if store is not None:
            store.snapshot()
        write_output(run(read_input(), store))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
