#!/usr/bin/env python3
"""Extract original cell IDs and labels from a normalized model graph."""
import argparse
import os
from pathlib import Path
import re
import sys

from workflow_io import Workspace, identifier, read_input, workspace, write_output

SERVICE = "model-label-extraction"
# Only formatting tags supported by the editor; other angle brackets are text.
FORMATTING_TAG = re.compile(r"</?(?:b|strong|i|em|u|br|div)\s*/?>", re.IGNORECASE)


def run(payload: dict, store: Workspace | None = None) -> dict:
    if (payload.get("schema") != "workflow-result/v1" or type(payload.get("schemaVersion")) is not int
            or payload["schemaVersion"] != 1
            or payload.get("status") != "ok"):
        raise ValueError("a successful workflow-result/v1 is required")
    data = payload.get("result")
    if not isinstance(data, dict):
        raise ValueError("result must be an object")
    graph, source = data.get("graph"), data.get("source")
    if (not isinstance(graph, dict) or type(graph.get("schemaVersion")) is not int or graph["schemaVersion"] != 2
            or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list)):
        raise ValueError("result.graph must contain schemaVersion=2 and nodes/edges arrays")
    if not isinstance(source, dict) or not all(
        isinstance(source.get(key), str) and source[key] for key in ("key", "role", "label", "modelId", "versionId")
    ):
        raise ValueError("result.source needs complete model source metadata")
    identifier(source["key"])
    if source["role"] not in ("submission", "reference"):
        raise ValueError("source.role must be submission/reference")
    if store is not None:
        model = next((item for item in store.snapshot()["models"] if item["source"]["key"] == source["key"]), None)
        if model is None or model["source"] != source:
            raise ValueError("source does not match a model in this evaluation")

    elements, seen = [], set()
    for section, kinds in (("nodes", {"element", "connection"}), ("edges", {"connection", "contains", "endpoint"})):
        for cell in graph[section]:
            if not isinstance(cell, dict) or cell.get("kind") not in kinds:
                raise ValueError(f"invalid cell kind in graph.{section}")
            identity, label = cell.get("id"), cell.get("label")
            if not isinstance(identity, str) or not identity.strip() or identity in seen:
                raise ValueError("graph cells need unique non-empty IDs")
            seen.add(identity)
            if not isinstance(label, str):
                raise ValueError("graph cell labels must be strings")
            if cell["kind"] in ("contains", "endpoint"):
                continue
            if FORMATTING_TAG.sub("", label).strip():
                elements.append({"id": identity, "label": label})
    elements.sort(key=lambda element: element["id"])
    result = {"source": source, "elements": elements}
    if store is not None:
        result["evaluationId"] = store.evaluation_id
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok",
            "capability": SERVICE, "mode": "extract",
            "summary": f"{len(elements)} Modellbezeichnungen extrahiert", "result": result}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--input", type=Path, help="Read one request JSON file instead of env/stdin")
    cli.add_argument("--output", type=Path, help="Write result JSON to a file instead of stdout")
    args = cli.parse_args()
    try:
        store = workspace() if os.environ.get("WORKFLOW_EVALUATION_ID") else None
        if store is not None:
            store.snapshot()
        write_output(run(read_input(args.input), store), args.output)
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
