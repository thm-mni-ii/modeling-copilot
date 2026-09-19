#!/usr/bin/env python3
"""Stub service boundary for future minimal matching unit calculation."""
import json
import os
import sys
import time

SERVICE = "minimal-matching-unit"


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
    print(f"[{SERVICE}] dummy matching-unit calculation started", file=sys.stderr); time.sleep(delay)
    result = {"units": [{"id": "unit-1", "submissionNodes": ["n1"], "referenceNodes": ["n1"], "score": 0.75}]}
    print(json.dumps({"status": "ok", "capability": SERVICE, "step": payload.get("step", SERVICE), "summary": "Dummy-Minimal-Matching abgeschlossen", "result": result}))
    return 0


if __name__ == "__main__": sys.exit(main())
