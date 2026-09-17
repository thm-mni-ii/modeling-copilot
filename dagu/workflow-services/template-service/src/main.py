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

    print(f"[template-service] received input: {payload}", file=sys.stderr)

    output = {
        "status": "ok",
        "echo": payload,
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
