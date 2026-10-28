"""Evaluation persistence and authorization; Dagu holds volatile run state."""

import json
from asyncio import gather
from typing import Any
from uuid import UUID

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, insert, list_page, to_api, utcnow
from modeling_api.services import dagu
from modeling_api.services.models import get_version
from modeling_api.services.tasks import ensure_release_reference


_EVALUATION_FIELDS = frozenset({
    "id", "ownerId", "task", "submission", "dagName", "dagRunId", "startedAt", "state", "workflow",
})
_EVALUATION_DETAIL_FIELDS = _EVALUATION_FIELDS | {"submissionSnapshot", "steps", "finalResult"}


def _public_evaluation(document: Document, *, detail: bool = False) -> Document:
    """Drop persistence-only fields before validating an evaluation response."""
    api_document = to_api(document) if "_id" in document else document
    fields = _EVALUATION_DETAIL_FIELDS if detail else _EVALUATION_FIELDS
    return {key: value for key, value in api_document.items() if key in fields}


def _state(value: object) -> str:
    raw = str(value or "unknown").lower()
    if raw in {"queued", "running", "succeeded", "failed", "cancelled"}:
        return raw
    if raw in {"success", "completed", "done"}:
        return "succeeded"
    if raw in {"error", "failed", "failure"}:
        return "failed"
    return "unknown"


def _dag_run(payload: Document) -> Document:
    """Dagu wraps the run returned by GET /dag-runs in `dagRunDetails`."""
    details = payload.get("dagRunDetails")
    return details if isinstance(details, dict) else payload


def _run_steps(run: dict[str, Any], workflow: dict[str, Any]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    raw_steps = run.get("steps") or run.get("nodes") or []
    if isinstance(raw_steps, dict):
        raw_steps = [{"name": name, **(value if isinstance(value, dict) else {})} for name, value in raw_steps.items()]
    for raw in raw_steps if isinstance(raw_steps, list) else []:
        if isinstance(raw, dict):
            definition = raw.get("step") if isinstance(raw.get("step"), dict) else {}
            name = raw.get("name") or raw.get("id") or definition.get("name")
            if name:
                by_name[str(name)] = raw
    result = []
    for definition in workflow.get("steps", []):
        raw = by_name.get(definition["id"], {})
        result.append({
            **definition,
            "status": _state(raw.get("statusLabel") or raw.get("status") or raw.get("state") or definition.get("status", "pending")),
            "resultSummary": raw.get("resultSummary") or raw.get("summary") or raw.get("output"),
            "result": None,
        })
    return result


def _structured_output(value: object) -> dict[str, Any]:
    """Read the final JSON line emitted by a workflow-service without naming a capability."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    for line in reversed(value.splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _enrich_step_output(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for step in steps:
        raw = step.get("resultSummary")
        output = _structured_output(raw)
        if output.get("summary"):
            step["resultSummary"] = str(output["summary"])
        if isinstance(output.get("result"), dict):
            step["result"] = output["result"]
        elif raw is not None and not isinstance(raw, str):
            step["resultSummary"] = json.dumps(raw, ensure_ascii=False)
    return steps


async def list_workflows() -> list[Document]:
    return await dagu.list_workflows()


async def start(model_id: UUID, user: User) -> Document:
    model = await db.models.find_one({"_id": str(model_id), "ownerId": user.id})
    if model is None or not model.get("taskVersion"):
        raise not_found()
    task_ref = model["taskVersion"]
    task_version = await ensure_release_reference(UUID(task_ref["taskId"]), UUID(task_ref["versionId"]), user)
    allowed = task_version.get("data", {}).get("evaluationWorkflows", [])
    if not allowed:
        raise ApiError(409, "WORKFLOW_NOT_ENABLED", "No evaluation workflow is enabled for the task.")
    workflow_name = allowed[0]
    version_id = model.get("latestVersionId")
    if not version_id:
        raise ApiError(409, "SUBMISSION_NOT_SAVED", "Save the submission before starting an evaluation.")
    submission = await get_version(model_id, UUID(version_id), user)
    workflow = next((item for item in await dagu.list_workflows() if item["name"] == workflow_name), None)
    if workflow is None:
        raise ApiError(409, "WORKFLOW_UNAVAILABLE", "The configured workflow is no longer available.")
    snapshot = {
        "data": submission["data"], "workspaceLanguages": submission["workspaceLanguages"],
        "taskVersion": submission.get("taskVersion"), "taskEditSnapshot": submission.get("taskEditSnapshot"),
    }
    params = {"task": task_version["data"], "submission_model": snapshot, "reference_solutions": task_version["data"].get("sampleSolutions", [])}
    dag_run_id = await dagu.start_workflow(workflow_name, params)
    evaluation = await insert(db.evaluations, {
        "ownerId": user.id, "taskId": task_ref["taskId"], "taskVersionId": task_ref["versionId"],
        "modelId": str(model_id), "modelVersionId": str(version_id),
        "task": task_ref, "submission": {"modelId": str(model_id), "versionId": str(version_id)},
        "submissionSnapshot": snapshot, "dagName": workflow_name, "dagRunId": dag_run_id,
        "startedAt": utcnow(), "state": "queued", "workflow": workflow,
    })
    return _public_evaluation(evaluation)


async def list_for_model(model_id: UUID, user: User, skip: int, limit: int) -> Document:
    page = await list_page(
        db.evaluations,
        {"modelId": str(model_id), "ownerId": user.id},
        skip,
        limit,
        omit=("submissionSnapshot",),
    )
    return {**page, "items": [_public_evaluation(item) for item in page["items"]]}


async def detail(evaluation_id: UUID, user: User) -> Document:
    evaluation = await db.evaluations.find_one({"_id": str(evaluation_id), "ownerId": user.id})
    if evaluation is None:
        raise not_found()
    run = _dag_run(await dagu.get_run(evaluation["dagName"], evaluation["dagRunId"]))
    state = _state(run.get("statusLabel") or run.get("status") or run.get("state"))
    raw_steps = _run_steps(run, evaluation["workflow"])
    completed_steps = [step for step in raw_steps if step["status"] in {"succeeded", "failed"}]
    logs = await gather(*(
        dagu.get_step_log(evaluation["dagName"], evaluation["dagRunId"], step["id"])
        for step in completed_steps
    ), return_exceptions=True)
    for step, log in zip(completed_steps, logs, strict=True):
        if isinstance(log, str) and log:
            step["resultSummary"] = log
    steps = _enrich_step_output(raw_steps)
    await db.evaluations.update_one({"_id": evaluation["_id"]}, {"$set": {"state": state, "lastObservedAt": utcnow()}})
    result = _public_evaluation(evaluation, detail=True)
    result["state"] = state
    result["steps"] = steps
    final_result = (run.get("result") or run.get("output")) if state == "succeeded" else None
    if state == "succeeded" and not isinstance(final_result, dict) and steps:
        # The final workflow step is the generic producer of the overall result.
        final_result = _structured_output(steps[-1].get("resultSummary")).get("result")
    result["finalResult"] = final_result if isinstance(final_result, dict) else None
    return result
