#!/usr/bin/env python3
"""JSON service boundary and file-based entry point for the graph parser."""
import argparse
import os
from pathlib import Path
import sys
from typing import Literal, TypedDict

from parser import Graph, content_hash, parse_model, resolve_languages
import workflow_io
from workflow_io import INPUT_SCHEMA, VERSION, Workspace, identifier, input_hash, read_input, workspace, write_output

SERVICE = "graph-parser"


class ModelSource(TypedDict):
    key: str
    role: Literal["submission", "reference"]
    label: str
    modelId: str
    versionId: str


class ParserRequest(TypedDict, total=False):
    # The same complete evaluation-input/v1 snapshot used by workspace readers.
    input: dict
    modelKey: str
    mode: Literal["parse", "demo"]


class ParserData(TypedDict):
    schema: Literal["graph-result/v3"]
    evaluationId: str
    source: ModelSource
    inputHash: str
    languageResources: list[dict]
    producer: dict
    graphHash: str
    graph: Graph
    completeness: dict
    diagnostics: list[dict]


class ParserResult(TypedDict):
    schemaVersion: Literal[1]
    schema: Literal["workflow-result/v1"]
    status: Literal["ok"]
    capability: Literal["graph-parser"]
    mode: Literal["parse", "demo"]
    summary: str
    result: ParserData


def run(payload: ParserRequest, store: Workspace | None = None) -> ParserResult:
    mode = payload.get("mode", "parse")
    if mode not in ("parse", "demo"):
        raise ValueError("mode must be parse/demo")
    if store is not None:
        if "input" in payload or "modelKey" in payload or mode == "demo":
            raise ValueError("workspace parsing uses only its frozen snapshot and MODEL_KEY")
        bundle = store.snapshot()
        key = identifier(os.environ.get("MODEL_KEY", "submission"))
    elif mode == "demo":
        source = {"key": "submission", "role": "submission", "label": "Demo", "modelId": "demo-model", "versionId": "demo-version"}
        bundle = {"schema": INPUT_SCHEMA, "schemaVersion": VERSION, "evaluationId": "demo",
                  "task": {"data": {}}, "models": [{"source": source, "snapshot": {"modelId": source["modelId"],
                  "versionId": source["versionId"], "workspaceLanguages": [], "data": {
                  "xml": '<GraphDataModel><root><Cell id="canvas"/><Cell id="modeling" parent="canvas"/>'
                         '<Cell id="n1" value="Demo" vertex="1" parent="modeling"/>'
                         '<Cell id="feedback" parent="canvas"/></root></GraphDataModel>'}}}],
                  "languages": [], "comparisonConfig": {}}
        bundle["inputHash"] = input_hash(bundle)
        key = "submission"
    else:
        bundle = payload.get("input")
        key = identifier(payload.get("modelKey", "submission"))
    if (not isinstance(bundle, dict) or bundle.get("schema") != INPUT_SCHEMA
            or type(bundle.get("schemaVersion")) is not int or bundle["schemaVersion"] != VERSION):
        raise ValueError("input must be the complete frozen evaluation-input/v1 snapshot")
    evaluation_id = identifier(bundle.get("evaluationId"))
    if bundle.get("inputHash") != input_hash(bundle):
        raise ValueError("input hash does not match the frozen snapshot")
    selected = [item for item in bundle["models"] if item["source"]["key"] == key]
    if len(selected) != 1:
        raise ValueError(f"model key must name exactly one model in this evaluation: {key}")
    model = selected[0]
    source = model["source"]
    if not isinstance(source, dict) or not all(isinstance(source.get(field), str) and source[field] for field in ("key", "role", "label", "modelId", "versionId")):
        raise ValueError("source needs complete model source metadata")
    if source["role"] != ("submission" if key == "submission" else "reference"):
        raise ValueError("source.role does not match its model key")
    if any(model["snapshot"].get(field) != source[field] for field in ("modelId", "versionId")):
        raise ValueError("model source does not match its snapshot version")
    if not isinstance(bundle.get("comparisonConfig"), dict):
        raise ValueError("comparisonConfig must be a JSON object")
    languages = resolve_languages(bundle, model["snapshot"]["workspaceLanguages"])
    parsed = parse_model({"model": model["snapshot"]["data"], "source": source,
                          "languages": languages})
    resources = {"parser.py": Path(__file__).with_name("parser.py"), "main.py": Path(__file__),
                 "workflow_io.py": Path(workflow_io.__file__)}
    producer = {"service": SERVICE, "version": "0.4.2",
                "resourceHash": content_hash({name: path.read_text(encoding="utf-8") for name, path in resources.items()})}
    result: ParserData = {"schema": "graph-result/v3", "evaluationId": evaluation_id, "source": source,
                          "inputHash": bundle["inputHash"], "producer": producer,
                          "languageResources": [{"languageId": language["languageId"], "versionId": language["versionId"],
                                                 "hash": content_hash(language["data"])} for language in languages], **parsed}
    result["graphHash"] = content_hash({field: result[field] for field in ("source", "languageResources", "producer", "graph", "completeness", "diagnostics")})
    graph = result["graph"]
    elements = sum(node["kind"] != "connection" for node in graph["nodes"])
    connections = sum(node["kind"] == "connection" for node in graph["nodes"])
    containments = sum(edge["kind"] == "contains" for edge in graph["edges"])
    endpoints = sum(edge["kind"] == "endpoint" for edge in graph["edges"])
    summary = (f"Modell normalisiert: {elements} Elementknoten (einschließlich verschachtelter Inhalte), "
               f"{connections} modellierte Verbindungen; "
               f"{containments} Zugehörigkeiten und {endpoints} technische Verbindungsanschlüsse")
    if mode == "demo":
        summary = "Expliziter Demo-Modus: Dummy-Graph, kein Nutzermodell geparst"
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok",
            "capability": SERVICE, "mode": mode, "summary": summary, "result": result}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--input", type=Path, help="Read one request JSON file instead of env/stdin")
    cli.add_argument("--output", type=Path, help="Write result JSON to a file instead of stdout")
    args = cli.parse_args()
    try:
        store = workspace() if os.environ.get("WORKFLOW_EVALUATION_ID") else None
        if store is not None:
            store.snapshot()
        result = run(read_input(args.input), store)
        write_output(result, args.output)
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
