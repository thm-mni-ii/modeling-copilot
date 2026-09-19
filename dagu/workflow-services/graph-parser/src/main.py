#!/usr/bin/env python3
"""Stub service boundary for converting one model into a graph."""
import json
import os
import sys
import time

SERVICE = "graph-parser"


def read_input() -> dict:
    raw = os.environ.get("TEMPLATE_INPUT")
    if raw is None: raw = sys.stdin.read()
    if not raw.strip(): raise ValueError("TEMPLATE_INPUT or stdin JSON is required")
    value = json.loads(raw)
    if not isinstance(value, dict): raise ValueError("a JSON object is required")
    return value


def main() -> int:
    try:
        payload = read_input(); delay = float(payload.get("demoDelaySeconds", 0))
        if not 0 <= delay <= 30: raise ValueError("demoDelaySeconds must be between 0 and 30")
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr); return 1
    print(f"[{SERVICE}] dummy parser started", file=sys.stderr); time.sleep(delay)
    graph = {"nodes": [{"id": "n1", "label": "Kunde", "type": "Entity"}], "edges": []}
    print(json.dumps({"status": "ok", "capability": SERVICE, "step": payload.get("step", SERVICE), "summary": "Modell als Dummy-Graph verarbeitet", "result": {"graph": graph}}))
    return 0


if __name__ == "__main__": sys.exit(main())
