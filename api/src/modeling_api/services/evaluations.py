"""Evaluation persistence and authorization; Dagu holds volatile run state."""

import base64
import gzip
import hashlib
import json
import shlex
from asyncio import gather
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, insert, list_page, to_api, utcnow
from modeling_api.services import dagu, languages
from modeling_api.services.models import get_version, ensure_task_questionnaire_completed
from modeling_api.services.synonym_glossary import frozen_glossaries
from modeling_api.services.tasks import ensure_release_reference, get_sample_solution


_EVALUATION_FIELDS = frozenset({
    "id", "ownerId", "task", "submission", "dagName", "dagRunId", "startedAt", "state", "workflow", "parameters",
})
_EVALUATION_DETAIL_FIELDS = _EVALUATION_FIELDS | {"submissionSnapshot", "steps", "finalResult", "scorePercent"}


def can_view_analysis(user: User) -> bool:
    return user.is_admin or user.global_role == "MODERATOR" or "MODERATOR" in user.roles


def _public_evaluation(document: Document, *, detail: bool = False) -> Document:
    """Drop persistence-only fields before validating an evaluation response."""
    api_document = to_api(document) if "_id" in document else document
    fields = _EVALUATION_DETAIL_FIELDS if detail else _EVALUATION_FIELDS
    result = {key: value for key, value in api_document.items() if key in fields}
    result["feedbackTypes"] = (api_document.get("feedbackRequest") or {}).get("types", [])
    # Reuse final learner feedback in navigation without fetching every run from Dagu.
    stored = api_document.get("studentFeedback")
    result["feedback"] = _feedback_projection(api_document, stored) if stored is not None else None
    return result


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
    if not isinstance(payload, dict):
        raise ApiError(503, "DAGU_INVALID_RESPONSE", "The evaluation service did not return a run object.")
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
        # Optional glossary by-product: never part of a run's visible progress or result.
        if definition["id"] == "export_synonym_signals":
            continue
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
        if step["id"].startswith("generate_analytical_feedback") and output:
            if (output.get("schema") != "workflow-result/v1" or type(output.get("schemaVersion")) is not int
                    or output.get("schemaVersion") != 1
                    or output.get("status") != "ok" or output.get("capability") != "analytical-feedback"
                    or not isinstance(output.get("result"), dict)
                    or output["result"].get("schema") not in ("analysis-feedback/v1", "analysis-feedback/v2", "analysis-feedback/v3")):
                step["resultSummary"] = "Das analytische Ergebnis hat ein ungültiges Format."
                step["result"] = None
                continue
        if output.get("summary"):
            step["resultSummary"] = str(output["summary"])
        if isinstance(output.get("result"), dict):
            step["result"] = output["result"]
        elif output:
            step["result"] = output
        elif raw is not None and not isinstance(raw, str):
            step["resultSummary"] = json.dumps(raw, ensure_ascii=False)
    return steps


def recognition_of(report: Document) -> Any:
    """v4 lists the requested feedback types; v2/v3 carry the recognition directly."""
    if report.get("schema") != "feedback-report/v4":
        return report.get("recognition")
    entries = report.get("feedback")
    return next((entry.get("recognition") for entry in entries if isinstance(entry, dict) and entry.get("type") == "recognition"),
                None) if isinstance(entries, list) else None


HELP_TYPES = ("help.clarify", "help.check", "help.next_step", "help.example", "help.solution")
HINT_FIELDS = ("id", "submissionId", "submissionLabel", "suggestion", "sources", "relation", "note")
HINT_ACTIONS = ("shown", "accepted", "dismissed")


def public_hints_entry(entry: Document) -> Document:
    """Allowlisted learner hints; the reference text is only present while the frozen probe switch allows it."""
    # The reference ID stays server-side for glossary suggestions; `_feedback_projection` never returns it.
    return {"type": "hints", "hints": [_pick(item, (*HINT_FIELDS, "referenceId")) for item in entry.get("hints", [])
                                       if isinstance(item, dict) and isinstance(item.get("id"), str)]}


def _pick(value: Any, fields: tuple[str, ...]) -> Document:
    return {key: value[key] for key in fields if key in value} if isinstance(value, dict) else {}


