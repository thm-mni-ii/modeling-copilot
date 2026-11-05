"""Versioned file contract shared by short-lived workflow services.

The only external input is the complete frozen evaluation bundle. All later
inputs are immutable JSON files in one evaluation directory on workflow storage.
This module has no dependency on the Modeling API, MongoDB, Dagu or the network.
"""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

VERSION = 1
INPUT_SCHEMA = "evaluation-input/v1"
RESULT_SCHEMA = "workflow-result/v1"


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("invalid evaluation/model identifier")
    return value


class Workspace:
    def __init__(self, evaluation_id: str, root: str | Path | None = None):
        self.evaluation_id = identifier(evaluation_id)
        self.root = (Path(root or os.environ.get("WORKFLOW_DATA_ROOT", "/work/evaluations")) / self.evaluation_id).resolve()

    def path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("artifact path leaves the evaluation workspace")
        return path

    def read(self, relative: str) -> dict:
        value = json.loads(self.path(relative).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"artifact must be a JSON object: {relative}")
        return value

    def write(self, relative: str, value: dict) -> dict:
        """Atomic, immutable publication; identical retries are idempotent."""
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        try:
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                if path.read_bytes() != encoded:
                    raise ValueError(f"artifact already exists with different content: {relative}")
        finally:
            temporary_path.unlink(missing_ok=True)
        return self.reference(relative)

    def reference(self, relative: str) -> dict:
        data = self.path(relative).read_bytes()
        return {"evaluationId": self.evaluation_id, "path": relative,
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    def resolve(self, reference: dict) -> dict:
        if reference.get("evaluationId") != self.evaluation_id:
            raise ValueError("cross-evaluation artifact reference")
        actual = self.reference(reference["path"])
        if actual["sha256"] != reference.get("sha256") or actual["bytes"] != reference.get("bytes"):
            raise ValueError("artifact checksum mismatch")
        return self.read(reference["path"])


def workspace() -> Workspace:
    return Workspace(os.environ["WORKFLOW_EVALUATION_ID"])


def envelope(capability: str, summary: str, result: dict, *, mode: str = "data") -> dict:
    return {"schemaVersion": VERSION, "schema": RESULT_SCHEMA, "status": "ok",
            "capability": capability, "mode": mode, "summary": summary, "result": result}


def prepare(store: Workspace, bundle: dict) -> dict:
    if bundle.get("schemaVersion") != VERSION or bundle.get("schema") != INPUT_SCHEMA:
        raise ValueError("unsupported evaluation input schema")
    if bundle.get("evaluationId") != store.evaluation_id:
        raise ValueError("input evaluation ID does not match the workspace")
    if not isinstance(bundle.get("task"), dict):
        raise ValueError("complete task snapshot is required")
    models, definitions = bundle.get("models"), bundle.get("languages")
    if not isinstance(models, list) or not models or not isinstance(definitions, list):
        raise ValueError("complete models and language definitions are required")
    languages = {}
    for definition in definitions:
        key = (definition["languageId"], definition["versionId"])
        if key in languages or not isinstance(definition.get("data"), dict):
            raise ValueError("duplicate or incomplete language version")
        languages[key] = definition
    keys = [identifier(model["source"]["key"]) for model in models]
    if len(keys) != len(set(keys)) or keys.count("submission") != 1:
        raise ValueError("model keys must be unique and include one submission")
    requests = []
    # Validate all inputs before publishing any request.
    for model in models:
        source, snapshot = model["source"], model["snapshot"]
        if not all(isinstance(source.get(key), str) and source[key] for key in ("key", "role", "label", "modelId", "versionId")):
            raise ValueError("complete model source metadata is required")
        if source.get("role") != ("submission" if source["key"] == "submission" else "reference"):
            raise ValueError("model role does not match its key")
        data = snapshot.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("xml"), str) or not data["xml"].strip():
            raise ValueError("model snapshot must contain complete XML")
        resolved = {}

        def visit(reference):
            key = (reference["languageId"], reference["versionId"])
            if key in resolved:
                return
            if key not in languages:
                raise ValueError("a referenced language version is missing from the frozen input")
            resolved[key] = languages[key]
            for included in languages[key].get("includedLanguageVersions", []):
                visit(included)

        for reference in snapshot.get("workspaceLanguages", []):
            visit(reference)
        requests.append({"mode": "parse", "step": "parse_model", "source": source,
                         "input": {"model": data, "languages": list(resolved.values())}})
    snapshot_ref = store.write("inputs/evaluation-input.json", bundle)
    entries = []
    for request in requests:
        ref = store.write(f"inputs/models/{request['source']['key']}.json", request)
        entries.append({"source": request["source"], "input": ref})
    manifest = {"schemaVersion": VERSION, "evaluationId": store.evaluation_id,
                "inputSnapshot": snapshot_ref, "models": entries}
    manifest_ref = store.write("inputs/manifest.json", manifest)
    return envelope("workflow-input", f"{len(entries)} vollständige Modell-Snapshots bereitgestellt",
                    {"evaluationId": store.evaluation_id, "manifest": manifest_ref, "snapshot": bundle})


