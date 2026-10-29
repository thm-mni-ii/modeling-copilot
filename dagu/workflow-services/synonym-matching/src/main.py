#!/usr/bin/env python3
"""Local/Dagu boundary: JSON in, one JSON result line out, diagnostics on stderr."""
import argparse
import json
import os
import sys
from pathlib import Path
from synonym_matching import MatchingEngine

SERVICE = "synonym-matching"


def read_input(path=None):
    if path:
        raw = Path(path).read_text()
    else:
        raw = os.environ.get("TEMPLATE_INPUT")
        if raw is None:
            raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("TEMPLATE_INPUT or stdin JSON is required")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("a JSON object is required")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="JSON file (otherwise TEMPLATE_INPUT or stdin)")
    args = parser.parse_args()
    try:
        import jsonschema
        payload = read_input(args.input)
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/input.schema.json").read_text())
        jsonschema.validate(payload, schema)
        data = payload["input"]
        engine = MatchingEngine(data.get("config"))
        result = engine.match(data["referenceModel"]["elements"], data["studentModel"]["elements"], threshold=data.get("threshold"))
        count = sum(len(row["matches"]) for row in result["synonymMatrix"])
        print(json.dumps({"status": "ok", "capability": SERVICE, "step": payload.get("step", SERVICE),
                          "summary": f"{count} candidate pairs", "result": result}, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as error:
        # Optional model/download failures must not produce a successful partial matrix.
        print(f"[{SERVICE}] {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
