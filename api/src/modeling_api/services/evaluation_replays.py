"""Temporary full evaluations, isolated from learner history and glossary suggestions."""

import base64
import gzip
import json
from asyncio import gather
from datetime import timedelta
from uuid import UUID

from pymongo.errors import DuplicateKeyError

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, new_id, utcnow
from modeling_api.services import dagu, synonym_outcomes
from modeling_api.services.evaluations import _dag_run, _evaluation_input, _public_evaluation, _state, inspect_run, learner_score
from modeling_api.services.synonym_glossary import frozen_glossaries
from modeling_api.services.synonym_signals import _sources, aggregate_outcomes
from modeling_api.services.tasks import ensure_release_reference, get_sample_solution

REPLAY_DAG = "evaluation-replay"
RETENTION = timedelta(days=7)
MAX_BATCHES = 3
MAX_SUBMISSIONS = 500
MAX_ACTIVE = 2


def _scope(task_id: UUID, version_id: UUID) -> Document:
    return {"taskId": str(task_id), "taskVersionId": str(version_id)}


async def _public(batch: Document, reference_version_id: UUID, *, unavailable: bool = False) -> Document:
    results = await db.evaluation_replay_results.find({"batchId": batch["_id"], "expiresAt": {"$gt": utcnow()}}, {"result": 1}).to_list(None)
    return {"id": batch["_id"], "state": batch["state"], "createdAt": batch["createdAt"],
            "expiresAt": batch["expiresAt"], "workflowName": batch["workflow"]["name"],
            "workflowVersion": batch["workflow"].get("labels", {}).get("version"), "textEvidence": batch["textEvidence"],
            "items": [{key: item.get(key) for key in ("evaluationId", "modelVersionId", "runId", "status", "beforePercent", "afterPercent", "error")}
                      for item in batch["items"]],
            "outcomes": aggregate_outcomes([item.get("result") for item in results], str(reference_version_id)),
            "unavailable": unavailable}


async def list_batches(task_id: UUID, version_id: UUID, reference_version_id: UUID) -> list[Document]:
    rows = await db.evaluation_replays.find({**_scope(task_id, version_id), "expiresAt": {"$gt": utcnow()}}).sort("createdAt", -1).to_list(MAX_BATCHES)
    return [await _public(row, reference_version_id) for row in rows]


async def candidates(task_id: UUID, version_id: UUID) -> list[Document]:
    """Latest attempt per saved model version, including failed evaluations for diagnosis."""
    rows = await db.evaluations.find({**_scope(task_id, version_id), "submissionSnapshot": {"$exists": True}},
        {"modelId": 1, "modelVersionId": 1, "ownerId": 1, "startedAt": 1, "state": 1}).sort(
            [("startedAt", -1), ("_id", 1)]).to_list(None)
    models = {row["_id"]: row for row in await db.models.find(
        {"_id": {"$in": list({row["modelId"] for row in rows})}}, {"name": 1, "preferences.evaluationLab": 1}).to_list(None)}
    staff = set(await db.submission_users.distinct("_id", {"isStaff": True}))
    latest = {}
    for row in rows:
        if row["modelId"] in models:
            latest.setdefault(row["modelVersionId"], row)
    return [{"evaluationId": row["_id"], "modelId": row["modelId"], "modelVersionId": row["modelVersionId"],
             "modelName": models[row["modelId"]].get("name") or "Untitled model", "startedAt": row["startedAt"],
             "state": row.get("state", "unknown"), "staff": row["ownerId"] in staff or models[row["modelId"]].get("preferences", {}).get("evaluationLab") is True} for row in latest.values()]


