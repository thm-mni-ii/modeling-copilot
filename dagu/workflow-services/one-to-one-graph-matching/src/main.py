#!/usr/bin/env python3
"""Demo placeholder consuming a graph result without knowing its producer."""
import math
import os
import sys
import time

from workflow_io import Workspace, read_input, workspace, write_output

SERVICE = "one-to-one-graph-matching"


def run(payload: dict, store: Workspace | None = None) -> dict:
    delay = payload.get("demoDelaySeconds", 0)
    if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay) or not 0 <= delay <= 30:
        raise ValueError("demoDelaySeconds must be a number between 0 and 30")
    time.sleep(delay)
    data = payload.get("result", {})
    graph = data.get("graph") if isinstance(data, dict) else None
    if graph is None and payload.get("mode") != "demo":
        raise ValueError("a graph in result.graph is required; use mode=demo for a standalone placeholder")
    if graph is not None and (not isinstance(graph, dict) or type(graph.get("schemaVersion")) is not int or graph.get("schemaVersion") != 1
                              or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list)):
        raise ValueError("result.graph must contain schemaVersion=1 and nodes/edges arrays")
    result = {"status": "not_implemented",
              "assessmentAvailable": False, "mapping": []}
    if graph is not None:
        result["observed"] = {"nodeCount": len(graph["nodes"]), "edgeCount": len(graph["edges"])}
    if store is not None:
        result["evaluationId"] = store.evaluation_id
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "demo",
            "capability": SERVICE, "summary": "1:1-Graph-Matching: Algorithmus noch nicht implementiert", "result": result}


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
