"""Connect glossary terms to the final recognition shown to learners."""

from asyncio import gather
import json
import shlex

from modeling_api.core.errors import ApiError
from modeling_api.db.client import db
from modeling_api.db.store import Document
from modeling_api.services import dagu
from modeling_api.services.evaluations import _dag_run, recognition_of, recognition_percent
from modeling_api.services.synonym_glossary import term_key
from modeling_api.services.text_forms import prepared


def child_key(child: Document, parameter: str) -> str | None:
    raw = child.get("params") or ""
    try:
        params = json.loads(raw)
    except (ValueError, TypeError):
        try:
            params = dict(item.split("=", 1) for item in shlex.split(raw) if "=" in item)
        except (ValueError, TypeError):
            return None
    return params.get(parameter) if isinstance(params, dict) else None


async def run_details(evaluation: Document) -> Document:
    run = _dag_run(await dagu.get_run(evaluation["dagName"], evaluation["dagRunId"]))
    if evaluation["dagName"] == "evaluation-replay":
        node = next((node for node in run.get("nodes", [])
                     if (node.get("name") or (node.get("step") or {}).get("name")) == "evaluate"), {})
        children = node.get("subRuns") or []
        if len(children) != 1:
            raise ApiError(503, "OUTCOME_UNAVAILABLE", "The full evaluation run is not available yet.")
        run = _dag_run(await dagu.get_sub_run(evaluation["dagName"], evaluation["dagRunId"], children[0]["dagRunId"]))
    return run


async def artifact(evaluation: Document, run: Document, step: str, key: str,
                   path: str, capability: str, *, parameter: str = "REFERENCE_KEY") -> Document:
    node = next((node for node in run.get("nodes", [])
                 if (node.get("name") or (node.get("step") or {}).get("name")) == step), {})
    child = next((child for child in node.get("subRuns", []) or [] if child_key(child, parameter) == key), None)
    if child is None:
        raise ApiError(503, "OUTCOME_UNAVAILABLE", "The final evaluation artifacts are unavailable.")
    envelope = await dagu.get_sub_run_artifact(evaluation["dagName"], evaluation["dagRunId"], child["dagRunId"],
                                              path=path, capability=capability)
    if envelope.get("status") != "ok" or envelope["result"].get("evaluationId") != evaluation["_id"]:
        raise ApiError(503, "OUTCOME_UNAVAILABLE", "The evaluation artifact does not match this run.")
    return envelope["result"]


def pair_conditions(comparison: Document, annotation: Document, reference_id: str, submission_id: str) -> Document:
    """Categorical context facts only; scores and the final decision are not preconditions."""
    trace = next((row for row in comparison.get("diagnostics", {}).get("identityEvidence", {}).get("pairs", [])
                  if row["referenceId"] == reference_id and row["studentId"] == submission_id), None)
    fact = next((row for row in comparison.get("propertyFacts", {}).get("items", [])
                 if row.get("code", "").startswith("identity.") and row.get("referenceIds") == [reference_id]
                 and row.get("submissionIds") == [submission_id]), {})
    criteria = (trace or {}).get("criteria") or fact.get("evidence", {}).get("criteria") or (
        (annotation.get("identity") or {}).get("criteria") if annotation.get("referenceId") == reference_id else None)
    methods = {"identified_owner": "parent", "type_compatibility": "type", "independent_children": "children",
               "combined_children": "combined_children", "connection_structure": "endpoints"}
    states = {"satisfied": "confirmed", "violated": "conflicting", "unresolved": "unresolved",
              "not_applicable": "not_required", "not_evaluated": "not_evaluated"}
    conditions = {}
    for item in criteria or []:
        if item["method"] not in methods:
            continue
        state = states.get(item["result"], "unknown")
        if item["method"] in {"independent_children", "combined_children"} and state == "confirmed" and (
                item.get("complete") is False or 0 < item.get("matched", 0) < item.get("expected", 0)):
            state = "partial"
        conditions[methods[item["method"]]] = state
    if "parent" not in conditions:
        decision = next((row for row in comparison.get("pairDecisions", [])
                         if row["referenceId"] == reference_id and row["studentId"] == submission_id), {})
        parent = {"identified_owner": "confirmed", "owner_unresolved": "unresolved", "owner_conflict": "conflicting"}.get(decision.get("reason"))
        if parent:
            conditions.update(parent=parent, context="incomplete")
    return conditions or {"context": "unknown"}