async def start(task_id: UUID, version_id: UUID, reference_version_id: UUID, user: User,
                text_evidence: Document | None, evaluation_ids: list[UUID] | None = None) -> Document:
    scope = _scope(task_id, version_id)
    running = await db.evaluation_replays.find_one({**scope, "state": "running", "expiresAt": {"$gt": utcnow()}})
    if running and evaluation_ids is not None:
        raise ApiError(409, "REPLAY_RUNNING", "A test run is already active for this release. Open it before starting another.")
    if running:
        return await _public(running, reference_version_id)
    release = await ensure_release_reference(task_id, version_id, user)
    if evaluation_ids is None:
        sources = await _sources(task_id, version_id)
    else:
        available = {row["evaluationId"]: row for row in await candidates(task_id, version_id)}
        selected = list(dict.fromkeys(str(identity) for identity in evaluation_ids))
        if any(identity not in available for identity in selected):
            raise ApiError(409, "REPLAY_SOURCE_CHANGED", "A selected submission is no longer available. Refresh the submission list.")
        sources = [{"_id": identity, "modelVersionId": available[identity]["modelVersionId"]} for identity in selected]
    if not sources or len(sources) > MAX_SUBMISSIONS:
        raise ApiError(422, "REPLAY_SUBMISSION_LIMIT", f"A comparison requires 1–{MAX_SUBMISSIONS} evaluated submissions.")
    workflow_name = next(iter(release["data"].get("evaluationWorkflows", [])), "model-evaluation-graph-matching")
    # The full artifact contract is currently supplied by this workflow only.
    if workflow_name != "model-evaluation-graph-matching":
        raise ApiError(422, "REPLAY_WORKFLOW_UNSUPPORTED", "This workflow does not support glossary comparisons.")
    workflow = next((item for item in await dagu.list_workflows() if item["name"] == workflow_name), None)
    if workflow is None:
        raise ApiError(409, "WORKFLOW_UNAVAILABLE", "The configured workflow is unavailable.")
    versions = await gather(*(get_sample_solution(task_id, version_id, UUID(ref["modelId"]), UUID(ref["versionId"]), user)
                              for ref in release["data"]["sampleSolutions"]))
    references = [{"modelId": version["modelId"], "versionId": version["id"], "data": version["data"],
                   "workspaceLanguages": version["workspaceLanguages"]} for version in versions]
    descriptors = [{"key": f"reference_{index}", "modelId": ref["modelId"], "versionId": ref["versionId"]}
                   for index, ref in enumerate(references, 1)]
    batch_id, now = new_id(), utcnow()
    batch = {"_id": batch_id, **scope, "state": "running", "createdBy": user.id, "createdAt": now,
             "expiresAt": now + RETENTION, "leaseUntil": now, "textEvidence": text_evidence, "workflow": workflow,
             "taskSnapshot": {"taskId": str(task_id), "versionId": str(version_id), "data": release["data"],
                              "workspaceLanguages": release.get("workspaceLanguages", [])},
             "references": references, "glossaries": await frozen_glossaries(str(task_id), descriptors),
             "items": [{"index": index, "evaluationId": source["_id"], "modelVersionId": source["modelVersionId"],
                        "runId": f"replay-{batch_id}-{index}", "status": "pending"} for index, source in enumerate(sources)]}
    # Expired metadata is temporary and may be removed even before MongoDB's TTL monitor runs.
    await db.evaluation_replays.delete_many({**scope, "expiresAt": {"$lte": now}})
    try:
        await db.evaluation_replays.insert_one(batch)
    except DuplicateKeyError:
        if evaluation_ids is not None:
            raise ApiError(409, "REPLAY_RUNNING", "Another test run was started for this release. Refresh the run list.")
        running = await db.evaluation_replays.find_one({**scope, "state": "running"})
        return await _public(running, reference_version_id)
    completed = await db.evaluation_replays.find({**scope, "state": "completed"}, {"_id": 1}).sort("createdAt", -1).to_list(None)
    if len(completed) >= MAX_BATCHES:
        obsolete = [row["_id"] for row in completed[MAX_BATCHES - 1:]]
        await db.evaluation_replay_results.delete_many({"batchId": {"$in": obsolete}})
        await db.evaluation_replays.delete_many({"_id": {"$in": obsolete}, "state": "completed"})
    return await _public(batch, reference_version_id)


async def _set_item(batch_id: str, index: int, changes: Document) -> None:
    await db.evaluation_replays.update_one({"_id": batch_id, "state": "running"},
        {"$set": {f"items.$[item].{key}": value for key, value in changes.items()}}, array_filters=[{"item.index": index}])


