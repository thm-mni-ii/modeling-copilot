#!/usr/bin/env python3
"""JSON service boundary and file-based entry point for the graph parser."""
import argparse
import os
from pathlib import Path
import sys
from typing import Literal, NotRequired, TypedDict

from parser import Graph, LanguageVersion, parse_model, resolve_languages
from workflow_io import Workspace, identifier, read_input, workspace, write_output

SERVICE = "graph-parser"


class ModelSource(TypedDict):
    key: str
    role: Literal["submission", "reference"]
    label: str
    modelId: str
    versionId: str


class MaxGraphModel(TypedDict):
    xml: str
    format: NotRequired[Literal["maxgraph-xml", "maxgraph-model"]]
    version: NotRequired[Literal[1]]
    name: NotRequired[str]


class ParserInput(TypedDict):
    model: MaxGraphModel
    languages: list[LanguageVersion]


class ParserRequest(TypedDict, total=False):
    input: ParserInput
    source: NotRequired[ModelSource]
    mode: NotRequired[Literal["parse", "demo"]]


class ParserData(TypedDict):
    graph: Graph
    source: NotRequired[ModelSource]


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
    if mode == "demo":
        graph = {"schemaVersion": 2, "languages": [],
                 "nodes": [{"id": "n1", "type": "Entity", "label": "Kunde", "kind": "element", "language": None,
                            "definition": None, "definitionCandidates": [], "parentId": None, "properties": {}}],
                 "edges": []}
        summary = "Expliziter Demo-Modus: Dummy-Graph, kein Modell geparst"
    else:
        if "input" not in payload and store is not None:
            bundle = store.snapshot()
            key = identifier(os.environ.get("MODEL_KEY", "submission"))
            model = next((item for item in bundle["models"] if item["source"]["key"] == key), None)
            if model is None:
                raise ValueError(f"model key does not belong to this evaluation: {key}")
            payload = {**payload, "source": model["source"], "input": {
                "model": model["snapshot"]["data"],
                "languages": resolve_languages(bundle, model["snapshot"]["workspaceLanguages"]),
            }}
        graph = parse_model(payload.get("input"))
        summary = f"Modell normalisiert: {len(graph['nodes'])} Knoten, {len(graph['edges'])} Kanten"
    result: ParserData = {"graph": graph}
    if "source" in payload:
        source = payload["source"]
        if not isinstance(source, dict) or not all(isinstance(source.get(key), str) and source[key] for key in ("key", "role", "label", "modelId", "versionId")):
            raise ValueError("source needs complete model source metadata")
        identifier(source["key"])
        if source["role"] not in ("submission", "reference"):
            raise ValueError("source.role must be submission/reference")
        result["source"] = source
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
