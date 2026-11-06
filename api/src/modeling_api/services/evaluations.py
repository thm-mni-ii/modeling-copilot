"""Evaluation persistence and authorization; Dagu holds volatile run state."""

import base64
import gzip
import json
import shlex
from asyncio import gather
from typing import Any
from uuid import UUID, uuid4

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, insert, list_page, to_api, utcnow
from modeling_api.services import dagu, languages
from modeling_api.services.models import get_version, ensure_task_questionnaire_completed
from modeling_api.services.tasks import ensure_release_reference, get_sample_solution


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
    if raw in {"aborted", "canceled"}:
        return "cancelled"
    if raw in {"pending", "not_started"}:
        return "queued"
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
            "resultSummary": raw.get("resultSummary") or raw.get("summary") or raw.get("output") or raw.get("error"),
            "result": None,
            "_subRuns": raw.get("subRuns", []),
        })
    return result


def _structured_output(value: object) -> dict[str, Any]:
    """Read the final JSON line emitted by a workflow-service without naming a capability."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
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


async def _evaluation_input(evaluation_id: str, task: Document, submission: Document, references: list[Document]) -> tuple[Document, list[Document]]:
    """Freeze complete platform-independent inputs, including language dependencies."""
    cache: dict[tuple[str, str], Document] = {}
    models, descriptors = [], []

    async def visit(reference: Document, resolved: set[tuple[str, str]]) -> None:
        key = (reference["languageId"], reference["versionId"])
        if key in resolved:
            return
        if len(resolved) >= languages.MAX_LANGUAGE_REFS:
            raise ApiError(422, "TOO_MANY_REFERENCES", "Too many included language versions for evaluation.")
        if key not in cache:
            cache[key] = await languages.get_version(UUID(key[0]), UUID(key[1]))
        resolved.add(key)
        for included in cache[key].get("includedLanguageVersions", []):
            await visit(included, resolved)

    for index, snapshot in enumerate([submission, *references]):
        resolved: set[tuple[str, str]] = set()
        for reference in snapshot["workspaceLanguages"]:
            await visit(reference, resolved)
        source = {
            "key": "submission" if index == 0 else f"reference_{index}",
            "role": "submission" if index == 0 else "reference",
            "label": "Aktuelles Modell" if index == 0 else f"Musterlösung {index}",
            "modelId": snapshot["modelId"], "versionId": snapshot["versionId"],
        }
        models.append({"source": source, "snapshot": snapshot})
        descriptors.append(source)
    task_languages: set[tuple[str, str]] = set()
    for reference in task.get("workspaceLanguages", []):
        await visit(reference, task_languages)
    definitions = [{"languageId": key[0], "versionId": key[1], "data": version["data"],
                    "includedLanguageVersions": version.get("includedLanguageVersions", [])}
                   for key, version in sorted(cache.items())]
    return {"schemaVersion": 1, "schema": "evaluation-input/v1", "evaluationId": evaluation_id,
            "task": task, "models": models, "languages": definitions}, descriptors


async def start(model_id: UUID, user: User) -> Document:
    model = await db.models.find_one({"_id": str(model_id), "ownerId": user.id})
    if model is None or not model.get("taskVersion"):
        raise not_found()
    await ensure_task_questionnaire_completed(model_id)
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
        "modelId": str(model_id), "versionId": str(version_id),
        "data": submission["data"], "workspaceLanguages": submission["workspaceLanguages"],
        "taskVersion": submission.get("taskVersion"), "taskEditSnapshot": submission.get("taskEditSnapshot"),
    }
    references = await gather(*(
        get_sample_solution(UUID(task_ref["taskId"]), UUID(task_ref["versionId"]), UUID(reference["modelId"]), UUID(reference["versionId"]), user)
        for reference in task_version["data"].get("sampleSolutions", [])
    ))
    reference_snapshots = [{"modelId": version["modelId"], "versionId": version["id"],
                            "data": version["data"], "workspaceLanguages": version["workspaceLanguages"]}
                           for version in references]
    evaluation_id = str(uuid4())
    task_snapshot = {**task_ref, "data": task_version["data"], "workspaceLanguages": task_version.get("workspaceLanguages", [])}
    bundle, parser_models = await _evaluation_input(evaluation_id, task_snapshot, snapshot, reference_snapshots)
    encoded = base64.b64encode(gzip.compress(json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"), mtime=0)).decode("ascii")
    if len(encoded) > 100_000:
        raise ApiError(422, "EVALUATION_INPUT_TOO_LARGE", "The complete evaluation snapshot exceeds the workflow launch limit.")
    # One complete input object; subsequent jobs only receive workspace/model keys.
    params = {"evaluation_id": evaluation_id, "evaluation_input": encoded,
              "parser_models": [{"key": source["key"]} for source in parser_models],
              "model_count": len(parser_models), "reference_count": len(reference_snapshots)}
    dag_run_id = await dagu.start_workflow(workflow_name, params)
    evaluation = await insert(db.evaluations, {
        "_id": evaluation_id,
        "ownerId": user.id, "taskId": task_ref["taskId"], "taskVersionId": task_ref["versionId"],
        "modelId": str(model_id), "modelVersionId": str(version_id),
        "task": task_ref, "submission": {"modelId": str(model_id), "versionId": str(version_id)},
        "submissionSnapshot": snapshot, "parserModels": parser_models, "dagName": workflow_name, "dagRunId": dag_run_id,
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


async def _model_run_steps(evaluation: Document, parent: Document, children: list[Document]) -> list[Document]:
    step_name, artifact_path, capability, label = {
        "parse_models": ("parse_model", "parser-result.json", "graph-parser", "Graph"),
        "extract_labels": ("extract_labels", "labels-result.json", "model-label-extraction", "Bezeichnungen"),
    }[parent["id"]]
    by_key = {}
    for child in children:
        try:
            params = json.loads(child.get("params") or "{}")
        except (json.JSONDecodeError, TypeError):
            # Dagu 2.16 stores child params as shell-style assignments even
            # though its OpenAPI schema calls the field JSON. Parse as data.
            try:
                params = dict(item.split("=", 1) for item in shlex.split(child.get("params") or "") if "=" in item)
            except (ValueError, TypeError):
                continue
        if isinstance(params, dict) and params.get("MODEL_KEY"):
            by_key[params["MODEL_KEY"]] = child

    async def read(source: Document) -> Document:
        step = {"id": f"{step_name}_{source['key']}", "label": f"{label}: {source['label']}",
                "description": f"{label} für Modell {source['modelId']}, Version {source['versionId']}",
                "status": "pending", "resultSummary": None, "result": None, "_modelRun": True}
        child = by_key.get(source["key"])
        if child is None:
            if parent["status"] in {"failed", "cancelled"}:
                step.update(status=parent["status"], resultSummary="Modellschritt wurde nicht gestartet.")
            return step
        try:
            child_id = child["dagRunId"]
            run = _dag_run(await dagu.get_sub_run(evaluation["dagName"], evaluation["dagRunId"], child_id))
            step["status"] = _state(run.get("statusLabel") or run.get("status"))
            errors = [node.get("error") for node in run.get("nodes", []) if node.get("error")]
            step["resultSummary"] = "\n".join(errors) or None
            if step["status"] == "succeeded":
                try:
                    step["resultSummary"] = await dagu.get_sub_run_artifact(
                        evaluation["dagName"], evaluation["dagRunId"], child_id, path=artifact_path, capability=capability,
                    )
                    return step
                except ApiError:
                    # Earlier runs predate artifact persistence and only have logs.
                    pass
            if step["status"] in {"succeeded", "failed", "cancelled"}:
                try:
                    output = await dagu.get_step_log(evaluation["dagName"], evaluation["dagRunId"], step_name, sub_run_id=child_id)
                    if not output and step["status"] == "failed":
                        output = await dagu.get_step_log(evaluation["dagName"], evaluation["dagRunId"], step_name, sub_run_id=child_id, stream="stderr")
                    step["resultSummary"] = output or step["resultSummary"]
                except ApiError:
                    # Job creation failures can have no step log at all.
                    pass
        except ApiError:
            step.update(status="unknown", resultSummary="Modellschritt konnte nicht geladen werden.")
        return step

    return list(await gather(*(read(source) for source in evaluation["parserModels"])))


async def detail(evaluation_id: UUID, user: User) -> Document:
    evaluation = await db.evaluations.find_one({"_id": str(evaluation_id), "ownerId": user.id})
    if evaluation is None:
        raise not_found()
    run = _dag_run(await dagu.get_run(evaluation["dagName"], evaluation["dagRunId"]))
    state = _state(run.get("statusLabel") or run.get("status") or run.get("state"))
    raw_steps = _run_steps(run, evaluation["workflow"])
    # Expand the fan-out into one visible intermediate result per model. The
    # existing sidebar already renders each step's structured JSON result.
    expanded = []
    for step in raw_steps:
        children = step.pop("_subRuns", [])
        if step["id"] in {"parse_models", "extract_labels"} and evaluation.get("parserModels"):
            expanded.extend(await _model_run_steps(evaluation, step, children))
        else:
            expanded.append(step)
    raw_steps = expanded
    completed_steps = [step for step in raw_steps if step["status"] in {"succeeded", "failed"}]
    logs = await gather(*(
        dagu.get_step_log(evaluation["dagName"], evaluation["dagRunId"], step["id"])
        for step in completed_steps if not step.get("_modelRun")
    ), return_exceptions=True)
    for step, log in zip([step for step in completed_steps if not step.get("_modelRun")], logs, strict=True):
        if isinstance(log, str) and log:
            step["resultSummary"] = log
    steps = _enrich_step_output(raw_steps)
    for step in steps:
        step.pop("_modelRun", None)
    await db.evaluations.update_one({"_id": evaluation["_id"]}, {"$set": {"state": state, "lastObservedAt": utcnow()}})
    result = _public_evaluation(evaluation, detail=True)
    result["state"] = state
    result["steps"] = steps
    final_result = (run.get("result") or run.get("output")) if state == "succeeded" else None
    if state == "succeeded" and not isinstance(final_result, dict) and steps:
        # The final workflow step is the generic producer of the overall result.
        final_result = next((step["result"] for step in reversed(steps) if isinstance(step.get("result"), dict)), None)
    result["finalResult"] = final_result if isinstance(final_result, dict) else None
    return result