def public_help_entry(entry: Document) -> Document:
    """Allowlisted help feedback; the service already omits sample-solution content that is not released."""
    result = {"type": entry["type"], "overview": _pick(entry.get("overview"), ("recognized", "expected", "percent", "evaluationStatus")),
              "notices": [notice for notice in entry.get("notices", []) if isinstance(notice, str)]}
    if isinstance(entry.get("referenced"), bool):
        result["referenced"] = entry["referenced"]
    if isinstance(entry.get("objects"), list):
        result["objects"] = [{**_pick(item, ("cellId", "label", "kind", "identity", "notEvaluated", "verdict")),
                              "checks": [_pick(check, ("area", "status", "certainty", "messageCode", "text"))
                                         for check in item.get("checks", []) if isinstance(check, dict)],
                              # Per-object completeness (help.clarify), the released sample-solution element (help.solution)
                              # and the anonymous structure pattern (help.example).
                              **{key: item[key] for key in ("score", "example", "pattern") if isinstance(item.get(key), dict)}}
                             for item in entry["objects"] if isinstance(item, dict)]
    # help.check: the same aggregate recognition learners already get for the completion check.
    if isinstance(entry.get("recognition"), dict):
        result["recognition"] = entry["recognition"]
    if isinstance(entry.get("focus"), dict):
        result["focus"] = _pick(entry["focus"], ("cellIds", "area", "issueKey", "messageCode", "text", "repeated"))
    return result


def student_step_results(steps: list[Document]) -> list[Document]:
    """Expose aggregate recognition only; reference facts and diagnostics stay private."""
    public = []
    for step in steps:
        item = {**step, "description": None, "resultSummary": None, "result": None}
        report = step.get("result")
        if isinstance(report, dict) and report.get("schema") in ("feedback-report/v2", "feedback-report/v3", "feedback-report/v4"):
            recognition = recognition_of(report)
            fields = ("recognized", "expected", "percent", "evaluationStatus")
            if (isinstance(recognition, dict) and isinstance(recognition.get("overall"), dict)
                    and isinstance(recognition.get("unmatchedSubmission"), list)):
                overview = {"basis": recognition.get("basis"),
                    "overall": {field: recognition["overall"].get(field) for field in fields},
                    "unmatchedSubmission": [{field: row.get(field) for field in ("id", "kind")} for row in recognition["unmatchedSubmission"] if isinstance(row, dict)]}
                if report["schema"] in ("feedback-report/v3", "feedback-report/v4") and isinstance(recognition.get("buckets"), list):
                    overview["buckets"] = [{field: row.get(field) for field in ("id", "label", "kind", "grouped", *fields)}
                                           for row in recognition["buckets"] if isinstance(row, dict)]
                elif report["schema"] == "feedback-report/v2" and isinstance(recognition.get("categories"), dict):
                    overview["categories"] = {category: {field: row.get(field) for field in fields}
                        for category, row in recognition["categories"].items() if category in ("nodes", "attributes", "connections", "other") and isinstance(row, dict)}
                    overview["unmatchedSubmission"] = [{field: row.get(field) for field in ("id", "kind", "category")} for row in recognition["unmatchedSubmission"] if isinstance(row, dict)]
                else:
                    public.append(item)
                    continue
                item["result"] = {"schema": report["schema"], "evaluationId": report.get("evaluationId"),
                    "pair": {"studentKey": "submission", "referenceKey": report.get("pair", {}).get("referenceKey")},
                    "status": report.get("status"), "assessmentAvailable": False}
                if report["schema"] == "feedback-report/v4":
                    item["result"].update(requested=["recognition"], feedback=[{"type": "recognition", "recognition": overview}])
                else:
                    item["result"]["recognition"] = overview
                item["resultSummary"] = "Erkennungs?bersicht verf?gbar; keine Korrektheitsquote oder Note."
        if isinstance(report, dict) and report.get("schema") == "feedback-report/v4" and isinstance(report.get("feedback"), list):
            entries = [public_help_entry(entry) if entry.get("type") in HELP_TYPES else public_hints_entry(entry)
                       for entry in report["feedback"] if isinstance(entry, dict) and entry.get("type") in (*HELP_TYPES, "hints")]
            if entries:
                base = item["result"] or {"schema": report["schema"], "evaluationId": report.get("evaluationId"),
                    "pair": {"studentKey": "submission", "referenceKey": report.get("pair", {}).get("referenceKey")},
                    "status": report.get("status"), "assessmentAvailable": False, "requested": [], "feedback": []}
                item["result"] = {**base, "requested": [*base["requested"], *(entry["type"] for entry in entries)],
                                  "feedback": [*base["feedback"], *entries]}
        public.append(item)
    return public


