"""Read historical matching evidence on demand without rerunning the algorithm."""

from asyncio import gather
from uuid import UUID

from modeling_api.core.errors import ApiError, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, utcnow
from modeling_api.schemas.synonym_glossary import ExplainOutcome
from modeling_api.services import synonym_outcomes as outcomes
from modeling_api.services.evaluations import recognition_of
from modeling_api.services.synonym_glossary import term_key

CHECK_NOTES = {
    "exact_label": "Compares the original labels for equality.",
    "type_compatibility": "Compatible types allow a comparison; they do not establish identity.",
    "text_similarity": "The text verdict recorded by the matcher for the indicated evidence scope.",
    "identified_owner": "Checks whether the owning elements were independently identified.",
    "independent_children": "Uses independently recognized child elements as support.",
    "combined_children": "Checks the combined child structure; incomplete support cannot establish identity.",
    "connection_structure": "Checks identified endpoints and their connection.",
    "label_structure": "The label conflicts with the observed structure.",
}
VETO_NOTES = {
    "glossary_rejected": "The frozen glossary rejects this term for text matching.",
    "digit_mismatch": "Different numbers prevent the text match.",
    "start_mismatch": "Different word starts prevent character similarity from confirming this pair.",
}


def candidate_pairs(candidates: Document) -> list[Document]:
    pairs = [{"referenceElementId": row["referenceElementId"], "referenceLabel": row["referenceLabel"],
              "submissionElementId": match["submissionElementId"], "submissionLabel": match["submissionLabel"],
              "scores": match.get("scores") or {}, "scoreStatus": match.get("scoreStatus"), "matchingSources": match.get("matchingSources", [])}
             for row in candidates.get("synonymMatrix", []) for match in row.get("matches", [])]
    pairs.extend({"referenceElementId": row["referenceOwnerConnectionId"], "referenceLabel": row["referenceLabel"],
                  "submissionElementId": row["submissionOwnerConnectionId"], "submissionLabel": row["submissionLabel"],
                  "scores": row.get("scores") or {}, "scoreStatus": row.get("scoreStatus"), "matchingSources": row.get("matchingSources", [])}
                 for row in candidates.get("connectionTextMatrix", []) if row.get("kind") == "self")
    return pairs