def parser_request(store: Workspace, model_key: str) -> dict:
    key = identifier(model_key)
    manifest = store.read("inputs/manifest.json")
    entry = next((item for item in manifest["models"] if item["source"]["key"] == key), None)
    if entry is None:
        raise ValueError("model key does not belong to this evaluation")
    return store.resolve(entry["input"])


def save_graph(store: Workspace, model_key: str, result: dict) -> dict:
    source = parser_request(store, model_key)["source"]
    if result.get("mode") != "parse" or result.get("result", {}).get("source") != source:
        raise ValueError("parser result does not match its input model")
    store.write(f"graphs/{identifier(model_key)}.json", result)
    return result


def collect_graphs(store: Workspace) -> dict:
    manifest = store.read("inputs/manifest.json")
    entries, graphs = [], {}
    for item in manifest["models"]:
        source = item["source"]
        ref = store.reference(f"graphs/{source['key']}.json")
        parsed = store.resolve(ref)
        if parsed.get("result", {}).get("source") != source:
            raise ValueError("graph source differs from its input snapshot")
        graph = parsed["result"]["graph"]
        entries.append({"source": source, "artifact": ref, "nodeCount": len(graph["nodes"]),
                        "edgeCount": len(graph["edges"]), "complete": graph["complete"]})
        graphs[source["key"]] = parsed["result"]
    index = {"schemaVersion": VERSION, "evaluationId": store.evaluation_id, "models": entries}
    ref = store.write("graphs/index.json", index)
    return envelope("graph-collection", f"{len(entries)} Graphen für nachfolgende Dienste bereitgestellt",
                    {"evaluationId": store.evaluation_id, "index": ref, "models": entries, "graphs": graphs})


def graph_pairs(store: Workspace) -> list[tuple[dict, dict, dict, dict]]:
    index = store.read("graphs/index.json")
    submission = next(item for item in index["models"] if item["source"]["role"] == "submission")
    submission_graph = store.resolve(submission["artifact"])["result"]["graph"]
    return [(submission, reference, submission_graph, store.resolve(reference["artifact"])["result"]["graph"])
            for reference in index["models"] if reference["source"]["role"] == "reference"]


