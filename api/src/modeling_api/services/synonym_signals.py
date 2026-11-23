"""Glossary connector: collect synonym signals of evaluated submissions into one shared suggestion state.

Reading never starts a pipeline run. Recalculation is an explicit job that advances whenever an
administrator polls its status, so no background worker exists and an unattended job simply pauses.
"""

import base64
import gzip
import json
import shlex
from asyncio import Semaphore, gather
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, new_id, utcnow
from modeling_api.schemas.synonym_glossary import SynonymSignals
from modeling_api.services import dagu
from modeling_api.services import synonym_outcomes
from modeling_api.services.evaluations import _dag_run, _evaluation_input, _state
from modeling_api.services.synonym_glossary import scope_of, solution_elements
from modeling_api.services.tasks import ensure_release_reference, get_sample_solution

SIGNAL_DAG = "synonym-signals-model"
SIGNAL_STEP = "export_synonym_signals"
SIGNAL_ARTIFACT = "signals-result.json"
MAX_ACTIVE_RUNS = 2
CLAIM_GRACE = timedelta(seconds=60)
_SOURCE_FIELDS = {"ownerId": 1, "modelId": 1, "modelVersionId": 1, "taskId": 1, "taskVersionId": 1, "dagName": 1, "dagRunId": 1,
                  "parserModels": 1, "workflow.steps.id": 1, "parameters": 1, "glossarySnapshots": 1, "startedAt": 1,
                  "glossaryOutcomes": 1, "studentFeedback": 1}


async def _sources(task_id: UUID, version_id: UUID, *, exclude_staff: bool = True, exclude_owner: str | None = None) -> list[Document]:
    """Latest successful evaluation per model version, with optional owner exclusions."""
    staff = await db.submission_users.distinct("_id", {"isStaff": True}) if exclude_staff else []
    if exclude_owner is not None:
        staff.append(exclude_owner)
    rows = await db.evaluations.find(
        {"taskId": str(task_id), "taskVersionId": str(version_id), "state": "succeeded", "ownerId": {"$nin": staff}},
        _SOURCE_FIELDS,
    ).sort([("startedAt", -1), ("_id", 1)]).to_list(None)
    existing = set(await db.models.distinct("_id", {"_id": {"$in": list({row["modelId"] for row in rows})}}))
    latest: dict[str, Document] = {}
    for row in rows:
        if row["modelId"] in existing:
            latest.setdefault(row["modelVersionId"], row)
    return list(latest.values())


def _references(evaluation: Document) -> list[Document]:
    return [item for item in evaluation.get("parserModels", []) if item.get("role") == "reference"]


async def _stored_sets(version_id: UUID) -> dict[tuple[str, str], Document]:
    rows = await db.synonym_signal_sets.find({"taskVersionId": str(version_id)}, {"signals": 0}).to_list(None)
    return {(row["referenceVersionId"], row["modelVersionId"]): row for row in rows}


def _child_key(child: Document) -> str | None:
    """Dagu stores child params as JSON or as shell-style assignments."""
    raw = child.get("params") or ""
    try:
        params = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        try:
            params = dict(item.split("=", 1) for item in shlex.split(raw) if "=" in item)
        except (ValueError, TypeError):
            return None
    return params.get("REFERENCE_KEY") if isinstance(params, dict) else None


async def _read_signals(dag_name: str, run_id: str, expected_id: str, references: list[Document]) -> dict[str, SynonymSignals]:
    """Validated signals per reference key; anything malformed or foreign is treated as absent."""
    run = _dag_run(await dagu.get_run(dag_name, run_id))
    node = next((item for item in run.get("nodes", [])
                 if (item.get("name") or (item.get("step") or {}).get("name")) == SIGNAL_STEP), None)
    children = {_child_key(child): child for child in (node or {}).get("subRuns", []) or []}
    result: dict[str, SynonymSignals] = {}
    for reference in references:
        child = children.get(reference["key"])
        if child is None:
            continue
        try:
            envelope = await dagu.get_sub_run_artifact(dag_name, run_id, child["dagRunId"], path=SIGNAL_ARTIFACT, capability="synonym-signals")
            signals = SynonymSignals.model_validate(envelope["result"])
        except ValidationError:
            continue
        except ApiError as error:
            if error.code in {"DAGU_UNAVAILABLE", "DAGU_UNAUTHORIZED"}:
                raise
            continue
        if (signals.evaluationId == expected_id and signals.reference.key == reference["key"]
                and signals.reference.modelId == reference["modelId"] and signals.reference.versionId == reference["versionId"]):
            result[reference["key"]] = signals
    return result