def explain_pair(pair: Document, pairs: list[Document], analysis: Document, feedback: Document,
                 comparison: Document, glossary: Document | None, limitations: list[str], known_state: str | None = None) -> Document:
    ref, sub = pair["referenceElementId"], pair.get("submissionElementId")
    annotation = next((item for item in analysis.get("annotations", []) if item["target"]["id"] == sub), {})
    identity = annotation.get("identity") or {}
    recognition = recognition_of(feedback)
    verified = (isinstance(recognition, dict) and recognition == analysis.get("recognition")
                and recognition.get("basis") == "uniquely_supported")
    state, summary = "unknown", "The final learner result cannot be verified from the available evidence."
    if verified:
        if identity.get("status") == "uniquely_supported":
            if annotation.get("referenceId") == ref:
                state, summary = "counted", "Final feedback confirms a unique match with this reference element."
            else:
                other = next((item["referenceLabel"] for item in pairs if item["referenceElementId"] == annotation.get("referenceId")), annotation.get("referenceId", "another element"))
                state, summary = "counted_elsewhere", f'The element was counted as “{other}” instead of this reference element.'
        elif identity.get("status") in {"supported", "unresolved"} and recognition.get("overall", {}).get("evaluationStatus") == "evaluated":
            state = "not_counted"
            summary = ("A provisional correspondence was recorded, but its identity was not uniquely established."
                       if annotation.get("referenceId") == ref else "No unique correspondence with this reference element was recorded in the final result.")
    facts = comparison.get("propertyFacts", {}).get("items", [])
    exact = next((fact for fact in facts if fact.get("code", "").startswith("identity.")
                  and fact.get("referenceIds") == [ref] and fact.get("submissionIds") == [sub]), None)
    aggregate = next((fact for fact in facts if fact.get("code", "").startswith("identity.")
                      and fact.get("submissionIds") == [sub] and not fact.get("referenceIds")), None)
    evidence = (exact or aggregate or {}).get("evidence", {})
    if verified and identity.get("status") in {"supported", "unresolved"} and evidence.get("evaluationStatus") == "evaluated":
        state = "not_counted"
        if summary.startswith("The final learner result"):
            summary = "This element was evaluated, but no unique correspondence was established. It was not counted."
    decision = next((item for item in comparison.get("pairDecisions", []) if item["referenceId"] == ref and item["studentId"] == sub), None)
    if state == "not_counted" and decision and decision["decision"] == "partial":
        state, summary = "partial", "The term exists and fits this element, but its containing element was not identified. It does not count toward the score."
    criteria = evidence.get("criteria", [])
    scope = "pair" if exact else "submission" if aggregate else "suggestion"
    trace = next((item for item in comparison.get("diagnostics", {}).get("identityEvidence", {}).get("pairs", [])
                  if item["referenceId"] == ref and item["studentId"] == sub), None)
    if trace is not None:
        criteria, scope = trace["criteria"], "pair"
    if not criteria and annotation.get("referenceId") == ref:
        criteria, scope = identity.get("criteria", []), "pair"
    checks = []
    for criterion in criteria:
        note = CHECK_NOTES.get(criterion["method"], "A criterion recorded by the matcher.")
        if criterion.get("veto"):
            note += " " + VETO_NOTES.get(criterion["veto"], f'Recorded veto: {criterion["veto"]}.')
        if criterion.get("tier"):
            note += f' Reached text tier: {criterion["tier"]}.'
        if criterion.get("sourceTerm"):
            note += f' Compared using the explicitly approved matching source “{criterion["sourceTerm"]}”.'
        if criterion.get("expected") is not None:
            note += f' Supporting elements: {criterion.get("matched", 0)} of {criterion["expected"]}.'
        if criterion.get("dependsOn"):
            note += " Depends on: " + ", ".join(f'{item["referenceId"]} ↔ {item["studentId"]}' for item in criterion["dependsOn"]) + "."
        checks.append({"method": criterion["method"], "result": criterion["result"], "role": criterion.get("role", "support"), "note": note})
    count = evidence.get("supportingCandidateCount")
    if count is not None:
        checks.append({"method": "candidate_count", "result": "informational", "role": "support",
                       "note": f'{count} candidate pair(s) have supporting evidence for this {"reference element" if exact else "submission element"}. This count alone does not prove a unique match.'})
    if evidence.get("evaluationStatus") == "not_evaluated":
        state = "unknown"
        summary = "This element was not included in semantic identity evaluation."
    if glossary is not None:
        decision = next((item["status"] for item in glossary.get("entries", [])
                         if item["referenceElementId"] == ref and item["termKey"] == term_key(pair["submissionLabel"])), None)
        note = (f'Frozen glossary revision {glossary.get("revision", 0)}: {decision or "no decision"}. '
                + ("This rejects text matching; independent structural evidence is a separate check." if decision == "rejected"
                   else "Text acceptance still requires an unambiguous overall correspondence." if decision == "accepted"
                   else "No manual text decision was recorded for this term."))
        checks.append({"method": "frozen_glossary", "result": "violated" if decision == "rejected" else "satisfied" if decision == "accepted" else "informational", "role": "support", "note": note})
    config = comparison.get("semanticConfiguration", {})
    tiers = config.get("textEvidence", {}).get("tiers", [])
    if config.get("minimumSimilarity"):
        tiers = [{"name": "minimumSimilarity", "minimumSimilarity": config["minimumSimilarity"]}]
    methods = sorted(set(pair.get("scores", {})) | {method for tier in tiers for method in tier["minimumSimilarity"]})
    similarities = [{"method": method, "score": pair.get("scores", {}).get(method),
                     "thresholds": {tier["name"]: tier["minimumSimilarity"][method] for tier in tiers if method in tier["minimumSimilarity"]},
                     "confirmationFloors": {tier["name"]: tier["confirmationFloor"][method] for tier in tiers if method in tier.get("confirmationFloor", {})}}
                    for method in methods]
    for source in pair.get("matchingSources", []):
        similarities.extend({**item, "referenceText": source["term"], "score": source["scores"].get(item["method"])}
                            for item in similarities[:len(methods)])
    if state == "not_counted":
        veto = next((criterion["veto"] for criterion in criteria if criterion.get("veto")), None) if scope == "pair" else None
        scored = [item for item in similarities if item["score"] is not None and item["thresholds"]]
        if veto:
            summary = VETO_NOTES.get(veto, f'The matcher recorded the veto “{veto}”.') + " No independent identity anchor confirmed this pair in the final result."
        elif count is not None and count > 1:
            summary = f'{count} candidate pairs have supporting evidence for this {"reference element" if exact else "submission element"}. The final result did not establish a unique correspondence with this reference element.'
        elif scored and all(item["score"] < min(item["thresholds"].values()) for item in scored):
            summary = "The text scores for this pair are below every saved acceptance threshold. The final result records no uniquely confirmed correspondence."
        elif any(any(item["score"] >= threshold for threshold in item["thresholds"].values()) for item in scored):
            summary = "A text threshold is reached, but the final result does not establish a unique correspondence. The recorded identity checks below show the remaining support and open conditions."
    chosen = {(item.get("referenceId"), item["target"]["id"]) for item in analysis.get("annotations", [])
              if item.get("identity", {}).get("status") == "uniquely_supported"}
    alternatives = [{**{key: item[key] for key in ("referenceElementId", "referenceLabel", "submissionElementId", "submissionLabel")},
                     "counted": verified and (item["referenceElementId"], item["submissionElementId"]) in chosen}
                    for item in pairs if (item["referenceElementId"] == ref or item["submissionElementId"] == sub)
                    and (item["referenceElementId"], item["submissionElementId"]) != (ref, sub)]
    alternatives.sort(key=lambda item: (not item["counted"], item["referenceElementId"], item["submissionElementId"]))
    notes = list(limitations)
    if not verified and known_state in {"counted", "partial", "not_counted", "counted_elsewhere"}:
        state = known_state
        summary = {"counted": "The saved learner result confirms this pair was counted.",
                   "partial": "The saved result records this term as present, with its containing element unidentified.",
                   "not_counted": "The saved learner result records that this pair was not counted.",
                   "counted_elsewhere": "The saved learner result records that the element was counted as a different reference element."}[known_state]
        notes.append("The result status was previously verified and saved. The complete original feedback is not currently available to verify its detailed reasoning again.")
    if not verified and analysis and feedback:
        notes.append("The final feedback does not contain a recognition report matching the analysis. Candidate evidence cannot establish the learner result.")
    if scope != "pair":
        notes.append("No pair-specific decision trace was saved. Element-level checks describe all alternatives for that element; similarity scores show text evidence only.")
        if count:
            notes.append("The saved evidence gives the number of supported alternatives, but does not identify which individual pairs supplied that support.")
    if len(alternatives) > 5:
        notes.append(f'{len(alternatives)} other compared pairs exist; the first five are shown, with confirmed matches first.')
    source_term = next((item["sourceTerm"] for item in criteria if item.get("sourceTerm")), None)
    similar = any(item["score"] is not None and any(item["score"] >= threshold for threshold in item["thresholds"].values())
                  for item in similarities)
    candidate_reason = (f'The wording is similar to your comparison term “{source_term}”.' if source_term else
                        "The names are similar enough to be considered." if similar else
                        "The term was compared with this element because their model types are compatible.")
    result_reason = {
        "counted": "The evaluation recognized this term as the selected element and counted it.",
        "partial": "The term exists and fits this element, but its containing element was not recognized. It is partially recognized and does not count toward the score.",
        "counted_elsewhere": summary,
        "unknown": ("The original evaluation report is unavailable, so it is not possible to tell whether this term counted."
                    if not analysis else "The saved report has no confirmed recognition decision for this term."),
        "not_counted": "The evaluation could not clearly identify which element was meant, so it did not count this term.",
    }[state]
    if state == "not_counted":
        veto = next((item.get("veto") for item in criteria if item.get("veto")), None) if scope == "pair" else None
        if veto == "glossary_rejected":
            result_reason = "This term was rejected in the glossary used for this evaluation."
        elif veto == "digit_mismatch":
            result_reason = "The numbers in the two names differ, so the text match was not accepted."
        elif veto == "start_mismatch":
            result_reason = "The names begin differently. Their spelling alone did not establish a match."
        elif count is not None and count > 1:
            result_reason = "Several elements were plausible. The evaluation could not choose one clearly, so it did not count this term."
        elif "below every saved acceptance threshold" in summary:
            result_reason = "The names were not similar enough for automatic recognition, and no clear match was established."
        else:
            open_checks = {item["method"] for item in criteria if item["result"] in {"violated", "unresolved"}}
            if "label_structure" in open_checks:
                result_reason = "The name suggests a match, but the structure of the model does not fit. The term was not counted."
            elif "identified_owner" in open_checks:
                result_reason = "The containing element was not clearly recognized, so the position of this term could not confirm the match."
            elif open_checks & {"independent_children", "combined_children"}:
                result_reason = "The elements inside this object did not provide enough confirmation. The evaluation could not establish a clear match."
            elif "connection_structure" in open_checks:
                result_reason = "The connected elements did not clearly confirm which connection was meant, so this term was not counted."
        if not verified:
            result_reason = "The saved result says this term was not counted. Its detailed reason is no longer available."
    if state == "unknown" and evidence.get("evaluationStatus") == "not_evaluated":
        result_reason = "This element was not evaluated, so there is no recognition decision to show."
    return {"submissionElementId": sub, "submissionLabel": pair["submissionLabel"], "referenceLabel": pair["referenceLabel"],
            "state": state, "summary": summary, "evidenceScope": scope, "checks": checks,
            "similarities": similarities, "alternatives": alternatives[:5], "limitations": notes,
            "candidateReason": candidate_reason, "resultReason": result_reason}


