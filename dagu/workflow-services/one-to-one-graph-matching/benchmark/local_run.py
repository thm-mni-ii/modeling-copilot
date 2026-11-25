#!/usr/bin/env python3
"""Rerun matcher, analytical feedback and feedback generation from the repository sources on kept workspaces.

Graphs, inventories and candidates come from a cluster run with `run.py --keep`; only the services after
synonym matching run locally. That makes matcher changes measurable in minutes and on identical inputs.

Usage: python local_run.py CLUSTER_RESULTS_DIR OUT_DIR [--only PREFIX] [--workers N] [--matcher SRC_DIR]

`--matcher` runs another matcher source tree (e.g. copied from the running pod) to check the tooling.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVICES = HERE.parents[1]
sys.path.insert(0, str(HERE))
from run import collect  # noqa: E402

PATHS = {
    "matcher": [SERVICES / "one-to-one-graph-matching/src", SERVICES, SERVICES / "synonym-matching/src/synonym_matching"],
    "analysis": [SERVICES / "analytical-feedback/src", SERVICES, SERVICES / "one-to-one-graph-matching/src", SERVICES / "synonym-matching/src/synonym_matching"],
    "feedback": [SERVICES / "feedback-generation/src", SERVICES, SERVICES / "analytical-feedback/src"],
}
MAINS = {"matcher": SERVICES / "one-to-one-graph-matching/src/main.py", "analysis": SERVICES / "analytical-feedback/src/main.py",
         "feedback": SERVICES / "feedback-generation/src/main.py"}


def service(name, root, evaluation_id, **env):
    variables = {**os.environ, "PYTHONPATH": os.pathsep.join(str(path) for path in PATHS[name]), "PYTHONIOENCODING": "utf-8",
                 "WORKFLOW_DATA_ROOT": str(root), "WORKFLOW_EVALUATION_ID": evaluation_id, "REFERENCE_KEY": "reference_1", **env}
    done = subprocess.run([sys.executable, str(MAINS[name])], env=variables, capture_output=True, text=True, encoding="utf-8")
    if done.returncode:
        raise RuntimeError(f"{name}: {done.stderr[-800:]}")
    return json.loads(done.stdout)


def run_one(result_path, out_dir):
    result = json.loads(result_path.read_text(encoding="utf-8"))
    source = result_path.parent / "workspaces" / result.get("workspace", result_path.stem)
    if not source.exists():
        source = result_path.parent / "workspaces" / result_path.stem
    record = {"reference": result["reference"], "case": result["case"]}
    if result["status"] != "ok" or not source.exists():
        record.update(status="error", error=result.get("error", "workspace missing"))
    else:
        bundle = json.loads((source / "inputs" / "evaluation-input.json").read_text(encoding="utf-8"))
        evaluation_id = bundle.get("result", bundle)["evaluationId"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / evaluation_id
            shutil.copytree(source, work, ignore=shutil.ignore_patterns("comparisons", "analysis", "feedback", "signals"))
            try:
                comparison = service("matcher", root, evaluation_id, WORKFLOW_OUTPUT_PATH="comparisons/reference_1.json",
                                     GRAPH_MATCHING_DIAGNOSTICS="1")["result"]
                analysis = service("analysis", root, evaluation_id)
                feedback = service("feedback", root, evaluation_id, ANALYSIS_INPUT_PATH=analysis["analysisPath"],
                                   WORKFLOW_OUTPUT_PATH="feedback/reference_1.json")["result"]
                record.update(status="ok", **collect(work, comparison, feedback))
            except Exception as error:  # noqa: BLE001 - one failing case must not stop the benchmark
                record.update(status="error", error=str(error)[-1500:])
    (out_dir / result_path.name).write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return result_path.stem, record["status"]


def main():
    source, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    if "--matcher" in sys.argv:
        matcher = Path(sys.argv[sys.argv.index("--matcher") + 1]).resolve()
        PATHS["matcher"][0] = matcher
        PATHS["analysis"][2] = matcher
        MAINS["matcher"] = matcher / "main.py"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in source.glob("*__*.json") if path.name.startswith(only))
    with ThreadPoolExecutor(workers) as pool:
        for stem, status in pool.map(lambda path: run_one(path, out_dir), files):
            if status != "ok":
                print(stem, status, flush=True)
    print(f"{len(files)} cases -> {out_dir}")


if __name__ == "__main__":
    main()
