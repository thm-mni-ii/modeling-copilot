#!/usr/bin/env python3
"""Produce complete V1 semantic evidence for one submission/reference pair."""
import argparse
import os
from pathlib import Path
import sys

from workflow_io import workspace, write_output
from synonym_matching.provenance import SERVICE
from synonym_matching.workflow import read_request, run


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--input", type=Path, help="Read a standalone inventory pair JSON file")
    cli.add_argument("--output", type=Path, help="Write result JSON to a file instead of stdout")
    args = cli.parse_args()
    try:
        store = workspace() if os.environ.get("WORKFLOW_EVALUATION_ID") else None
        payload, bundle, reference_key = read_request(args.input, store)
        write_output(run(payload, bundle, reference_key), args.output)
        return 0
    except Exception as error:
        # Validation and required-method failures must never publish partial success.
        print(f"[{SERVICE}] {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
