#!/usr/bin/env python3
"""A plain JSON-in/JSON-out script with optional access to a frozen snapshot."""
import os
import sys

from workflow_io import read_input, workspace, write_output


def main() -> int:
    try:
        payload = read_input()
        result = {"echo": payload}
        if os.environ.get("WORKFLOW_EVALUATION_ID"):
            store = workspace()
            result.update(evaluationId=store.evaluation_id, modelCount=len(store.snapshot()["models"]))
        write_output({"status": "ok", "capability": "template-service",
                      "summary": "Template erfolgreich ausgeführt", "result": result})
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[template-service] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