async def _store(evaluation: Document, reference: Document, signals: SynonymSignals) -> None:
    await db.synonym_signal_sets.update_one(
        {"referenceVersionId": reference["versionId"], "modelVersionId": evaluation["modelVersionId"]},
        {"$set": {"taskId": evaluation["taskId"], "taskVersionId": evaluation["taskVersionId"],
                  "referenceModelId": reference["modelId"], "modelId": evaluation["modelId"], "evaluationId": evaluation["_id"],
                  "schema": signals.schema_, "glossaryRevision": signals.glossaryRevision,
                  "signals": [item.model_dump() for item in signals.signals], "collectedAt": utcnow()},
         "$setOnInsert": {"_id": new_id()}},
        upsert=True,
    )


def _complete(evaluation: Document, stored: dict[tuple[str, str], Document]) -> bool:
    references = _references(evaluation)
    return bool(references) and all(
        stored.get((reference["versionId"], evaluation["modelVersionId"]), {}).get("evaluationId") == evaluation["_id"]
        for reference in references)


async def _collect(sources: list[Document], stored: dict[tuple[str, str], Document]) -> bool:
    """Reuse stored sets and read artifacts of new evaluations; returns True when Dagu was unreachable."""
    pending = [item for item in sources if not _complete(item, stored)
               and any(step.get("id") == SIGNAL_STEP for step in item.get("workflow", {}).get("steps", []))]
    limit, unavailable = Semaphore(4), False

    async def collect(evaluation: Document) -> None:
        nonlocal unavailable
        async with limit:
            try:
                signals = await _read_signals(evaluation["dagName"], evaluation["dagRunId"], evaluation["_id"], _references(evaluation))
            except ApiError:
                unavailable = True
                return
        for reference in _references(evaluation):
            if reference["key"] in signals:
                await _store(evaluation, reference, signals[reference["key"]])
                stored[(reference["versionId"], evaluation["modelVersionId"])] = {"evaluationId": evaluation["_id"]}

    await gather(*(collect(item) for item in pending))
    return unavailable


def _public_job(job: Document | None) -> Document | None:
    if job is None:
        return None
    items = job["items"]
    return {"id": job["_id"], "scope": job["scope"], "state": job["state"], "total": len(items),
            "done": sum(item["status"] == "done" for item in items), "failed": sum(item["status"] == "failed" for item in items)}


