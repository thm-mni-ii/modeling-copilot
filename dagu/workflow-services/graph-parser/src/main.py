#!/usr/bin/env python3
"""JSON service boundary and file-based entry point for the graph parser."""
import argparse
import base64
import binascii
import gzip
import json
import math
import os
from pathlib import Path
import sys
import time

from parser import parse_model

SERVICE = "graph-parser"


def read_input(path: Path | None = None) -> dict:
    if path:
        raw = path.read_text(encoding="utf-8-sig")
    elif os.environ.get("WORKFLOW_EVALUATION_ID"):
        from workflow_io import parser_request, workspace
        return parser_request(workspace(), os.environ["MODEL_KEY"])
    elif "PARSER_REQUEST_GZIP_BASE64" in os.environ:
        try:
            raw = gzip.decompress(base64.b64decode(os.environ["PARSER_REQUEST_GZIP_BASE64"], validate=True)).decode("utf-8")
        except (ValueError, OSError, EOFError, binascii.Error) as error:
            raise ValueError("invalid compressed parser request") from error
    else:
        raw = os.environ.get("TEMPLATE_INPUT")
    if raw is None:
        raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("TEMPLATE_INPUT, stdin JSON or --input is required")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("a JSON object is required")
    return value


def run(payload: dict) -> dict:
    mode = payload.get("mode", "parse")
    step = payload.get("step", SERVICE)
    if mode not in ("parse", "demo") or not isinstance(step, str):
        raise ValueError("mode must be parse/demo and step must be a string")
    delay = payload.get("demoDelaySeconds", 0)
    if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay) or not 0 <= delay <= 30:
        raise ValueError("demoDelaySeconds must be a number between 0 and 30")
    if mode == "demo":
        time.sleep(delay)
        graph = {"schemaVersion": 1, "languages": [], "complete": True,
                 "nodes": [{"id": "n1", "type": "Entity", "label": "Kunde", "kind": "element", "language": None, "properties": {}}],
                 "edges": []}
        diagnostics = []
        summary = "Expliziter Demo-Modus: Dummy-Graph, kein Modell geparst"
    else:
        graph, diagnostics = parse_model(payload.get("input"))
        summary = f"Modell normalisiert: {len(graph['nodes'])} Knoten, {len(graph['edges'])} Kanten"
    result = {"graph": graph, "diagnostics": diagnostics}
    if "source" in payload:
        source = payload["source"]
        if not isinstance(source, dict) or not all(isinstance(value, str) for value in source.values()):
            raise ValueError("source must be an object with string values")
        result["source"] = source
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "capability": SERVICE, "step": step, "mode": mode,
            "summary": summary, "result": result}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--input", type=Path, help="Read one request JSON file instead of env/stdin")
    cli.add_argument("--output", type=Path, help="Write result JSON to a file instead of stdout")
    args = cli.parse_args()
    try:
        result = run(read_input(args.input))
        if os.environ.get("WORKFLOW_EVALUATION_ID") and args.input is None:
            from workflow_io import save_graph, workspace
            save_graph(workspace(), os.environ["MODEL_KEY"], result)
        if args.output:
            output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
            args.output.write_text(output, encoding="utf-8")
        else:
            # One complete JSON record per line survives Dagu log tailing.
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
