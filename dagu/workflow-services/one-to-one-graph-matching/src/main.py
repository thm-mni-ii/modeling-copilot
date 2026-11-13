#!/usr/bin/env python3
"""Produce an initial, provisional comparison for one validated model pair."""
import os
from pathlib import Path
import sys

from artifacts import content_hash, read_artifacts
from assignment_capacity import analyze_proposal_feasibility
from correspondence_state import build_provisional_state
from initial_evaluation import evaluate_initial_coverage
from initial_recognition import evaluate_connections, propose_connections, recognition_metrics
from initial_structure import evaluate_containment_relations, evaluate_provisional_owners
from semantic_refinement import refine_semantic_proposals
import workflow_io
from workflow_io import Workspace, workspace, write_output

SERVICE = "one-to-one-graph-matching"


def run(store: Workspace, reference_key: str | None) -> dict:
    bundle, graphs, indices, candidates = read_artifacts(store, reference_key)
    state = build_provisional_state(indices, candidates)
    evaluation = evaluate_initial_coverage(indices, state)
    graph_matching = bundle["comparisonConfig"].get("graphMatching", {})
    if not isinstance(graph_matching, dict):
        raise ValueError("comparisonConfig.graphMatching must be an object")
    semantics = refine_semantic_proposals(
        indices, candidates, state, graph_matching.get("minimumSimilarity", {}),
    )
    semantic_proposals = semantics["proposals"]
    evaluation["mapping"]["provisionalElements"].extend(
        {**item, "status": "provisional"} for item in semantic_proposals
    )
    evaluation["mapping"]["provisionalElements"].sort(key=lambda item: (item["referenceId"], item["studentId"]))
    evaluation["unresolvedReferenceIds"] = sorted(
        set(evaluation["unresolvedReferenceIds"]) - {item["referenceId"] for item in semantic_proposals}
    )
    evaluation["unresolvedStudentIds"] = sorted(
        set(evaluation["unresolvedStudentIds"]) - {item["studentId"] for item in semantic_proposals}
    )
    if semantic_proposals:
        evaluation["proposalFeasibility"] = analyze_proposal_feasibility({
            **state, "proposals": state["proposals"] + semantic_proposals,
        })
    reference_count = evaluation["metrics"]["overall"]["referenceCount"]
    evaluation["metrics"]["semanticProposalCoverage"] = {
        "referenceCount": reference_count,
        "additionalProposalCount": len(semantic_proposals),
        "coverage": len(semantic_proposals) / reference_count if reference_count else None,
    }
    evaluation["semanticRefinement"] = semantics
    connections = propose_connections(indices, evaluation["mapping"]["provisionalElements"])
    evaluation["mapping"]["provisionalConnections"] = connections["proposals"]
    evaluation["unresolvedReferenceConnectionIds"] = connections["unresolvedReferenceIds"]
    evaluation["unresolvedStudentConnectionIds"] = connections["unresolvedStudentIds"]
    evaluation["metrics"]["provisionalRecognition"] = recognition_metrics(
        indices, evaluation["mapping"]["provisionalElements"], connections,
        graph_matching.get("elementCategories", []),
    )
    evaluation["provisionalConnectionStructure"] = evaluate_connections(
        indices, evaluation["mapping"]["provisionalElements"],
    )
    structure = evaluate_provisional_owners(indices, candidates, evaluation["mapping"]["provisionalElements"])
    evaluation["metrics"]["provisionalOwnerConsistency"] = structure["metrics"]
    evaluation["provisionalOwnerEvidence"] = structure["pairs"]
    containment = evaluate_containment_relations(indices, evaluation["mapping"]["provisionalElements"])
    evaluation["metrics"]["provisionalContainment"] = containment["metrics"]
    evaluation["provisionalContainmentEvidence"] = containment["relations"]
    source_dir = Path(__file__).parent
    resources = {"src/workflow_io.py": Path(workflow_io.__file__)}
    resources.update({
        f"src/{path.relative_to(source_dir).as_posix()}": path for path in source_dir.rglob("*.py")
    })
    producer = {
        "service": SERVICE,
        "version": "0.1.0",
        "resourceHash": content_hash({name: path.read_text(encoding="utf-8") for name, path in resources.items()}),
    }
    incomplete = (candidates["completeness"]["interpretation"] == "partial"
                  or any(data["completeness"]["interpretation"] == "partial" for data in graphs.values())
                  or any(node["kind"] == "modelElement" and (
                      node["comparisonRole"] != "semantic" or node["languageResolution"] != "resolved"
                  ) for index in indices.values() for node in index.nodes.values()))
    result = {
        "schema": "reference-comparison/v1",
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
        write_output(run(store, os.environ.get("REFERENCE_KEY")))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"[{SERVICE}] invalid input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