async def list_workflows() -> list[Document]:
    return await dagu.list_workflows()


async def _evaluation_input(
    evaluation_id: str, task: Document, submission: Document, references: list[Document],
    *, comparison_config: Document | None = None,
) -> tuple[Document, list[Document]]:
    """Freeze complete platform-independent inputs, including language dependencies."""
    if not references:
        raise ApiError(422, "EVALUATION_REFERENCES_REQUIRED", "At least one released reference model is required.")
    if comparison_config is not None and not isinstance(comparison_config, dict):
        raise ApiError(422, "INVALID_COMPARISON_CONFIG", "comparisonConfig must be a JSON object.")
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
    config = deepcopy(comparison_config) if comparison_config is not None else {}
    graph_matching = config.setdefault("graphMatching", {})
    if not isinstance(graph_matching, dict):
        raise ApiError(422, "INVALID_COMPARISON_CONFIG", "graphMatching must be a JSON object.")
    # Every caller serialises the bundle; stored snapshots still carry MongoDB datetimes (task edits).
    return jsonable_encoder({"schemaVersion": 1, "schema": "evaluation-input/v1", "evaluationId": evaluation_id,
                             "task": task, "models": models, "languages": definitions,
                             "comparisonConfig": config}), descriptors


async def start(model_id: UUID, user: User, *, text_evidence: dict | None = None, help_request_id: UUID | None = None,
                all_feedback_types: bool = False) -> Document:
    """`text_evidence`: admin overrides {spelling, meaning, meaningFloor}; None runs the workflow defaults.

    `help_request_id` runs the feedback type the learner asked for in that help request instead of the overview.
    """
    from modeling_api.services import help_requests  # imported late: learning paths import this module
    if all_feedback_types and not can_view_analysis(user):
        raise ApiError(403, "FORBIDDEN", "The feedback catalog requires staff access.")
    if all_feedback_types and help_request_id is not None:
        raise ApiError(422, "FEEDBACK_REQUEST_CONFLICT", "Choose either a help request or the full feedback catalog.")
    if text_evidence is not None and not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "Evaluation parameters require administrator access.")
    model = await db.models.find_one({"_id": str(model_id), "ownerId": user.id})
    if model is None or not model.get("taskVersion"):
        raise not_found()
    await ensure_task_questionnaire_completed(model_id)
    task_ref = model["taskVersion"]
    task_version = await ensure_release_reference(UUID(task_ref["taskId"]), UUID(task_ref["versionId"]), user)
    data = task_version.get("data", {})
    if not data.get("sampleSolutions"):
        raise ApiError(409, "EVALUATION_REFERENCES_REQUIRED", "A released sample solution is required for evaluation.")
    workflow_name = next(iter(data.get("evaluationWorkflows", [])), "model-evaluation-graph-matching")
    version_id = model.get("latestVersionId")
    if not version_id:
        raise ApiError(409, "SUBMISSION_NOT_SAVED", "Save the submission before starting an evaluation.")
    feedback_request = None
    if help_request_id is not None:
        request, feedback_request = await help_requests.feedback_request(help_request_id, model_id, version_id, user)
        # One automatic check per help request; a retry returns the run already started.
        existing = request.get("evaluationId") and await db.evaluations.find_one({"_id": request["evaluationId"], "ownerId": user.id})
        if existing and existing.get("state") not in ("failed", "cancelled"):
            return _public_evaluation(existing)
        if existing:
            await help_requests.release_feedback_reservation(help_request_id)
    elif all_feedback_types:
        # Staff runs precompute every learner help feedback per object once for the analysis view.
        feedback_request = {"types": ["recognition", "help.catalog"], "context": {}}
    # Every run collects the label hints for the separate hint view (AP-10); they are never counted.
    feedback_request = feedback_request or {"types": ["recognition"], "context": {}}
    if "hints" not in feedback_request["types"]:
        feedback_request = {**feedback_request, "types": [*feedback_request["types"], "hints"]}
    unresolved =await db.evaluations.find_one({
        "ownerId": user.id, "modelId": str(model_id), "modelVersionId": str(version_id),
        "dagName": workflow_name, "startStatus": {"$in": ["starting", "unknown"]},
        "helpRequestId": str(help_request_id) if help_request_id else None,
        "feedbackRequest.types": feedback_request["types"],
    })
    if unresolved is not None:
        # A repeated browser request must not launch again after an ambiguous start.
        return _public_evaluation(unresolved)
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
    glossaries = await frozen_glossaries(task_ref["taskId"], [
        {"key": f"reference_{index}", "modelId": item["modelId"], "versionId": item["versionId"]}
        for index, item in enumerate(reference_snapshots, start=1)])
    bundle, parser_models = await _evaluation_input(
        evaluation_id, task_snapshot, snapshot, reference_snapshots,
        comparison_config={"graphMatching": {"glossaries": glossaries}} if glossaries else None)
    if feedback_request is not None:
        bundle["feedbackRequest"] = feedback_request
    encoded = base64.b64encode(gzip.compress(json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"), mtime=0)).decode("ascii")
    if len(encoded) > 100_000:
        raise ApiError(422, "EVALUATION_INPUT_TOO_LARGE", "The complete evaluation snapshot exceeds the workflow launch limit.")
    # One complete input object; subsequent jobs only receive workspace/model keys.
    params = {"evaluation_id": evaluation_id, "evaluation_input": encoded,
              "parser_models": [{"key": source["key"]} for source in parser_models],
              "reference_models": [{"key": source["key"]} for source in parser_models if source["role"] == "reference"],
              "model_count": len(parser_models), "reference_count": len(reference_snapshots)}
    if text_evidence is not None:
        # Dagu declares the parameter as a string; workflow-data validates and freezes it.
        params["text_evidence"] = json.dumps(text_evidence, separators=(",", ":"))
    if help_request_id is not None:
        await help_requests.reserve_feedback(request)
    try:
        evaluation = await insert(db.evaluations, {
            "_id": evaluation_id,
            "ownerId": user.id, "taskId": task_ref["taskId"], "taskVersionId": task_ref["versionId"],
            "modelId": str(model_id), "modelVersionId": str(version_id),
            "task": task_ref, "submission": {"modelId": str(model_id), "versionId": str(version_id)},
            "submissionSnapshot": snapshot, "parserModels": parser_models, "dagName": workflow_name, "dagRunId": evaluation_id,
            "startedAt": utcnow(), "state": "unknown", "startStatus": "starting", "workflow": workflow,
            "parameters": {"textEvidence": text_evidence}, "glossarySnapshots": glossaries,
            "helpRequestId": str(help_request_id) if help_request_id else None, "feedbackRequest": feedback_request,
        })
    except Exception:
        if help_request_id is not None:
            await help_requests.release_feedback_reservation(help_request_id)
        raise
    if help_request_id is not None:
        await help_requests.link_evaluation(help_request_id, evaluation_id)
    try:
        dag_run_id = await dagu.start_workflow(workflow_name, params, run_id=evaluation_id)
    except ApiError as error:
        rejected = error.code in {"DAGU_START_REJECTED", "DAGU_UNAUTHORIZED"}
        changes = {"state": "failed" if rejected else "unknown", "startStatus": "failed" if rejected else "unknown",
                   "startError": {"code": error.code, "message": error.message}}
    else:
        changes = {"dagRunId": dag_run_id, "state": "queued", "startStatus": "started"}
    await db.evaluations.update_one({"_id": evaluation_id}, {"$set": changes})
    evaluation.update(changes)
    return _public_evaluation(evaluation)


def student_evaluation(item: Document) -> Document:
    # Workflow step definitions and run parameters are internals; learners only need the name.
    workflow = item.get("workflow") or {}
    return {**item, "workflow": {"name": workflow.get("name", ""), "labels": {}, "steps": []}, "parameters": {}, "feedbackTypes": []}


async def list_for_model(model_id: UUID, user: User, skip: int, limit: int) -> Document:
    page = await list_page(
        db.evaluations,
        {"modelId": str(model_id), "ownerId": user.id},
        skip,
        limit,
        omit=("submissionSnapshot",),
    )
    items = [_public_evaluation(item) for item in page["items"]]
    return {**page, "items": items if can_view_analysis(user) else [student_evaluation(item) for item in items]}


async def feedback(evaluation_id: UUID, user: User) -> Document:
    """The learner-facing result: state, score and recognition overview only.

    Built server-side from the student projection, so no intermediate artifacts, logs, workflow
    internals or reference-model content ever reach the browser. Persisted once the run is final.
    """
    evaluation = await db.evaluations.find_one({"_id": str(evaluation_id), "ownerId": user.id},
                                               {"startedAt": 1, "workflow.name": 1, "submission": 1, "studentFeedback": 1, "helpRequestId": 1})
    if evaluation is None:
        raise not_found()
    stored = evaluation.get("studentFeedback")
    if stored is None:
        result = await detail(evaluation_id, user, analysis=False)
        recognitions = [{"referenceKey": step["result"]["pair"]["referenceKey"], "recognition": recognition_of(step["result"])}
                        for step in result["steps"]
                        if step["status"] == "succeeded" and isinstance(step.get("result"), dict) and recognition_of(step["result"]) is not None]
        helps = [(entry, step["result"]["pair"]["referenceKey"]) for step in result["steps"]
                 if step["status"] == "succeeded" and isinstance(step.get("result"), dict)
                 for entry in step["result"].get("feedback", []) if entry.get("type") in HELP_TYPES]
        # Several sample solutions: help feedback follows the best recognized one, like the score.
        chosen = min(helps, key=lambda pair: (-(recognition_percent(pair[0].get("overview")) or 0), pair[1]), default=None)
        best = min(recognitions, key=lambda item: (-(recognition_percent((item["recognition"] or {}).get("overall")) or 0),
                                                   item["referenceKey"]), default=None)
        # Object/whole-model help can omit the standalone recognition entry. Its hints follow
        # the same reference as the displayed help instead of requiring an unrelated report type.
        hint_reference_key = best["referenceKey"] if best else chosen[1] if chosen else None
        hints = next((entry["hints"] for step in result["steps"] if hint_reference_key and step["status"] == "succeeded"
                      and isinstance(step.get("result"), dict) and step["result"]["pair"]["referenceKey"] == hint_reference_key
                      for entry in step["result"].get("feedback", []) if entry.get("type") == "hints"), [])
        stored = {"state": result["state"], "scorePercent": result.get("scorePercent"), "recognitions": recognitions,
                  "feedback": [{**chosen[0], "referenceKey": chosen[1]}] if chosen else [],
                  "hints": [{**item, "referenceKey": hint_reference_key} for item in hints]}
        # A succeeded run whose feedback artifact could not be read yet is retried on the next call.
        if result["state"] in {"failed", "cancelled", "succeeded"} and (
            result["state"] != "succeeded" or recognitions or chosen
        ):
            await db.evaluations.update_one({"_id": str(evaluation_id)}, {"$set": {"studentFeedback": stored}})
            if evaluation.get("helpRequestId"):
                from modeling_api.services import help_requests
                await help_requests.record_feedback(evaluation["helpRequestId"], evaluation_id, stored["feedback"])
    return _feedback_projection(evaluation, stored)


def _feedback_projection(evaluation: Document, stored: Document) -> Document:
    """Share the same published feedback between navigation and the learner endpoint."""
    score = learner_score(stored)
    # A decision outranks a mere view, whatever order the browser reported them in.
    states = {}
    retention = {}
    for event in stored.get("hintEvents", []):
        if event["action"] not in HINT_ACTIONS:
            if event["action"] in ("retained", "reverted", "removed"):
                retention[event["hintId"]] = event["action"]
            continue
        current = states.get(event["hintId"], "new")
        states[event["hintId"]] = max(current, event["action"], key=("new", *HINT_ACTIONS).index)
    hints = [{**_pick(item, HINT_FIELDS), "state": states.get(item["id"], "new"),
              "retention": retention.get(item["id"])} for item in stored.get("hints", [])]
    return {"id": evaluation.get("id", evaluation.get("_id")), "startedAt": evaluation["startedAt"],
            "workflowName": evaluation["workflow"]["name"], "submission": evaluation["submission"],
            "state": stored["state"], "recognitions": stored["recognitions"], "feedback": stored.get("feedback", []),
            "hints": hints, "scorePercent": score}


async def record_hint_event(evaluation_id: UUID, hint_id: str, action: str, user: User) -> None:
    """Deduplicated decisions plus observed retention transitions; hints never change recognition."""
    if action not in (*HINT_ACTIONS, "retained", "reverted", "removed"):
        raise ApiError(422, "INVALID_HINT_ACTION", "Unknown hint action.")
    query = {"_id": str(evaluation_id), "ownerId": user.id, "studentFeedback.hints.id": hint_id}
    evaluation = await db.evaluations.find_one(query, {"studentFeedback.hints": 1})
    if evaluation is None:
        raise not_found()
    hint = next(item for item in evaluation["studentFeedback"]["hints"] if item["id"] == hint_id)
    event = {"hintId": hint_id, "action": action, "createdAt": utcnow(),
             "sources": hint.get("sources", []), "relation": hint.get("relation"),
             "withReferenceText": hint.get("suggestion") is not None}
    if action in ("retained", "reverted", "removed"):
        # Keep transitions (including repeated undo/redo), deduplicating only unchanged observations.
        key = hashlib.sha256(hint_id.encode()).hexdigest()
        path = f"studentFeedback.hintRetention.{key}"
        await db.evaluations.update_one(
            {**query, path: {"$ne": action},
             "studentFeedback.hintEvents": {"$elemMatch": {"hintId": hint_id, "action": "accepted"}}},
            {"$set": {path: action}, "$push": {"studentFeedback.hintEvents": event}})
        return
    await db.evaluations.update_one(
        {**query, "studentFeedback.hintEvents": {"$not": {"$elemMatch": {"hintId": hint_id, "action": action}}}},
        {"$push": {"studentFeedback.hintEvents": event}})


def learner_score(stored: Document) -> float | None:
    """The workflow reports no score; the learner score is the best overall recognition across sample solutions."""
    scores = [recognition_percent((item.get("recognition") or {}).get("overall")) for item in stored.get("recognitions", [])]
    return max((value for value in scores if value is not None), default=stored.get("scorePercent"))


def recognition_percent(row: Any) -> float | None:
    if not isinstance(row, dict):
        return None
    recognized, expected = row.get("recognized"), row.get("expected")
    if type(recognized) is not int or type(expected) is not int or expected <= 0:
        return None
    return 100 * recognized / expected


async def _model_run_steps(
    evaluation: Document, parent: Document, children: list[Document], *, allow_analysis: bool
) -> list[Document]:
    step_spec = {
        "parse_models": ("parse_model", "parser-result.json", "graph-parser", "Graph", "MODEL_KEY"),
        "extract_labels": ("extract_labels", "labels-result.json", "model-label-extraction", "Elementinventar", "MODEL_KEY"),
        "match_synonyms": ("match_synonyms", "candidates-result.json", "synonym-matching", "Semantische Kandidaten", "REFERENCE_KEY"),
        "match_graphs": ("match_graph", "comparison-result.json", "one-to-one-graph-matching", "Vorläufiger Graphvergleich", "REFERENCE_KEY"),
        "generate_feedback": ("generate_feedback", "feedback-result.json", "feedback-generation", "Vorläufiges Feedback", "REFERENCE_KEY"),
        "generate_analytical_feedback": ("generate_analytical_feedback", "analysis-result.json", "analytical-feedback", "Analytisches Feedback", "REFERENCE_KEY"),
    }[parent["id"]]
    source_param = step_spec[-1]
    step_specs = [step_spec]
    if parent["id"] == "generate_analytical_feedback":
        step_specs.append(("generate_feedback", "feedback-result.json", "feedback-generation", "Vorläufiges Feedback", "REFERENCE_KEY"))
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
        if isinstance(params, dict) and params.get(source_param):
            by_key[params[source_param]] = child

    async def read(source: Document, spec: tuple[str, ...]) -> Document:
        step_name, artifact_path, capability, label, _ = spec
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
            node = next((item for item in run.get("nodes", []) if
                         (item.get("name") or item.get("id") or (item.get("step") or {}).get("name")) == step_name), None)
            if node is not None:
                step["status"] = _state(node.get("statusLabel") or node.get("status"))
            if capability == "analytical-feedback" and not allow_analysis:
                step["resultSummary"] = "Analytisches Feedback ist Moderatoren und Administratoren vorbehalten."
                return step
            if not allow_analysis and capability != "feedback-generation":
                return step
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

    sources = [source for source in evaluation["parserModels"]
               if source_param == "MODEL_KEY" or source["role"] == "reference"]
    return list(await gather(*(read(source, spec) for source in sources for spec in step_specs)))


async def detail(evaluation_id: UUID, user: User, *, analysis: bool = True) -> Document:
    """`analysis=False` forces the student projection even for administrators."""
    evaluation = await db.evaluations.find_one({"_id": str(evaluation_id), "ownerId": user.id})
    if evaluation is None:
        raise not_found()
    if evaluation.get("startStatus") == "failed":
        run = None
    else:
        try:
            run = _dag_run(await dagu.get_run(evaluation["dagName"], evaluation["dagRunId"]))
            if evaluation.get("startStatus") in {"starting", "unknown"} and run.get("dagRunId") != evaluation["dagRunId"]:
                raise ApiError(503, "DAGU_INVALID_RESPONSE", "The evaluation service did not identify the requested run.")
        except ApiError:
            if evaluation.get("startStatus") not in {"starting", "unknown"}:
                raise
            run = None
    if run is None:
        result = _public_evaluation(evaluation, detail=True)
        failed = evaluation.get("startStatus") == "failed"
        result["steps"] = [{
            "id": "workflow_start", "label": "Workflow-Start", "status": "failed" if failed else "unknown",
            "resultSummary": "Der Auswertungsstart wurde abgelehnt." if failed else
                "Der Startausgang ist unklar. Die Laufkennung bleibt zur Klärung erhalten; es wird kein weiterer Lauf gestartet.",
            "result": {"evaluationId": evaluation["_id"], "dagRunId": evaluation["dagRunId"],
                       "error": evaluation.get("startError")},
        }]
        result["finalResult"] = None
        if not (analysis and can_view_analysis(user)):
            result["steps"] = student_step_results(result["steps"])
        return result
    state = _state(run.get("statusLabel") or run.get("status") or run.get("state"))
    await db.evaluations.update_one({"_id": evaluation["_id"]}, {
        "$set": {"state": state, "startStatus": "started", "lastObservedAt": utcnow()}, "$unset": {"startError": ""},
    })
    return await inspect_run(evaluation, run, allow_analysis=analysis and can_view_analysis(user))


async def inspect_run(evaluation: Document, run: Document, *, allow_analysis: bool,
                      sub_run_id: str | None = None) -> Document:
    """Read a run without changing learner history; also used by isolated lab runs."""
    state = _state(run.get("statusLabel") or run.get("status") or run.get("state"))
    raw_steps = _run_steps(run, evaluation["workflow"])
    # Expand model and reference-pair fan-outs into their persisted artifacts.
    expanded = []
    for step in raw_steps:
        children = step.pop("_subRuns", [])
        if step["id"] in {"parse_models", "extract_labels", "match_synonyms", "match_graphs", "generate_analytical_feedback", "generate_feedback"} and evaluation.get("parserModels"):
            expanded.extend(await _model_run_steps(evaluation, step, children, allow_analysis=allow_analysis))
        else:
            if step["id"] == "generate_analytical_feedback" and not allow_analysis:
                step["resultSummary"] = "Analytisches Feedback ist Moderatoren und Administratoren vorbehalten."
                step["_modelRun"] = True
            expanded.append(step)
    raw_steps = expanded
    completed_steps = [step for step in raw_steps if step["status"] in {"succeeded", "failed"}]
    logs = await gather(*(
        dagu.get_step_log(evaluation["dagName"], evaluation["dagRunId"], step["id"], sub_run_id=sub_run_id)
        for step in completed_steps if not step.get("_modelRun") and allow_analysis
    ), return_exceptions=True)
    for step, log in zip([step for step in completed_steps if not step.get("_modelRun") and allow_analysis], logs, strict=True):
        if isinstance(log, str) and log:
            step["resultSummary"] = log
    steps = _enrich_step_output(raw_steps)
    for step in steps:
        step.pop("_modelRun", None)
    result = _public_evaluation(evaluation, detail=True)
    result["state"] = state
    result["steps"] = steps if allow_analysis else student_step_results(steps)
    final_result = (run.get("result") or run.get("output")) if state == "succeeded" else None
    if state == "succeeded" and allow_analysis and not sub_run_id and not isinstance(final_result, dict):
        try:
            final_result = await dagu.get_run_outputs(evaluation["dagName"], evaluation["dagRunId"])
        except ApiError:
            # Intermediate artifacts remain available even if outputs cannot be loaded.
            final_result = None
    result["finalResult"] = final_result if allow_analysis and isinstance(final_result, dict) else None
    return result
