#!/usr/bin/env python3
"""Run generated benchmark cases through the deployed workflow services, step by step like the DAG.

Runs inside a pod that mounts the shared workflow volume (e.g. the workflow-data deployment) and
reaches the `workflow-services` Kubernetes service. Standard library only. Each case uses a
temporary `replay-<uuid>-<n>` workspace, which is removed afterwards.

Usage: python run.py CASES_DIR LANGUAGES_JSON OUT_DIR [--only PREFIX] [--keep]

`--keep` stores each workspace under OUT_DIR/workspaces/<evaluationId>, so `local_run.py` can rerun the matcher,
analysis and feedback on exactly the same inputs without the cluster.
"""

import base64
import gzip
import json
import os
import shutil
import sys
import urllib.request
import uuid
from pathlib import Path

HOST = "http://workflow-services"
ROOT = Path(os.environ.get("WORKFLOW_DATA_ROOT", "/work/evaluations"))
PORTS = {"data": 30081, "parser": 30082, "labels": 30083, "synonyms": 30084, "matcher": 30085, "analysis": 30086, "feedback": 30087}


def post(service, fields):
    boundary = uuid.uuid4().hex
    body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode() + str(value).encode() + b"\r\n"
                    for name, value in fields.items()) + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(f"{HOST}:{PORTS[service]}/run", data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{service}: {error.read().decode('utf-8', 'replace')[-600:]}") from None


def bundle(case, reference, languages, evaluation_id):
    def snapshot(model_id, version_id, xml, workspace):
        return {"modelId": model_id, "versionId": version_id, "workspaceLanguages": workspace,
                "data": {"format": "maxgraph-xml", "version": 1, "xml": xml}}
    workspace = reference["reference"]["workspaceLanguages"]
    wanted = {item["versionId"] for item in workspace}
    submission_workspace = case.get("submissionWorkspace", workspace)
    wanted |= {item["versionId"] for item in submission_workspace}
    return {
        "schemaVersion": 1, "schema": "evaluation-input/v1", "evaluationId": evaluation_id,
        "task": reference["task"],
        "models": [
            {"source": {"key": "submission", "role": "submission", "label": "Benchmark", "modelId": f"benchmark-{case['case']}",
                        "versionId": f"benchmark-{case['reference']}-{case['case']}"},
             "snapshot": snapshot(f"benchmark-{case['case']}", f"benchmark-{case['reference']}-{case['case']}", case["xml"], submission_workspace)},
            {"source": {"key": "reference_1", "role": "reference", "label": "Musterlösung 1", "modelId": reference["reference"]["modelId"],
                        "versionId": reference["reference"]["versionId"]},
             "snapshot": snapshot(reference["reference"]["modelId"], reference["reference"]["versionId"], reference["xml"], workspace)},
        ],
        "languages": [language for language in languages if language["versionId"] in wanted],
        "comparisonConfig": {}, "feedbackRequest": {"types": ["recognition", "hints"], "context": {}},
    }


def run_case(case, reference, languages, evaluation_id):
    encoded = base64.b64encode(gzip.compress(json.dumps(bundle(case, reference, languages, evaluation_id),
                                                        ensure_ascii=False).encode("utf-8"), mtime=0)).decode("ascii")
    common = {"WORKFLOW_EVALUATION_ID": evaluation_id}
    post("data", {**common, "EVALUATION_INPUT_GZIP_BASE64": encoded, "TEXT_EVIDENCE": ""})
    for key in ("submission", "reference_1"):
        post("parser", {**common, "MODEL_KEY": key, "WORKFLOW_OUTPUT_PATH": f"graphs/{key}.json"})
        post("labels", {**common, "MODEL_KEY": key, "WORKFLOW_INPUT_PATH": f"graphs/{key}.json", "WORKFLOW_OUTPUT_PATH": f"labels/{key}.json"})
    pair = {**common, "REFERENCE_KEY": "reference_1"}
    post("synonyms", {**pair, "WORKFLOW_OUTPUT_PATH": "candidates/reference_1.json"})
    comparison = post("matcher", {**pair, "WORKFLOW_OUTPUT_PATH": "comparisons/reference_1.json", "GRAPH_MATCHING_DIAGNOSTICS": "1"})["result"]
    analysis = post("analysis", pair)
    feedback = post("feedback", {**pair, "ANALYSIS_INPUT_PATH": analysis["analysisPath"], "WORKFLOW_OUTPUT_PATH": "feedback/reference_1.json"})["result"]
    return collect(ROOT / evaluation_id, comparison, feedback)


def collect(workspace, comparison, feedback):
    """The compact benchmark result of one evaluated workspace."""
    candidates = json.loads((workspace / "candidates" / "reference_1.json").read_text(encoding="utf-8"))["result"]
    # Text scores of the true pairs (same cell ID), to tell text failures from structural ones.
    true_scores = {row["referenceElementId"]: match.get("scores") for row in candidates["synonymMatrix"] for match in row["matches"]
                   if match["submissionElementId"] == row["referenceElementId"]}
    graphs = {key: json.loads((workspace / "graphs" / f"{key}.json").read_text(encoding="utf-8"))["result"]["graph"]
              for key in ("submission", "reference_1")}
    identity = comparison["diagnostics"]["identityEvidence"]["pairs"]
    return {
        "nodes": {key: {node["id"]: {"kind": node["kind"], "type": node.get("type"), "role": node.get("comparisonRole"), "label": node.get("label")}
                        for node in graph["nodes"]} for key, graph in graphs.items()},
        "candidatePairs": len(comparison["diagnostics"].get("candidatePairs", [])),
        "mapping": [{key: row.get(key) for key in ("referenceId", "studentId", "reason", "round")}
                    for field in ("provisionalElements", "provisionalConnections") for row in comparison["mapping"][field]],
        "identity": [{"referenceId": row["referenceId"], "studentId": row["studentId"], "status": row["status"], "zone": row.get("zone"),
                      "anchors": sorted({item["method"] for item in row["criteria"] if item["role"] == "identity_anchor"}),
                      "text": next(({"tier": item.get("tier"), "result": item["result"], "scores": item.get("scores"), "veto": item.get("veto")}
                                    for item in row["criteria"] if item["method"] == "text_similarity"), None)}
                     for row in identity if row["status"] != "unresolved" or any(item["method"] == "text_similarity" and item["result"] == "satisfied" for item in row["criteria"])],
        "pairDecisions": comparison["pairDecisions"],
        "hints": comparison["hints"]["items"],
        "learnerHints": next((entry["hints"] for entry in feedback["feedback"] if entry["type"] == "hints"), []),
        "recognition": next(entry["recognition"] for entry in feedback["feedback"] if entry["type"] == "recognition"),
        "decisionRounds": comparison.get("decisionRounds"),
        "trueScores": true_scores,
    }


def main():
    cases_dir, languages_path, out_dir = (Path(item) for item in sys.argv[1:4])
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    languages = json.loads(languages_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    batch = str(uuid.uuid4())
    files = sorted(path for path in cases_dir.glob("*__*.json") if path.name.startswith(only))
    for index, path in enumerate(files):
        case = json.loads(path.read_text(encoding="utf-8"))
        reference = json.loads((cases_dir / f"{case['reference']}.reference.json").read_text(encoding="utf-8"))
        evaluation_id = f"replay-{batch}-{index}"
        try:
            result = {"status": "ok", **run_case(case, reference, languages, evaluation_id)}
        except Exception as error:  # noqa: BLE001 - one failing case must not stop the benchmark
            result = {"status": "error", "error": str(error)[-1500:]}
        finally:
            if "--keep" in sys.argv and (ROOT / evaluation_id).exists():
                shutil.copytree(ROOT / evaluation_id, out_dir / "workspaces" / evaluation_id, dirs_exist_ok=True)
            shutil.rmtree(ROOT / evaluation_id, ignore_errors=True)
        (out_dir / path.name).write_text(json.dumps({"reference": case["reference"], "case": case["case"], "workspace": evaluation_id, **result}, ensure_ascii=False), encoding="utf-8")
        print(index + 1, len(files), path.stem, result["status"], flush=True)


if __name__ == "__main__":
    main()
