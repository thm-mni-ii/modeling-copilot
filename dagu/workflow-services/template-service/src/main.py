#!/usr/bin/env python3
"""Minimal template entrypoint for a Dagu workflow-service container.

Contract:
- Input: a JSON object, read from the TEMPLATE_INPUT env var, or from stdin
  if that env var is not set.
- Output: a JSON object written to stdout on success.
- Logs: human-readable progress messages written to stderr.
- Exit code: 0 on success, non-zero on any failure.

This template intentionally contains no domain logic. It only demonstrates
the container contract that future workflow services should follow.
"""
import json
import os
import sys
import time


def read_input() -> dict:
    raw = os.environ.get("TEMPLATE_INPUT")
    if raw is None:
        raw = sys.stdin.read()
    if not raw or not raw.strip():
        raise ValueError("no input provided (set TEMPLATE_INPUT or pipe JSON via stdin)")
    return json.loads(raw)


def main() -> int:
    try:
        payload = read_input()
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[template-service] invalid input: {exc}", file=sys.stderr)
        return 1

    capability = os.environ.get("WORKFLOW_CAPABILITY", "template-service")
    step = str(payload.get("step", capability))
    try:
        delay_seconds = float(payload.get("demoDelaySeconds", os.environ.get("DEMO_DELAY_SECONDS", "0")))
    except (TypeError, ValueError):
        print("[template-service] demoDelaySeconds must be a number", file=sys.stderr)
        return 1
    if not 0 <= delay_seconds <= 30:
        print("[template-service] demoDelaySeconds must be between 0 and 30", file=sys.stderr)
        return 1

    print(f"[{capability}] executing {step} with input: {payload}", file=sys.stderr)
    if delay_seconds:
        time.sleep(delay_seconds)

    dummy_results = {
        "synonym-matching": ("12 mögliche Begriffszuordnungen gefunden", {"matches": [{"studentTerm": "Kunde", "referenceTerm": "Customer"}] * 12}),
        "graph-parser": ("Modell als Dummy-Graph verarbeitet", {"nodes": [{"id": "n1", "label": "Kunde"}], "edges": []}),
        "one-to-one-graph-matching": ("Dummy-1:1-Matching abgeschlossen", {"score": 0.8, "mapping": [{"submissionNode": "n1", "referenceNode": "n1"}]}),
        "minimal-matching-unit": ("Dummy-Minimal-Matching abgeschlossen", {"units": [{"id": "unit-1", "score": 0.75}]}),
        "feedback-generation": ("Dummy-Ergebnis: Modell wurde verarbeitet", {"score": 0.8, "feedback": ["Dummy-Feedback für den durchspielbaren Workflow."]}),
    }
    summary, result = dummy_results.get(capability, ("Template erfolgreich ausgeführt", {}))

    output = {
        "status": "ok",
        "capability": capability,
        "step": step,
        "summary": summary,
        "result": result,
        "echo": payload,
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
