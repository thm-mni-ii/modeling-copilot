#!/usr/bin/env python3
"""Produce an initial, provisional comparison for one validated model pair."""
import os
from pathlib import Path
import sys

from artifacts import content_hash, read_artifacts
from facts import evaluate_facts
from hints import derive_hints, hint_config
from identity_evidence import evaluate_identity
from initial_evaluation import evaluate_initial_coverage, evaluate_type_comparison
from initial_recognition import evaluate_connections, propose_connections, recognition_metrics
from initial_structure import evaluate_containment_relations, evaluate_provisional_owners
from resolution import resolve
from text_similarity import configured_tiers, glossary_decisions, pair_similarity, validate_matching_sources, with_glossary
import workflow_io
from workflow_io import Workspace, workspace, write_output

SERVICE = "one-to-one-graph-matching"


def run(store: Workspace, reference_key: str | None, *, include_diagnostics=False) -> dict:
    bundle, graphs, indices, candidates = read_artifacts(store, reference_key)
    graph_matching = bundle["comparisonConfig"].get("graphMatching", {})
    if not isinstance(graph_matching, dict):
        raise ValueError("comparisonConfig.graphMatching must be an object")
    validate_matching_sources(candidates, graph_matching, reference_key)
    glossary = glossary_decisions(graph_matching, candidates["pair"]["referenceKey"])
    state, semantics, rounds = resolve(indices, candidates, graphs, graph_matching, glossary)
    semantic_proposals = semantics["proposals"]
    evaluation = evaluate_initial_coverage(indices, state)
    evaluation["childOwnerEvidence"] = state["childOwnerEvidence"]
    reference_count = evaluation["metrics"]["overall"]["referenceCount"]
    evaluation["metrics"]["semanticProposalCoverage"] = {
        "referenceCount": reference_count,
        "additionalProposalCount": len(semantic_proposals),
        "coverage": len(semantic_proposals) / reference_count if reference_count else None,
    }
    evaluation["semanticRefinement"] = semantics
    connections = propose_connections(indices, evaluation["mapping"]["provisionalElements"], candidates, glossary, graph_matching)
    evaluation["mapping"]["provisionalConnections"] = connections["proposals"]
    evaluation["decisionEvents"] = sorted(
        state["decisionEvents"] + semantics["decisionEvents"] + connections["decisionEvents"],
        key=lambda item: item["id"],
    )
    evaluation["unresolvedReferenceConnectionIds"] = connections["unresolvedReferenceIds"]
    evaluation["unresolvedStudentConnectionIds"] = connections["unresolvedStudentIds"]
    if include_diagnostics:
        evaluation["provisionalTypeComparison"] = evaluate_type_comparison(
            indices, evaluation["mapping"]["provisionalElements"], connections["proposals"],
        )
        evaluation["metrics"]["provisionalRecognition"] = recognition_metrics(
            indices, evaluation["mapping"]["provisionalElements"], connections,
            graph_matching.get("elementCategories", []),
        )
    evaluation["provisionalConnectionStructure"] = evaluate_connections(
        indices, evaluation["mapping"]["provisionalElements"],
    )
    if include_diagnostics:
        structure = evaluate_provisional_owners(indices, candidates, evaluation["mapping"]["provisionalElements"])
        evaluation["metrics"]["provisionalOwnerConsistency"] = structure["metrics"]
        evaluation["provisionalOwnerEvidence"] = structure["pairs"]
    containment = evaluate_containment_relations(indices, evaluation["mapping"]["provisionalElements"])
    evaluation["metrics"]["provisionalContainment"] = containment["metrics"]
    evaluation["provisionalContainmentEvidence"] = containment["relations"]
    evaluation["identityEvidence"] = evaluate_identity(
        indices, candidates, evaluation["mapping"]["provisionalElements"],
        combined=state["combinedChildEvidence"],
        connection_pairs=connections["proposals"],
        connection_candidates=connections["candidateEvidence"],
        minimum_similarity=semantics["minimumSimilarity"],
        text_evidence=semantics.get("textEvidence"), glossary=glossary,
        label_conflicts={(item["referenceId"], item["studentId"]) for item in state["conflictingProposals"]
                         if item.get("conflictReason") == "label_structure_conflict"},
    )
    evaluation["pairDecisions"] = evaluation["identityEvidence"].pop("decisions")
    evaluation["decisionRounds"] = rounds
    tiers = with_glossary(configured_tiers(candidates, {
        "minimumSimilarity": semantics["minimumSimilarity"],
        **({"textEvidence": semantics["textEvidence"]} if "textEvidence" in semantics else {})}), glossary)
    evaluation["hints"] = derive_hints(
        indices, candidates, evaluation["identityEvidence"]["pairs"],
        pair_similarity(candidates, tiers, glossary) if tiers else {}, tiers,
        state["combinedChildEvidence"], hint_config(graph_matching))
    hinted = {(item["referenceId"], item["studentId"]) for item in evaluation["hints"]["items"]}
    for row in evaluation["identityEvidence"]["pairs"]:
        row["zone"] = ("certain" if row["status"] == "uniquely_supported" else
                       "hint" if (row["referenceId"], row["studentId"]) in hinted else "open")
    evaluation["propertyFacts"] = evaluate_facts(indices, evaluation, graphs, candidates, {
        side: store.read(candidates["inventoryPaths"][side])["result"] for side in indices
    })
    semantic_configuration = {key: semantics[key] for key in ("configurationStatus", "minimumSimilarity", "textEvidence")
                              if key in semantics}
    diagnostics = {key: value for key, value in evaluation.items() if key not in (
        "mapping", "propertyFacts", "pairDecisions", "decisionRounds", "hints", "unresolvedReferenceIds", "unresolvedStudentIds",
        "unresolvedReferenceConnectionIds", "unresolvedStudentConnectionIds")}
    evaluation = {key: value for key, value in evaluation.items() if key not in diagnostics}
    source_dir = Path(__file__).parent
    resources = {"src/workflow_io.py": Path(workflow_io.__file__)}
    resources.update({
        f"src/{path.relative_to(source_dir).as_posix()}": path for path in source_dir.rglob("*.py")
    })
    producer = {
        "service": SERVICE,
        "version": "2.16.0",
        "resourceHash": content_hash({name: path.read_text(encoding="utf-8") for name, path in resources.items()}),
    }
    incomplete = (candidates["completeness"]["interpretation"] == "partial"
                  or any(data["completeness"]["interpretation"] == "partial" for data in graphs.values())
                  or any(node["kind"] == "modelElement" and (
                      node["comparisonRole"] != "semantic" or node["languageResolution"] != "resolved"
                  ) for index in indices.values() for node in index.nodes.values()))
    result = {
        "schema": "reference-comparison/v2",
        "status": "partial",
        "assessmentAvailable": False,
        "evaluationId": bundle["evaluationId"],
        "inputHash": bundle["inputHash"],
        "pair": candidates["pair"],
        "sources": {side: data["source"] for side, data in graphs.items()},
        "graphHashes": {side: data["graphHash"] for side, data in graphs.items()},
        "languageResources": {side: data["languageResources"] for side, data in graphs.items()},
        "inventoryHashes": candidates["inventoryHashes"],
        "candidateHash": candidates["candidateHash"],
        "producer": producer,
        **evaluation,
        "semanticConfiguration": semantic_configuration,
        **({"diagnostics": {"purpose": "development_only", **diagnostics}} if include_diagnostics else {}),
        "completeness": {
            "technical": "complete",
            "interpretation": "partial" if incomplete else "complete",
            "matching": "provisional",
            "structuralComparison": "provisional_owner_and_connections",
        },
    }
    result["comparisonHash"] = content_hash(result)
    return {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "match",
            "capability": SERVICE, "summary": "Vorläufige Ankerabdeckung und Zugehörigkeitskonsistenz",
            "result": result}


def main() -> int:
    try:
        store = workspace()
        write_output(run(store, os.environ.get("REFERENCE_KEY"), include_diagnostics=os.environ.get("GRAPH_MATCHING_DIAGNOSTICS") == "1"))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