def run_capability(capability: str, store: Workspace) -> dict:
    """Exercise real file dependencies while keeping algorithms explicit stubs."""
    if capability == "feedback-generation":
        service_results = {name: load_results(store, name) for name in
                           ("synonym-matching", "one-to-one-graph-matching", "minimal-matching-unit")}
        comparisons = []
        for _, reference, _, _ in graph_pairs(store):
            key = reference["source"]["key"]
            results = {name: values[key] for name, values in service_results.items()}
            comparisons.append({"comparisonId": key, "reference": reference["source"], "services": results,
                                "assessmentAvailable": False})
        report = {"schemaVersion": VERSION, "evaluationId": store.evaluation_id,
                  "inputSnapshot": store.reference("inputs/evaluation-input.json"),
                  "graphs": store.read("graphs/index.json"), "comparisons": comparisons,
                  "assessmentAvailable": False, "status": "not_implemented"}
        store.write("evaluation-result.json", report)
        return envelope(capability, "Ergebnisse zusammengeführt; Bewertungsalgorithmen sind noch Platzhalter", report, mode="demo")
    if capability not in ("synonym-matching", "one-to-one-graph-matching", "minimal-matching-unit"):
        raise ValueError("unknown workflow capability")
    comparisons = []
    synonyms = load_results(store, "synonym-matching") if capability != "synonym-matching" else {}
    synonym_index = store.read("results/synonym-matching/index.json") if capability != "synonym-matching" else {}
    for submission, reference, sub_graph, ref_graph in graph_pairs(store):
        key = reference["source"]["key"]
        inputs = {"submissionGraph": submission["artifact"], "referenceGraph": reference["artifact"]}
        if capability != "synonym-matching":
            synonym_ref = {item["comparisonId"]: item["artifact"] for item in synonym_index["comparisons"]}[key]
            synonym = synonyms[key]
            if synonym["comparisonId"] != key or synonym["evaluationId"] != store.evaluation_id:
                raise ValueError("synonym result belongs to another comparison")
            inputs["synonymMatrix"] = synonym_ref
        result = {"schemaVersion": VERSION, "evaluationId": store.evaluation_id, "comparisonId": key,
                  "capability": capability, "capabilityVersion": "0.2.0", "inputs": inputs,
                  "status": "not_implemented" if sub_graph["complete"] and ref_graph["complete"] else "blocked",
                  "reason": "Algorithmus noch nicht implementiert" if sub_graph["complete"] and ref_graph["complete"] else "Parsergraph ist unvollständig",
                  "observed": {"submissionNodes": len(sub_graph["nodes"]), "referenceNodes": len(ref_graph["nodes"])} }
        ref = store.write(f"results/{capability}/{key}.json", result)
        comparisons.append({"comparisonId": key, "artifact": ref, "result": result})
    store.write(f"results/{capability}/index.json", {"schemaVersion": VERSION, "evaluationId": store.evaluation_id,
                "capability": capability, "comparisons": [{"comparisonId": item["comparisonId"], "artifact": item["artifact"]} for item in comparisons]})
    return envelope(capability, f"Daten für {len(comparisons)} Modellpaare gelesen; Algorithmus ist noch Platzhalter",
                    {"evaluationId": store.evaluation_id, "comparisons": comparisons}, mode="demo")


def load_results(store: Workspace, capability: str) -> dict:
    index = store.read(f"results/{capability}/index.json")
    if index.get("schemaVersion") != VERSION or index.get("evaluationId") != store.evaluation_id or index.get("capability") != capability:
        raise ValueError("result index does not match the requested service/evaluation")
    results = {}
    for entry in index["comparisons"]:
        key = entry["comparisonId"]
        result = store.resolve(entry["artifact"])
        if key in results or result.get("schemaVersion") != VERSION or result.get("evaluationId") != store.evaluation_id or result.get("comparisonId") != key or result.get("capability") != capability:
            raise ValueError("result does not match its comparison/service/evaluation")
        results[key] = result
    return results


def execute(capability: str) -> int:
    try:
        print(json.dumps(run_capability(capability, workspace()), ensure_ascii=False, separators=(",", ":"), allow_nan=False))
        return 0
    except (ValueError, KeyError, OSError) as error:
        import sys
        print(f"[{capability}] {error}", file=sys.stderr)
        return 1


def decode_bundle(encoded: str) -> dict:
    value = json.loads(gzip.decompress(base64.b64decode(encoded, validate=True)).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("evaluation input must be a JSON object")
    return value
