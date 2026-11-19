"""Collect one authorized evaluation and its Dagu run tree into a ZIP archive."""

import base64
import gzip
import json
from pathlib import PurePosixPath
import shlex
from tempfile import SpooledTemporaryFile
from typing import BinaryIO
from urllib.parse import quote
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.services import dagu
from modeling_api.services.evaluations import _dag_run, _public_evaluation, _state, can_view_analysis


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n"


def _archive_path(path: str) -> str:
    normalized = PurePosixPath(path)
    if not path or normalized.is_absolute() or ".." in normalized.parts or "\\" in path or ":" in path:
        raise ApiError(503, "DAGU_INVALID_RESPONSE", "The evaluation service returned an invalid archive path.")
    return str(normalized)


async def create_archive(evaluation_id: UUID, user: User) -> BinaryIO:
    if not can_view_analysis(user):
        raise ApiError(403, "FORBIDDEN", "Run exports require administrator or moderator access.")
    evaluation = await db.evaluations.find_one({"_id": str(evaluation_id), "ownerId": user.id})
    if evaluation is None:
        raise not_found()
    name, run_id = evaluation["dagName"], evaluation["dagRunId"]
    root = _dag_run(await dagu.get_run(name, run_id))
    if _state(root.get("statusLabel") or root.get("status")) not in {"succeeded", "failed", "cancelled"}:
        raise ApiError(409, "EVALUATION_NOT_FINISHED", "Wait for the evaluation to finish before exporting it.")
    archive_file = SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b")
    missing = []
    try:
        with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("evaluation.json", _json(_public_evaluation(evaluation)))
            archive.writestr("inputs/submission.json", _json(evaluation["submissionSnapshot"]))
            # The run retains the exact launch snapshot, including reference models and languages.
            params = root.get("params") or ""
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    params = dict(item.split("=", 1) for item in shlex.split(params) if "=" in item)
            if isinstance(params, dict) and params.get("evaluation_input"):
                snapshot = json.loads(gzip.decompress(base64.b64decode(params["evaluation_input"], validate=True)))
                archive.writestr("inputs/launch-input.json", _json(snapshot))
            else:
                missing.append("inputs/launch-input.json")
            pending = [(None, root)]
            visited = set()
            base = f"/dag-runs/{quote(name, safe='')}/{quote(run_id, safe='')}"

            async def include_file(url, destination, **kwargs):
                content = await dagu._request("GET", url, raw=True, allow_missing=True, **kwargs)
                if content is None:
                    missing.append(destination)
                else:
                    archive.writestr(destination, content)

            while pending:
                child_id, run = pending.pop(0)
                identity = child_id or run_id
                if identity in visited:
                    continue
                visited.add(identity)
                prefix = "runs/root" if child_id is None else f"runs/subruns/{_archive_path(child_id)}"
                url = base if child_id is None else f"{base}/sub-dag-runs/{quote(child_id, safe='')}"
                archive.writestr(f"{prefix}/run.json", _json(run))
                outputs = await dagu._request("GET", f"{url}/outputs", allow_missing=True)
                if outputs is not None:
                    archive.writestr(f"{prefix}/outputs.json", _json(outputs))
                else:
                    missing.append(f"{prefix}/outputs.json")
                await include_file(f"{url}/log/download", f"{prefix}/logs/run.log")
                nodes = list(run.get("nodes", []))
                nodes.extend(run[key] for key in ("onInit", "onExit", "onSuccess", "onFailure", "onAbort", "onWait")
                             if isinstance(run.get(key), dict))
                for position, node in enumerate(nodes):
                    step = node.get("step") or {}
                    step_name = step.get("name") or step.get("id")
                    if step_name:
                        for stream in ("stdout", "stderr"):
                            await include_file(f"{url}/steps/{quote(step_name, safe='')}/log/download",
                                               f"{prefix}/logs/{position:03d}-{_archive_path(step_name)}-{stream}.log",
                                               params={"stream": stream})
                    for child in node.get("subRuns", []) + node.get("subRunsRepeated", []):
                        nested_id = child["dagRunId"]
                        if nested_id not in visited:
                            nested = _dag_run(await dagu.get_sub_run(name, run_id, nested_id))
                            pending.append((nested_id, nested))
                tree = await dagu._request("GET", f"{url}/artifacts", params={"recursive": True}, allow_missing=True)
                if tree is None:
                    missing.append(f"{prefix}/artifacts/")
                    continue
                entries = list(tree.get("items", []))
                while entries:
                    entry = entries.pop()
                    if entry["type"] == "directory":
                        entries.extend(entry.get("children", []))
                    elif entry["type"] == "file":
                        path = _archive_path(entry["path"])
                        await include_file(f"{url}/artifacts/download", f"{prefix}/artifacts/{path}", params={"path": entry["path"]})
            archive.writestr("manifest.json", _json({"schema": "evaluation-run-export/v1", "evaluationId": str(evaluation_id),
                "dagName": name, "dagRunId": run_id, "runCount": len(visited), "unavailableFiles": missing}))
        archive_file.seek(0)
        return archive_file
    except BaseException:
        archive_file.close()
        raise