def term_outcomes(inventory: Document, candidates: Document, analysis: Document, feedback: Document,
                  signals: list[Document], comparison: Document | None = None) -> list[Document]:
    """Only final feedback confirms the analysis; a candidate score never confirms recognition."""
    recognition = recognition_of(feedback)
    if (not isinstance(recognition, dict) or recognition != analysis.get("recognition")
            or recognition.get("basis") != "uniquely_supported"):
        raise ApiError(503, "OUTCOME_UNAVAILABLE", "Final learner recognition could not be verified.")
    annotations = {item["target"]["id"]: item for item in analysis.get("annotations", [])}
    evaluated = {sub: fact.get("evidence", {}).get("evaluationStatus")
                 for fact in (comparison or {}).get("propertyFacts", {}).get("items", [])
                 if fact.get("code", "").startswith("identity.") for sub in fact.get("submissionIds", [])}
    texts = {item["id"]: item["matchText"] for item in inventory.get("elements", []) if item.get("labelStatus") == "present"}
    texts.update({item["id"]: item["matchText"] for item in inventory.get("connectionTexts", [])
                  if item.get("kind") == "self" and item.get("labelStatus") == "present"})
    pairs: dict[tuple[str, str], str] = {}
    scores = {}
    for row in candidates.get("synonymMatrix", []):
        for match in row.get("matches", []):
            pairs[(row["referenceElementId"], match["submissionElementId"])] = row["referenceLabel"]
            scores[(row["referenceElementId"], match["submissionElementId"])] = match.get("scores") or {}
    for row in candidates.get("connectionTextMatrix", []):
        if row.get("kind") == "self":
            pairs[(row["referenceOwnerConnectionId"], row["submissionOwnerConnectionId"])] = row["referenceLabel"]
            scores[(row["referenceOwnerConnectionId"], row["submissionOwnerConnectionId"])] = row.get("scores") or {}
    rows = []
    tiers = (comparison or {}).get("semanticConfiguration", {}).get("textEvidence", {}).get("tiers", [])
    boundaries = {}
    for tier in tiers:
        for method, threshold in tier.get("minimumSimilarity", {}).items():
            acceptance, floor = boundaries.get(method, (threshold, threshold))
            boundaries[method] = (min(acceptance, threshold), min(floor, threshold, tier.get("confirmationFloor", {}).get(method, threshold)))
    suggested = {(item["referenceElementId"], item["termKey"]) for item in signals}
    reference_labels = {reference_id: label for (reference_id, _), label in pairs.items()}
    decisions = {(row["referenceId"], row["studentId"]): row for row in (comparison or {}).get("pairDecisions", [])}
    for (reference_id, submission_id), label in pairs.items():
        text = texts.get(submission_id)
        if not text or len(text) > 256 or not term_key(text) or term_key(text) == term_key(label):
            continue
        item = annotations.get(submission_id)
        if ((reference_id, term_key(text)) not in suggested
                and (item is None or item.get("referenceId") != reference_id)):
            continue
        # Omitted/unevaluated objects are unknown, never silently counted as rejected.
        state = "unknown"
        if item is not None:
            identity = (item.get("identity") or {}).get("status")
            if identity == "uniquely_supported":
                state = "counted" if item.get("referenceId") == reference_id else "counted_elsewhere"
            elif identity in {"supported", "unresolved"} and (evaluated.get(submission_id) == "evaluated" or
                    submission_id not in evaluated and recognition.get("overall", {}).get("evaluationStatus") == "evaluated"):
                state = "not_counted"
        decision = decisions.get((reference_id, submission_id))
        if state == "not_counted" and decision and decision["decision"] == "partial":
            state = "partial"
        same_name = state == "counted_elsewhere" and term_key(reference_labels.get(item.get("referenceId"), "")) == term_key(label)
        reason = (("counted_at_same_name" if same_name else "assigned_elsewhere") if state == "counted_elsewhere"
                  else ("not_evaluated" if evaluated.get(submission_id) == "not_evaluated" else None) if state == "unknown"
                  else decision["reason"] if decision
                  else "text_below_threshold" if state == "not_counted" and decisions and scores[(reference_id, submission_id)] else None)
        rows.append({"referenceElementId": reference_id, "submissionElementId": submission_id,
                     "term": text, "termKey": term_key(text), "state": state, "reason": reason,
                     "conditions": pair_conditions(comparison or {}, item or {}, reference_id, submission_id),
                     "countedAtSameName": same_name,
                     "comparisons": [{"referenceText": label, "submissionText": text, "method": method, "minimum": score, "maximum": score,
                                      "acceptance": boundaries.get(method, (None, None))[0], "floor": boundaries.get(method, (None, None))[1]}
                                     for method, score in scores[(reference_id, submission_id)].items()],
                     "evidenceNote": ("This element was not evaluated for semantic identity." if evaluated.get(submission_id) == "not_evaluated"
                                      else "The saved partial result does not confirm whether this element was evaluated.") if state == "unknown" else None})
    return rows