async def _start_item(job: Document, item: Document, user: User) -> None:
    evaluation = await db.evaluations.find_one({"_id": item["evaluationId"]})
    run_id = item["runId"]
    try:
        if evaluation is None:
            raise ApiError(404, "NOT_FOUND", "The evaluation no longer exists.")
        task_id, version_id = UUID(job["taskId"]), UUID(job["taskVersionId"])
        release = await ensure_release_reference(task_id, version_id)
        solutions = await gather(*(
            get_sample_solution(task_id, version_id, UUID(reference["modelId"]), UUID(reference["versionId"]), user)
            for reference in release["data"]["sampleSolutions"]))
        references = [{"modelId": version["modelId"], "versionId": version["id"], "data": version["data"],
                       "workspaceLanguages": version["workspaceLanguages"]} for version in solutions]
        task_snapshot = {"taskId": job["taskId"], "versionId": job["taskVersionId"], "data": release["data"],
                         "workspaceLanguages": release.get("workspaceLanguages", [])}
        glossaries = evaluation.get("glossarySnapshots") or {}
        bundle, models = await _evaluation_input(run_id, task_snapshot, evaluation["submissionSnapshot"], references,
                                                 comparison_config={"graphMatching": {"glossaries": glossaries}} if glossaries else None)
        encoded = base64.b64encode(gzip.compress(json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"), mtime=0)).decode("ascii")
        if len(encoded) > 100_000:
            raise ApiError(422, "EVALUATION_INPUT_TOO_LARGE", "The snapshot exceeds the workflow launch limit.")
        params: Document = {"evaluation_id": run_id, "evaluation_input": encoded,
                            "parser_models": [{"key": source["key"]} for source in models],
                            "reference_models": [{"key": source["key"]} for source in models if source["role"] == "reference"]}
        text_evidence = (evaluation.get("parameters") or {}).get("textEvidence")
        if text_evidence is not None:
            params["text_evidence"] = json.dumps(text_evidence, separators=(",", ":"))
        await dagu.start_workflow(SIGNAL_DAG, params, run_id=run_id)
    except ApiError as error:
        transient = error.code in {"DAGU_UNAVAILABLE", "DAGU_REQUEST_FAILED", "DAGU_INVALID_RESPONSE"}
        await _set_item(job["_id"], item["index"], "pending" if transient else "failed")
        if transient:
            raise


async def _set_item(job_id: str, index: int, status: str) -> None:
    await db.synonym_signal_jobs.update_one(
        {"_id": job_id}, {"$set": {"items.$[item].status": status, "items.$[item].claimedAt": utcnow()}},
        array_filters=[{"item.index": index}])


async def _poll_item(job: Document, item: Document) -> None:
    """Move one running item forward; only a finished run is ever read."""
    try:
        raw = await dagu.find_run(SIGNAL_DAG, item["runId"])
    except ApiError:
        return
    if raw is None:
        # Claimed but never started (the claiming request died): hand it back after a grace period.
        if utcnow() - item["claimedAt"] > CLAIM_GRACE:
            await _set_item(job["_id"], item["index"], "pending")
        return
    run = _dag_run(raw)
    state = _state(run.get("statusLabel") or run.get("status"))
    if state in {"failed", "cancelled"}:
        await _set_item(job["_id"], item["index"], "failed")
    elif state == "succeeded":
        evaluation = await db.evaluations.find_one({"_id": item["evaluationId"]}, _SOURCE_FIELDS)
        references = _references(evaluation) if evaluation else []
        try:
            signals = await _read_signals(SIGNAL_DAG, item["runId"], item["runId"], references)
        except ApiError:
            return
        if not references or any(reference["key"] not in signals for reference in references):
            await _set_item(job["_id"], item["index"], "failed")
            return
        for reference in references:
            await _store(evaluation, reference, signals[reference["key"]])
        await _set_item(job["_id"], item["index"], "done")


async def _advance(job: Document, user: User) -> Document:
    await gather(*(_poll_item(job, item) for item in job["items"] if item["status"] == "running"))
    job = await db.synonym_signal_jobs.find_one({"_id": job["_id"]})
    active = sum(item["status"] == "running" for item in job["items"])
    for item in job["items"]:
        if active >= MAX_ACTIVE_RUNS:
            break
        if item["status"] != "pending":
            continue
        # The conditional update is the claim: concurrent pollers cannot start the same run twice.
        claimed = await db.synonym_signal_jobs.update_one(
            {"_id": job["_id"], "items": {"$elemMatch": {"index": item["index"], "status": "pending"}}},
            {"$set": {"items.$.status": "running", "items.$.claimedAt": utcnow()}})
        if claimed.modified_count:
            active += 1
            await _start_item(job, item, user)
    job = await db.synonym_signal_jobs.find_one({"_id": job["_id"]})
    if all(item["status"] in {"done", "failed"} for item in job["items"]):
        await db.synonym_signal_jobs.update_one({"_id": job["_id"], "state": "running"},
                                                {"$set": {"state": "completed", "finishedAt": utcnow()}})
        job = await db.synonym_signal_jobs.find_one({"_id": job["_id"]})
    return job


async def status(task_id: UUID, version_id: UUID, user: User) -> Document:
    """The shared state of this release; polling it is what moves a running job forward."""
    unavailable = False
    job = await db.synonym_signal_jobs.find_one({"taskId": str(task_id), "taskVersionId": str(version_id)}, sort=[("createdAt", -1)])
    if job is not None and job["state"] == "running":
        try:
            job = await _advance(job, user)
        except ApiError:
            unavailable = True
    sources = await _sources(task_id, version_id)
    stored = await _stored_sets(version_id)
    unavailable = await _collect(sources, stored) or unavailable
    collected = sum(_complete(item, stored) for item in sources)
    return {"evaluated": len(sources), "collected": collected, "missing": len(sources) - collected,
            "unavailable": unavailable, "job": _public_job(job)}


async def recalculate(task_id: UUID, version_id: UUID, scope: str, user: User) -> Document:
    await ensure_release_reference(task_id, version_id, user)
    running = await db.synonym_signal_jobs.find_one({"taskId": str(task_id), "taskVersionId": str(version_id), "state": "running"})
    if running is None:
        sources = await _sources(task_id, version_id)
        stored = await _stored_sets(version_id)
        targets = sources if scope == "all" else [item for item in sources if not _complete(item, stored)]
        if targets:
            job_id = new_id()
            try:
                await db.synonym_signal_jobs.insert_one({
                    "_id": job_id, "taskId": str(task_id), "taskVersionId": str(version_id), "scope": scope, "state": "running",
                    "createdBy": user.id, "createdAt": utcnow(),
                    "items": [{"index": index, "evaluationId": item["_id"], "runId": f"glossary-{job_id}-{index}", "status": "pending"}
                              for index, item in enumerate(targets)],
                })
            except DuplicateKeyError:
                pass  # another administrator started the shared job first
    return await status(task_id, version_id, user)


def _suggestions(sets: list[Document], owners: dict[str, str], elements: dict[str, Document], entries: list[Document],
                 results: list[Document | None] | None = None, reference_version_id: str | None = None) -> list[Document]:
    sets = list(sets)
    for result in results or []:
        if result is None:
            continue
        terms = [term for reference in result.get("references", []) if reference["referenceVersionId"] == reference_version_id
                 for term in reference["terms"] if term["state"] == "counted"]
        sets.append({"modelVersionId": result["modelVersionId"], "signals": [
            {**term, "evidence": "recognized"} for term in terms]})
    rows: dict[tuple[str, str], Document] = {}
    for signal_set in sets:
        owner = owners.get(signal_set["modelVersionId"])
        if owner is None:
            continue
        for signal in signal_set["signals"]:
            pair = (signal["referenceElementId"], signal["termKey"])
            if pair[0] not in elements:
                continue
            row = rows.setdefault(pair, {"variants": Counter(), "persons": set(), "submissions": set(), "evidence": Counter(), "comparisons": []})
            row["variants"][signal["term"]] += 1
            row["persons"].add(owner)
            row["submissions"].add(signal_set["modelVersionId"])
            row["evidence"][signal["evidence"]] += 1
            row["comparisons"].extend(signal.get("comparisons", []))
            row["comparisons"].extend({"referenceText": elements[pair[0]]["label"], "submissionText": signal["term"],
                                       "method": method, "minimum": score, "maximum": score}
                                      for method, score in signal.get("scores", {}).items())
    by_term: dict[str, list[str]] = defaultdict(list)
    for reference_id, key in rows:
        by_term[key].append(reference_id)
    result = []
    for (reference_id, key), row in rows.items():
        variants = sorted(row["variants"].items(), key=lambda item: (-item[1], item[0]))
        result.append({
            "referenceElementId": reference_id, "term": variants[0][0], "termKey": key,
            "variants": [{"text": text, "count": count} for text, count in variants],
            "persons": len(row["persons"]), "submissions": len(row["submissions"]),
            "evidence": {"contextUnique": row["evidence"]["context_unique"], "contextBest": row["evidence"]["context_best"],
                         "textOnly": row["evidence"]["text_only"], "recognized": row["evidence"]["recognized"]},
            "comparisons": synonym_outcomes.merge_comparisons([row]),
            "alsoSuggestedFor": [{"referenceElementId": other, "label": elements[other]["label"],
                                  "persons": len(rows[(other, key)]["persons"])}
                                 for other in sorted(by_term[key]) if other != reference_id],
        })
    result.sort(key=lambda item: (-item["evidence"]["contextUnique"], -item["persons"], item["term"].casefold(), item["referenceElementId"]))
    return result


def _public_entry(entry: Document) -> Document:
    return {**{key: entry[key] for key in ("id", "referenceElementId", "term", "termKey", "status", "origin", "updatedAt")},
            "matchingSource": entry.get("matchingSource", False)}


async def solution_view(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID, user: User,
                        *, exclude_own: bool = False, exclude_staff: bool = True) -> Document:
    """Glossary and suggestions of one sample solution; stays usable while Dagu is unreachable."""
    solution = await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    release = await ensure_release_reference(task_id, version_id, user)
    if not release["data"].get("sampleSolutions"):
        raise not_found()
    elements = await solution_elements(solution)
    signal_status = await status(task_id, version_id, user)
    document: Any = await db.synonym_glossaries.find_one(scope_of(task_id, model_id, model_version_id), {"revision": 1, "entries": 1})
    entries = (document or {}).get("entries", [])
    sources = await _sources(task_id, version_id, exclude_staff=exclude_staff, exclude_owner=user.id if exclude_own else None)
    current = {item["modelVersionId"]: item["_id"] for item in sources}
    sets = [row for row in await db.synonym_signal_sets.find(
        {"taskVersionId": str(version_id), "referenceVersionId": str(model_version_id)}).to_list(None)
        if row["modelVersionId"] in current]
    owners = {item["modelVersionId"]: item["ownerId"] for item in sources}
    limit = Semaphore(2)

    async def collect(evaluation: Document) -> Document | None:
        async with limit:
            return await synonym_outcomes.original_outcomes(evaluation)

    results = await gather(*(collect(item) for item in sources))
    # Recalculated signals are suggestions, not proof of an original learner result.
    # Keep these cases inspectable even when the original workflow artifacts are missing.
    for source, result in zip(sources, results, strict=True):
        if result is None:
            continue
        references = result.setdefault("references", [])
        reference = next((item for item in references if item["referenceVersionId"] == str(model_version_id)), None)
        if reference is None:
            reference = {"referenceVersionId": str(model_version_id), "usedForLearnerResult": False, "terms": []}
            references.append(reference)
        present = {(item["referenceElementId"], item["termKey"]) for item in reference["terms"]}
        for term in reference["terms"]:
            if term["state"] == "unknown" and not term.get("evidenceNote"):
                term["evidenceNote"] = result.get("unavailableReason") or "The saved result does not confirm whether this element was evaluated."
        for signal_set in sets:
            if signal_set["modelVersionId"] != source["modelVersionId"]:
                continue
            for signal in signal_set["signals"]:
                pair = (signal["referenceElementId"], signal["termKey"])
                if pair not in present:
                    reference["terms"].append({"referenceElementId": pair[0], "termKey": pair[1], "term": signal["term"],
                        "submissionElementId": None, "state": "unknown",
                        "comparisons": [{"referenceText": elements[pair[0]]["label"], "submissionText": signal["term"],
                                         "method": method, "minimum": score, "maximum": score}
                                        for method, score in signal.get("scores", {}).items()] if pair[0] in elements else [],
                        "evidenceNote": result.get("unavailableReason") or
                            "This term has suggestion evidence, but no recorded result for this pair in the original evaluation."})
                    present.add(pair)
    outcomes = aggregate_outcomes(results, str(model_version_id))
    return {"revision": (document or {}).get("revision", 0), "elements": list(elements.values()),
            "entries": [_public_entry(item) for item in entries],
            "suggestions": _suggestions(sets, owners, elements, entries, results, str(model_version_id)), "signals": signal_status,
            "outcomes": outcomes, "outcomesUnavailable": sum(item is None or bool(item.get("unavailableReason")) for item in results),
            "matchingWorkload": matching_workload(results, str(model_version_id), entries, len(elements))}


def matching_workload(results: list[Document | None], reference_version_id: str, entries: list[Document], element_count: int) -> Document:
    sources = Counter(item["referenceElementId"] for item in entries if item["status"] == "accepted" and item.get("matchingSource"))
    counts = [reference["workload"] for result in results for reference in (result or {}).get("references", [])
              if reference["referenceVersionId"] == reference_version_id and "workload" in reference]
    if counts:
        baseline = sum(item["baseline"] for item in counts)
        additional = sum(number * item["byElement"].get(identity, 0) for item in counts for identity, number in sources.items())
    else:
        baseline, additional = element_count, sum(sources.values())
    return {"basis": "text_pairs" if counts else "reference_texts", "baseline": baseline, "additional": additional,
            "total": baseline + additional, "percent": 100 * additional / baseline if baseline else None,
            "covered": len(counts), "evaluated": len(results)}


def aggregate_outcomes(results: list[Document | None], reference_version_id: str) -> list[Document]:
    grouped: dict[tuple[str, str], list[Document]] = defaultdict(list)
    for result in results:
        for reference in (result or {}).get("references", []):
            if reference["referenceVersionId"] == reference_version_id:
                for term in reference["terms"]:
                    grouped[(term["referenceElementId"], term["termKey"])].append(
                        {**term, "evaluationId": result["evaluationId"], "modelVersionId": result["modelVersionId"],
                         "usedForLearnerResult": reference["usedForLearnerResult"]})
    return [{"referenceElementId": ref, "termKey": key, "term": rows[0]["term"],
             "groups": synonym_outcomes.condition_groups(rows),
             "comparisons": synonym_outcomes.merge_comparisons(rows),
             "counts": synonym_outcomes.summarize(rows),
             "reasons": Counter(row["reason"] for row in rows if row.get("reason")),
             "occurrences": [{key: row[key] for key in ("evaluationId", "modelVersionId", "submissionElementId", "state", "usedForLearnerResult")}
                             | {"evidenceNote": row.get("evidenceNote"), "reason": row.get("reason")} for row in rows]}
            for (ref, key), rows in sorted(grouped.items())]
