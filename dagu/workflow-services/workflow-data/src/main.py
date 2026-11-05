#!/usr/bin/env python3
"""Materialize frozen evaluation inputs or collect graph artifacts."""
import json
import os
import sys

from workflow_io import collect_graphs, decode_bundle, prepare, workspace


def main() -> int:
    try:
        store = workspace()
        action = os.environ.get("WORKFLOW_ACTION", "prepare")
        if action == "prepare":
            result = prepare(store, decode_bundle(os.environ["EVALUATION_INPUT_GZIP_BASE64"]))
        elif action == "collect":
            result = collect_graphs(store)
        else:
            raise ValueError("unknown workflow data action")
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
        return 0
    except (ValueError, KeyError, OSError, EOFError) as error:
        print(f"[workflow-data] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