async def _launch(batch: Document, item: Document) -> None:
    source = await db.evaluations.find_one({"_id": item["evaluationId"], "taskId": batch["taskId"], "taskVersionId": batch["taskVersionId"]})
    if source is None:
        await _set_item(batch["_id"], item["index"], {"status": "failed", "error": "The original evaluation no longer exists."})
        return
    try:
        bundle, models = await _evaluation_input(item["runId"], batch["taskSnapshot"], source["submissionSnapshot"],
                                                 batch["references"], comparison_config={"graphMatching": {"glossaries": batch["glossaries"]}})
        bundle["feedbackRequest"] = {"types": ["recognition", "help.catalog"], "context": {}}
        encoded = base64.b64encode(gzip.compress(json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"), mtime=0)).decode("ascii")
        if len(encoded) > 100_000:
            raise ApiError(422, "EVALUATION_INPUT_TOO_LARGE", "The snapshot exceeds the workflow launch limit.")
        original = await synonym_outcomes.original_outcomes(source)
        before = learner_score(source["studentFeedback"]) if source.get("studentFeedback") else (original or {}).get("scorePercent")
        await _set_item(batch["_id"], item["index"], {"parserModels": models, "beforePercent": before})
        params = {"evaluation_id": item["runId"], "evaluation_input": encoded,
                  "parser_models": json.dumps([{"key": model["key"]} for model in models], separators=(",", ":")),
                  "reference_models": json.dumps([{"key": model["key"]} for model in models if model["role"] == "reference"], separators=(",", ":")),
                  "model_count": len(models), "reference_count": len(batch["references"]),
                  "text_evidence": json.dumps(batch["textEvidence"], separators=(",", ":")) if batch["textEvidence"] else ""}
        await dagu.start_workflow(REPLAY_DAG, {"evaluation_id": item["runId"],
                                  "evaluation_params": json.dumps(params, ensure_ascii=False, separators=(",", ":"))}, run_id=item["runId"])
    except ApiError as error:
        if error.code in {"DAGU_UNAVAILABLE", "DAGU_REQUEST_FAILED", "DAGU_INVALID_RESPONSE"}:
            # The request may have reached Dagu. Reconcile this exact ID before another start.
            await _set_item(batch["_id"], item["index"], {"error": error.message})
            raise
        await _set_item(batch["_id"], item["index"], {"status": "failed", "error": error.message})


async def _poll(batch: Document, item: Document) -> None:
    raw = await dagu.find_run(REPLAY_DAG, item["runId"])
    if raw is None:
        if utcnow() - item["claimedAt"] > timedelta(minutes=2):
            await _set_item(batch["_id"], item["index"], {"status": "pending"})
        return
    state = _state(_dag_run(raw).get("statusLabel") or _dag_run(raw).get("status"))
    if state in {"failed", "cancelled"}:
        await _set_item(batch["_id"], item["index"], {"status": "failed", "error": "The full evaluation or workspace cleanup failed."})
    elif state == "succeeded":
        evaluation = {"_id": item["runId"], "modelVersionId": item["modelVersionId"],
                      "dagName": REPLAY_DAG, "dagRunId": item["runId"], "parserModels": item["parserModels"]}
        try:
            result = await synonym_outcomes.read_outcomes(evaluation)
        except ApiError as error:
            if error.code in {"DAGU_UNAVAILABLE", "DAGU_UNAUTHORIZED"}:
                raise
            await _set_item(batch["_id"], item["index"], {"status": "failed", "error": error.message})
            return
        except (KeyError, ValueError, TypeError) as error:
            await _set_item(batch["_id"], item["index"], {"status": "failed", "error": f"Invalid final result: {error}"})
            return
        await db.evaluation_replay_results.replace_one({"_id": item["runId"]},
            {"_id": item["runId"], "batchId": batch["_id"], "expiresAt": batch["expiresAt"], "result": result}, upsert=True)
        await _set_item(batch["_id"], item["index"], {"status": "done", "afterPercent": result["scorePercent"], "error": None})


async def detail(task_id: UUID, version_id: UUID, batch_id: UUID, reference_version_id: UUID) -> Document:
    query = {"_id": str(batch_id), **_scope(task_id, version_id), "expiresAt": {"$gt": utcnow()}}
    batch = await db.evaluation_replays.find_one(query)
    if batch is None:
        raise not_found()
    unavailable = False
    now, lease_id = utcnow(), new_id()
    # One advancing request per batch, including multiple tabs and administrators.
    claimed = await db.evaluation_replays.update_one({**query, "state": "running", "leaseUntil": {"$lte": now}},
        {"$set": {"leaseUntil": now + timedelta(minutes=10), "leaseId": lease_id}})
    if claimed.modified_count:
        try:
            for item in batch["items"]:
                if item["status"] == "running":
                    await _poll(batch, item)
            batch = await db.evaluation_replays.find_one(query)
            active = sum(item["status"] == "running" for item in batch["items"])
            for item in batch["items"]:
                if active >= MAX_ACTIVE:
                    break
                if item["status"] != "pending":
                    continue
                await _set_item(batch["_id"], item["index"], {"status": "running", "claimedAt": utcnow(), "error": None})
                active += 1
                await _launch(batch, item)
            batch = await db.evaluation_replays.find_one(query)
            if all(item["status"] in {"done", "failed"} for item in batch["items"]):
                await db.evaluation_replays.update_one(query, {"$set": {"state": "completed"},
                    "$unset": {"taskSnapshot": "", "references": ""}})
        except ApiError:
            unavailable = True
        finally:
            await db.evaluation_replays.update_one({"_id": str(batch_id), "leaseId": lease_id}, {"$set": {"leaseUntil": utcnow()}})
    batch = await db.evaluation_replays.find_one(query)
    if batch is None:
        raise not_found()
    return await _public(batch, reference_version_id, unavailable=unavailable)


async def delete(task_id: UUID, version_id: UUID, batch_id: UUID) -> None:
    removed = await db.evaluation_replays.delete_one({"_id": str(batch_id), **_scope(task_id, version_id), "state": "completed"})
    if not removed.deleted_count:
        raise ApiError(409, "REPLAY_RUNNING", "Only completed comparisons can be deleted. Refresh the comparison first.")
    await db.evaluation_replay_results.delete_many({"batchId": str(batch_id)})


async def inspect_item(task_id: UUID, version_id: UUID, batch_id: UUID, evaluation_id: UUID) -> Document:
    batch = await db.evaluation_replays.find_one({"_id": str(batch_id), **_scope(task_id, version_id),
                                                  "expiresAt": {"$gt": utcnow()}})
    item = next((item for item in (batch or {}).get("items", []) if item["evaluationId"] == str(evaluation_id)), None)
    if batch is None or item is None:
        raise not_found()
    source = await db.evaluations.find_one({"_id": str(evaluation_id), **_scope(task_id, version_id)})
    if source is None:
        raise not_found()
    evaluation = {**source, "_id": item["runId"], "dagName": REPLAY_DAG, "dagRunId": item["runId"], "workflow": batch["workflow"],
                  "parserModels": item.get("parserModels", []), "startedAt": batch["createdAt"],
                  "parameters": {"textEvidence": batch["textEvidence"]}, "studentFeedback": None,
                  "feedbackRequest": {"types": ["recognition", "help.catalog"]}}
    if item["status"] == "pending" or not item.get("parserModels"):
        result = _public_evaluation(evaluation, detail=True)
        result.update(state="failed" if item["status"] == "failed" else "queued", steps=[{
            "id": "workflow_start", "label": "Workflow start", "status": "failed" if item["status"] == "failed" else "queued",
            "resultSummary": item.get("error"), "result": None}], finalResult=None, scorePercent=None)
        return result
    outer = _dag_run(await dagu.get_run(REPLAY_DAG, item["runId"]))
    node = next((node for node in outer.get("nodes", [])
                 if (node.get("name") or (node.get("step") or {}).get("name")) == "evaluate"), {})
    children = node.get("subRuns") or []
    child_id = children[0]["dagRunId"] if len(children) == 1 else None
    run = _dag_run(await dagu.get_sub_run(REPLAY_DAG, item["runId"], child_id)) if child_id else outer
    result = await inspect_run(evaluation, run, allow_analysis=True, sub_run_id=child_id)
    result["scorePercent"] = item.get("afterPercent")
    # Include wrapper/cleanup failures as well as failures inside the evaluation.
    outer_state = _state(outer.get("statusLabel") or outer.get("status"))
    if outer_state in {"failed", "cancelled"} or outer_state != result["state"]:
        result["state"] = outer_state
        result["steps"].append({"id": "replay_wrapper", "label": "Test run / cleanup", "status": outer_state,
                                 "resultSummary": item.get("error") or outer.get("error"), "result": None})
    return result