def comparison_workload(candidates: Document) -> Document:
    by_element = {row["referenceElementId"]: sum(match.get("scoreStatus") == "scored" for match in row["matches"])
                  for row in candidates.get("synonymMatrix", [])}
    connections = candidates.get("connectionTextMatrix", [])
    baseline = sum(by_element.values()) + len(connections)
    for row in connections:
        if row["kind"] == "self":
            identity = row["referenceOwnerConnectionId"]
            by_element[identity] = by_element.get(identity, 0) + 1
    return {"baseline": baseline, "byElement": by_element}


async def read_outcomes(evaluation: Document) -> Document:
    run = await run_details(evaluation)
    inventory = await artifact(evaluation, run, "extract_labels", "submission", "labels-result.json", "model-label-extraction", parameter="MODEL_KEY")
    references = [item for item in evaluation.get("parserModels", []) if item.get("role") == "reference"]

    async def final_feedback(key: str) -> Document:
        try:
            return await artifact(evaluation, run, "generate_analytical_feedback", key, "feedback-result.json", "feedback-generation")
        except ApiError:
            archived = next((item["recognition"] for item in (evaluation.get("studentFeedback") or {}).get("recognitions", [])
                             if item["referenceKey"] == key), None)
            if archived is None:
                raise
            return {"pair": {"referenceKey": key}, "recognition": archived}

    async def read(reference: Document) -> Document:
        key = reference["key"]
        candidates, analysis, feedback = await gather(
            artifact(evaluation, run, "match_synonyms", key, "candidates-result.json", "synonym-matching"),
            artifact(evaluation, run, "generate_analytical_feedback", key, "analysis-result.json", "analytical-feedback"),
            final_feedback(key))
        if any(result.get("pair", {}).get("referenceKey") != key for result in (candidates, analysis, feedback)):
            raise ApiError(503, "OUTCOME_UNAVAILABLE", "The final artifacts refer to a different sample solution.")
        try:
            comparison = await artifact(evaluation, run, "match_graphs", key, "comparison-result.json", "one-to-one-graph-matching")
            if comparison.get("pair", {}).get("referenceKey") != key:
                comparison = None
        except ApiError:
            comparison = None
        try:
            signals = (await artifact(evaluation, run, "export_synonym_signals", key,
                                      "signals-result.json", "synonym-signals"))["signals"]
        except ApiError:
            signals = []
        terms = term_outcomes(inventory, candidates, analysis, feedback, signals, comparison)
        frozen = (evaluation.get("glossarySnapshots") or {}).get(key)
        if frozen is not None:
            decisions = {(item["referenceElementId"], item["termKey"]): item["status"] for item in frozen.get("entries", [])}
            for term in terms:
                term["conditions"]["glossary"] = decisions.get((term["referenceElementId"], term["termKey"]), "none")
        # Pair report (AP-01): every selected pair with its reason, identity status and decision round,
        # so two replays can be compared pair by pair instead of only by recognition buckets.
        rounds = {(row["referenceId"], row["studentId"]): row.get("round") for field in ("provisionalElements", "provisionalConnections")
                  for row in (comparison or {}).get("mapping", {}).get(field, [])}
        pairs = [{"referenceId": item["referenceId"], "submissionId": item["target"]["id"], "reason": item.get("mappingReason"),
                  "identity": (item.get("identity") or {}).get("status"), "round": rounds.get((item["referenceId"], item["target"]["id"]))}
                 for item in analysis.get("annotations", []) if item.get("referenceId")]
        hints = [{field: hint.get(field) for field in ("referenceId", "submissionId", "sources", "relation")}
                 for hint in analysis.get("labelHints", [])]
        return {"referenceVersionId": reference["versionId"], "referenceKey": key,
                "recognition": recognition_of(feedback), "terms": terms,
                "workload": comparison_workload(candidates), "pairs": pairs, "hints": hints,
                "decisionRounds": (comparison or {}).get("decisionRounds")}

    results = await gather(*(read(reference) for reference in references))
    published = evaluation.get("studentFeedback")
    if published is not None:
        published_recognitions = {item["referenceKey"]: item["recognition"] for item in published.get("recognitions", [])}
        if any(published_recognitions.get(item["referenceKey"]) != item["recognition"] for item in results):
            raise ApiError(503, "OUTCOME_UNAVAILABLE", "The archived learner feedback differs from the workflow result.")
    scores = [recognition_percent((item["recognition"] or {}).get("overall")) for item in results]
    best = max((score for score in scores if score is not None), default=None)
    for item, score in zip(results, scores, strict=True):
        item["usedForLearnerResult"] = score is not None and score == best
    return {"evidenceVersion": 7, "evaluationId": evaluation["_id"], "modelVersionId": evaluation["modelVersionId"],
            "scorePercent": best, "references": results}