async def explain(task_id: UUID, version_id: UUID, reference_version_id: UUID, body: ExplainOutcome) -> list[Document]:
    scope = {"taskId": str(task_id), "taskVersionId": str(version_id)}
    if body.replay_id is not None:
        batch = await db.evaluation_replays.find_one({"_id": str(body.replay_id), **scope, "expiresAt": {"$gt": utcnow()}})
        item = next((item for item in (batch or {}).get("items", []) if item["runId"] == body.evaluation_id), None)
        if item is None:
            raise not_found()
        evaluation = {"_id": item["runId"], **scope, "dagName": "evaluation-replay", "dagRunId": item["runId"],
                      "modelVersionId": item["modelVersionId"], "parserModels": item.get("parserModels", [])}
        frozen = (batch or {}).get("glossaries")
        stored = await db.evaluation_replay_results.find_one({"_id": item["runId"], "batchId": str(body.replay_id), "expiresAt": {"$gt": utcnow()}})
        cached = (stored or {}).get("result", {})
    else:
        evaluation = await db.evaluations.find_one({"_id": body.evaluation_id, **scope})
        if evaluation is None:
            raise not_found()
        frozen = evaluation.get("glossarySnapshots")
        cached = evaluation.get("glossaryOutcomes") or {}
    reference = next((item for item in evaluation.get("parserModels", []) if item.get("role") == "reference"
                      and item["versionId"] == str(reference_version_id)), None)
    if reference is None:
        raise not_found()
    key = reference["key"]
    signal_set = await db.synonym_signal_sets.find_one({**scope, "referenceVersionId": str(reference_version_id),
                                                       "modelVersionId": evaluation["modelVersionId"]}) if body.replay_id is None else None
    signal = next((item for item in (signal_set or {}).get("signals", [])
                   if item["referenceElementId"] == body.reference_element_id and item["termKey"] == body.term_key), None)
    limitations, artifacts = [], {}
    try:
        run = await outcomes.run_details(evaluation)
    except ApiError as error:
        limitations.append("The original workflow run could not be loaded. " + error.message)
    except (KeyError, TypeError, ValueError):
        limitations.append("The archived workflow run is not readable in its stored format.")
    else:
        specs = [("candidates", "match_synonyms", "candidates-result.json", "synonym-matching", "Original candidate scores"),
                 ("analysis", "generate_analytical_feedback", "analysis-result.json", "analytical-feedback", "Identity analysis"),
                 ("feedback", "generate_analytical_feedback", "feedback-result.json", "feedback-generation", "Original final-feedback file"),
                 ("comparison", "match_graphs", "comparison-result.json", "one-to-one-graph-matching", "Frozen matching rules")]
        results = await gather(*(outcomes.artifact(evaluation, run, step, key, path, capability)
                                 for _, step, path, capability, _ in specs), return_exceptions=True)
        for (name, _, _, _, label), result in zip(specs, results, strict=True):
            if isinstance(result, ApiError):
                limitations.append(f'{label} could not be loaded. {result.message}')
            elif isinstance(result, Exception):
                limitations.append(f'{label} is not readable in this historical result.')
            elif result.get("pair", {}).get("referenceKey") != key:
                limitations.append(f'{label} refers to a different sample solution and was excluded.')
            else:
                artifacts[name] = result
    archived = next((item["recognition"] for item in (evaluation.get("studentFeedback") or {}).get("recognitions", [])
                     if item["referenceKey"] == key), None)
    if archived is not None:
        if "feedback" not in artifacts:
            artifacts["feedback"] = {"recognition": archived}
            limitations.append("Final learner recognition was recovered from the archived learner result.")
        elif recognition_of(artifacts["feedback"]) != archived:
            artifacts["feedback"] = {"recognition": archived}
            limitations.append("The feedback file differs from the archived learner result. The archived learner recognition is used for verification.")
    pairs = candidate_pairs(artifacts.get("candidates", {}))
    selected = [pair for pair in pairs if pair["referenceElementId"] == body.reference_element_id
                and term_key(pair["submissionLabel"]) == body.term_key
                and (body.submission_element_id is None or pair["submissionElementId"] == body.submission_element_id)]
    if not selected:
        selected = [{"referenceElementId": body.reference_element_id, "referenceLabel": body.reference_element_id,
                     "submissionElementId": body.submission_element_id, "submissionLabel": (signal or {}).get("term", body.term_key), "scores": {}}]
        limitations.append("No original candidate record is available for this exact pair.")
    glossary = frozen.get(key, {}) if frozen is not None else None
    cached_terms = [term for ref in cached.get("references", []) if ref["referenceVersionId"] == str(reference_version_id)
                    for term in ref["terms"] if term["referenceElementId"] == body.reference_element_id and term["termKey"] == body.term_key]
    explanations = [explain_pair(pair, pairs, artifacts.get("analysis", {}), artifacts.get("feedback", {}),
                                  artifacts.get("comparison", {}), glossary, limitations,
                                  next((term["state"] for term in cached_terms if term["submissionElementId"] == pair.get("submissionElementId")), None))
                    for pair in selected]
    if signal is not None:
        for explanation in explanations:
            explanation["candidateReason"] = {
                "context_unique": "It is the only remaining term in a matching part of the model.",
                "context_best": "Its wording is similar and it appears in a related part of the model.",
                "text_only": "Its wording is similar to the reference name; the model context does not confirm the meaning.",
            }.get(signal["evidence"], explanation["candidateReason"])
            explanation["checks"].append({"method": "suggestion_context", "result": "informational", "role": "suggestion",
                "note": {"context_unique": "The term was unique in its context.", "context_best": "The pair was the mutually strongest text candidate in its context.", "text_only": "The suggestion is based on text similarity only."}.get(signal["evidence"], "A glossary suggestion was recorded.")
                    + " Context: " + {"owner": "owning element", "neighbors": "recognized neighbors", "endpoints": "connection endpoints", "none": "no structural context"}.get(signal["contextBasis"], signal["contextBasis"])
                    + ". This proposes a glossary term and does not confirm recognition in the original evaluation."})
            if not any(item["score"] is not None for item in explanation["similarities"]):
                explanation["similarities"] = [{"method": method, "score": score, "thresholds": {}, "confirmationFloors": {}}
                                               for method, score in signal.get("scores", {}).items()]
                explanation["limitations"].append("These scores come from the stored glossary suggestion. The original evaluation's thresholds and pair decision cannot be inferred from them.")
    return explanations
