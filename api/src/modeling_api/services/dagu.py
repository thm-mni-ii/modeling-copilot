"""Small, server-only adapter for the Dagu HTTP API.

The adapter deliberately returns a stable application shape.  Dagu remains the
source of live run data; no Dagu token reaches a browser.
"""

import json
from asyncio import gather
from typing import Any

import httpx

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError


def _headers() -> dict[str, str]:
    if settings.dagu_api_key:
        return {"Authorization": f"Bearer {settings.dagu_api_key}"}
    return {}


async def _request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        async with httpx.AsyncClient(base_url=settings.dagu_base_url.rstrip("/"), timeout=settings.dagu_request_timeout_seconds) as client:
            response = await client.request(method, f"/api/v1{path}", headers=_headers(), **kwargs)
    except httpx.HTTPError as error:
        raise ApiError(503, "DAGU_UNAVAILABLE", "The evaluation service is currently unavailable.") from error
    if response.status_code in (401, 403):
        raise ApiError(503, "DAGU_UNAUTHORIZED", "The evaluation service rejected its credentials.")
    if response.status_code >= 400:
        raise ApiError(503, "DAGU_REQUEST_FAILED", "The evaluation workflow could not be queried.")
    return response.json() if response.content else {}


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "dags", "data"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    return []


def normalize_workflow(raw: dict[str, Any]) -> dict[str, Any]:
    # GET /dags returns an entry wrapper, while GET /dags/{name} puts the
    # complete definition below `dag`.
    definition = raw.get("dag") if isinstance(raw.get("dag"), dict) else raw
    labels = definition.get("labels") or definition.get("tags") or {}
    if isinstance(labels, list):
        labels = {
            key: value
            for item in labels
            for key, _, value in [str(item).partition("=")]
        }
    if not isinstance(labels, dict):
        labels = {}
    raw_steps = definition.get("steps") or []
    if isinstance(raw_steps, dict):
        raw_steps = [{"name": key, **(value if isinstance(value, dict) else {})} for key, value in raw_steps.items()]
    steps = []
    for step in raw_steps if isinstance(raw_steps, list) else []:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("name") or step.get("id") or "step")
        steps.append({"id": step_id, "label": str(step.get("label") or step.get("name") or step_id), "description": step.get("description"), "status": "pending"})
    name = str(definition.get("name") or definition.get("dagName") or definition.get("id") or "")
    return {"name": name, "description": definition.get("description"), "labels": labels, "steps": steps}


async def list_workflows() -> list[dict[str, Any]]:
    entries = _items(await _request("GET", "/dags"))
    names = [workflow["name"] for workflow in map(normalize_workflow, entries) if workflow["name"]]
    details = await gather(*(_request("GET", f"/dags/{name}") for name in names))
    return [workflow for workflow in map(normalize_workflow, details) if workflow["name"]]


async def start_workflow(name: str, params: dict[str, Any]) -> str:
    # Dagu exposes runtime params as scalar environment values. Preserve the
    # application's objects and arrays as JSON strings instead of relying on
    # Dagu's implicit string conversion.
    dagu_params = {
        key: json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (dict, list)) else value
        for key, value in params.items()
    }
    # Dagu's REST API expects `params` itself to be a JSON-encoded string,
    # rather than an object in the enclosing request body.
    payload = await _request(
        "POST",
        f"/dags/{name}/start",
        json={"params": json.dumps(dagu_params, ensure_ascii=False, separators=(",", ":"))},
    )
    run_id = payload.get("dagRunId") or payload.get("dag_run_id") or payload.get("runId")
    if not run_id:
        raise ApiError(503, "DAGU_INVALID_RESPONSE", "The evaluation service did not return a run ID.")
    return str(run_id)


async def get_run(name: str, run_id: str) -> dict[str, Any]:
    # Dagu's DAG-run resource contains the current status and per-step state.
    return await _request("GET", f"/dag-runs/{name}/{run_id}")


async def get_step_log(name: str, run_id: str, step_name: str) -> str:
    """Return the stdout emitted by one workflow step."""
    payload = await _request(
        "GET",
        f"/dag-runs/{name}/{run_id}/steps/{step_name}/log",
        params={"stream": "stdout", "tail": 100},
    )
    return str(payload.get("content") or "") if isinstance(payload, dict) else ""