async def original_outcomes(evaluation: Document) -> Document | None:
    cached = evaluation.get("glossaryOutcomes")
    if cached is not None and cached.get("evidenceVersion") == 7:
        return cached
    try:
        result = await read_outcomes(evaluation)
    except ApiError as error:
        return {**(cached or {"evaluationId": evaluation["_id"], "modelVersionId": evaluation["modelVersionId"], "references": []}),
                "unavailableReason": error.message}
    except (KeyError, TypeError, ValueError):
        return {**(cached or {"evaluationId": evaluation["_id"], "modelVersionId": evaluation["modelVersionId"], "references": []}),
                "unavailableReason": "The archived evaluation does not contain a readable final recognition report."}
    await db.evaluations.update_one({"_id": evaluation["_id"]}, {"$set": {"glossaryOutcomes": result}})
    return result


def merge_comparisons(rows: list[Document]) -> list[Document]:
    merged = {}
    for row in rows:
        for item in row.get("comparisons", []):
            key = item["referenceText"], item["submissionText"], item["method"]
            if key not in merged:
                merged[key] = dict(item)
            else:
                merged[key]["minimum"] = min(merged[key]["minimum"], item["minimum"])
                merged[key]["maximum"] = max(merged[key]["maximum"], item["maximum"])
                for field in ("acceptance", "floor"):
                    if merged[key].get(field) != item.get(field):
                        merged[key][field] = None
    return [{**item, "referenceForm": prepared(item["method"], item["referenceText"]),
             "submissionForm": prepared(item["method"], item["submissionText"])} for item in (merged[key] for key in sorted(merged))]


def condition_groups(rows: list[Document]) -> list[Document]:
    grouped = {}
    for row in rows:
        conditions = row.get("conditions") or {"context": "unknown"}
        thresholds = sorted({(item["method"], item.get("acceptance"), item.get("floor"))
                             for item in row.get("comparisons", [])}, key=lambda item: item[0])
        key = json.dumps([conditions, thresholds], sort_keys=True, separators=(",", ":"))
        group = grouped.setdefault(key, {"key": key, "conditions": conditions, "rows": []})
        group["rows"].append(row)
    return [{"key": group["key"], "conditions": group["conditions"], "cases": len(group["rows"]),
             "comparisons": merge_comparisons(group["rows"]), "counts": summarize(group["rows"]),
             "reasons": {reason: sum(row.get("reason") == reason for row in group["rows"])
                         for reason in sorted({row["reason"] for row in group["rows"] if row.get("reason")})}}
            for _, group in sorted(grouped.items())]


def summarize(rows: list[Document]) -> Document:
    return {"counted": sum(row["state"] == "counted" for row in rows),
            "partial": sum(row["state"] == "partial" for row in rows),
            "notCounted": sum(row["state"] == "not_counted" for row in rows),
            "countedElsewhere": sum(row["state"] == "counted_elsewhere" for row in rows),
            "countedAtSameName": sum(row.get("countedAtSameName", False) for row in rows),
            "unknown": sum(row["state"] == "unknown" for row in rows),
            "usedForLearnerResult": sum(row["state"] == "counted" and row.get("usedForLearnerResult", False) for row in rows)}
