#!/usr/bin/env python3
"""Build an element inventory from one graph-result/v3 without reinterpreting it."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import workflow_io
from workflow_io import Workspace, identifier, read_input, workspace, write_output

SERVICE = "model-label-extraction"
# Same attribute-free tags as web/src/utils/htmlLabels.ts; all other text is literal.
FORMATTING_TAG = re.compile(r"</?(?P<tag>b|strong|i|em|u|br|div)\s*/?>", re.IGNORECASE)
GRAPH_HASH_FIELDS = ("source", "languageResources", "producer", "graph", "completeness", "diagnostics")


def content_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def label_text(label: object) -> tuple[str, str]:
    if label is None:
        return "", "missing"
    if not isinstance(label, str):
        return "", "unsupported"
    parts, position, block_boundary = [], 0, False

    def append_text(text: str) -> None:
        nonlocal block_boundary
        if not text:
            return
        if block_boundary and parts and not parts[-1].endswith("\n") and not text.startswith("\n"):
            parts.append("\n")
        parts.append(text)
        block_boundary = False

    for match in FORMATTING_TAG.finditer(label):
        append_text(label[position:match.start()])
        tag = match.group("tag").lower()
        if tag == "br":
            if block_boundary and parts and not parts[-1].endswith("\n"):
                parts.append("\n")
            parts.append("\n")
            block_boundary = False
        elif tag == "div":
            block_boundary = True
        position = match.end()
    append_text(label[position:])
    # XML decoding already happened in the parser. The editor displays stored
    # entity spellings literally, so HTML unescaping here would change content.
    text = "".join(parts)
    return text, "present" if text.strip() else "missing"


def run(payload: dict, store: Workspace | None = None) -> dict:
    if (payload.get("schema") != "workflow-result/v1" or type(payload.get("schemaVersion")) is not int
            or payload["schemaVersion"] != 1
            or payload.get("status") != "ok"):
        raise ValueError("a successful workflow-result/v1 is required")
    data = payload.get("result")
    if not isinstance(data, dict) or data.get("schema") != "graph-result/v3":
        raise ValueError("result must be a graph-result/v3 object")
    evaluation_id = identifier(data.get("evaluationId"))
    graph, source = data.get("graph"), data.get("source")
    if (not isinstance(graph, dict) or type(graph.get("schemaVersion")) is not int or graph["schemaVersion"] != 3
            or any(not isinstance(graph.get(key), list) for key in ("nodes", "edges", "languages"))):
        raise ValueError("result.graph must contain schemaVersion=3 and nodes/edges/languages arrays")
    if not isinstance(source, dict) or not all(
        isinstance(source.get(key), str) and source[key] for key in ("key", "role", "label", "modelId", "versionId")
    ):
        raise ValueError("result.source needs complete model source metadata")
    identifier(source["key"])
    if source["role"] != ("submission" if source["key"] == "submission" else "reference"):
        raise ValueError("source.role does not match its model key")
    if not isinstance(data.get("inputHash"), str) or not re.fullmatch(r"[0-9a-f]{64}", data["inputHash"]):
        raise ValueError("result.inputHash must be a SHA-256 hex digest")
    if not isinstance(data.get("producer"), dict) or not isinstance(data.get("languageResources"), list):
        raise ValueError("result needs producer and languageResources metadata")
    completeness, diagnostics = data.get("completeness"), data.get("diagnostics")
    if not isinstance(completeness, dict) or completeness.get("interpretation") not in ("complete", "partial"):
        raise ValueError("result.completeness.interpretation must be complete/partial")
    if not isinstance(diagnostics, list) or any(not isinstance(item, dict) for item in diagnostics):
        raise ValueError("result.diagnostics must be an array of objects")
    if data.get("graphHash") != content_hash({field: data[field] for field in GRAPH_HASH_FIELDS}):
        raise ValueError("graph hash does not match the graph-result/v3 content")
    if store is not None:
        bundle = store.snapshot()
        if evaluation_id != store.evaluation_id or data["inputHash"] != bundle["inputHash"]:
            raise ValueError("graph does not belong to the frozen evaluation input")
        models = [item for item in bundle["models"] if item["source"]["key"] == source["key"]]
        if len(models) != 1 or models[0]["source"] != source:
            raise ValueError("source does not match a model in this evaluation")
        for variable in ("WORKFLOW_INPUT_PATH", "WORKFLOW_OUTPUT_PATH"):
            relative = os.environ.get(variable)
            if relative is not None and store.path(relative).name != f"{source['key']}.json":
                raise ValueError(f"{variable} filename does not match source.key")

    elements, seen, seen_edges = [], set(), set()
    diagnostics = []
    completeness = deepcopy(completeness)
    for section in ("nodes", "edges"):
        for cell in graph[section]:
            if not isinstance(cell, dict):
                raise ValueError(f"invalid object in graph.{section}")
            if section == "edges" and cell.get("kind") not in ("contains", "endpoint"):
                raise ValueError(f"invalid cell kind in graph.{section}")
            if section == "edges":
                if any(key not in cell for key in ("source", "target", "role")):
                    raise ValueError("graph edges need source/target/role")
                edge_key = (cell["kind"], cell.get("source"), cell.get("target"), cell.get("role"))
                if any(value is not None and not isinstance(value, str) for value in edge_key):
                    raise ValueError("graph edge references and role must be strings or null")
                if cell["kind"] == "contains" and not all(cell.get(end) for end in ("source", "target")):
                    raise ValueError("contains edges need non-empty source and target IDs")
                if edge_key in seen_edges:
                    raise ValueError("graph edges need unique kind/source/target/role combinations")
                seen_edges.add(edge_key)
                continue
            if cell.get("kind") not in ("modelElement", "structuralElement", "connection", "connectionLabel", None):
                raise ValueError("invalid graph node kind")
            identity = cell.get("id")
            if not isinstance(identity, str) or not identity.strip() or identity in seen:
                raise ValueError("graph cells need unique non-empty IDs")
            seen.add(identity)
            if cell.get("comparisonRole") not in ("semantic", "structural", "unsupported"):
                raise ValueError("graph nodes need a comparisonRole")
            if (any(key not in cell for key in (
                    "type", "kind", "comparisonGroup", "comparisonRole", "label", "language",
                    "definition", "languageResolution"))
                    or cell.get("languageResolution") not in ("resolved", "ambiguous", "unresolved")
                    or (cell.get("kind") is not None and not isinstance(cell.get("kind"), str))
                    or (cell.get("comparisonGroup") is not None and not isinstance(cell.get("comparisonGroup"), str))
                    or ("definitionCandidates" in cell and not isinstance(cell["definitionCandidates"], list))
                    or ("properties" in cell and not isinstance(cell["properties"], dict))
                    or ("directed" in cell and cell["directed"] is not None and type(cell["directed"]) is not bool)):
                raise ValueError("graph nodes need valid V3 type, kind and language metadata")
            if cell["comparisonRole"] == "structural":
                continue
            text_language = cell.get("textLanguage")
            if text_language is not None and (not isinstance(text_language, str) or not text_language.strip()):
                raise ValueError("explicit node.textLanguage must be a non-empty string or null")
            label = cell.get("label")
            match_text, label_status = label_text(label)
            elements.append({"id": identity, "matchText": match_text,
                             "labelStatus": label_status, "textLanguage": text_language})
            if label_status == "unsupported":
                completeness["interpretation"] = "partial"
                diagnostics.append({"code": "UNSUPPORTED_LABEL_TEXT", "severity": "warning", "scope": "element",
                                    "message": "Label is not textual; its original value was retained.",
                                    "source": deepcopy(source), "elementIds": [identity], "sourceField": "label"})
    elements.sort(key=lambda element: element["id"])
    diagnostics.sort(key=lambda item: (item.get("code", ""), item.get("elementIds", []), content_hash(item)))
    resources = {"main.py": Path(__file__), "workflow_io.py": Path(workflow_io.__file__)}
    producer = {"service": SERVICE, "version": "0.1.1",
                "resourceHash": content_hash({name: path.read_text(encoding="utf-8") for name, path in resources.items()})}
    graph_path = os.environ.get("WORKFLOW_INPUT_PATH", f"graphs/{source['key']}.json")
    if store is not None:
        store.path(graph_path)
    result = {"schema": "element-inventory/v1", "evaluationId": evaluation_id, "source": deepcopy(source),
              "inputHash": data["inputHash"], "graphHash": data["graphHash"], "graphPath": graph_path,
              "producer": producer, "elements": elements,
              "completeness": completeness, "diagnostics": diagnostics}
    result["inventoryHash"] = content_hash(result)
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok",
            "capability": SERVICE, "mode": "extract",
            "summary": f"{len(elements)} Elementinstanzen inventarisiert", "result": result}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--input", type=Path, help="Read one request JSON file instead of env/stdin")
    cli.add_argument("--output", type=Path, help="Write result JSON to a file instead of stdout")
    args = cli.parse_args()
    try:
        store = workspace() if os.environ.get("WORKFLOW_EVALUATION_ID") else None
        if store is not None:
            store.snapshot()
        write_output(run(read_input(args.input), store), args.output)
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
