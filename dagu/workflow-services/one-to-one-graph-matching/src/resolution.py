"""Repeat the proposal phases until a round accepts no new pair (AP-03).

Decisions are monotone: a round only adds pairs, so the loop ends by itself. Every accepted pair
reserves both elements, which removes all other candidates of these elements in the next round
(early elimination). Hints never enter this loop; they are derived afterwards and never reserve.
"""

from copy import deepcopy

from correspondence_state import finish_state, initial_state, run_structural_phases
from semantic_refinement import refine_semantic_proposals

SNAPSHOT_FIELDS = ("childOwnerEvidence", "combinedChildEvidence")


def resolve(indices, candidates, graphs, graph_matching, glossary):
    """Return the final state (all accepted pairs), the semantic refinement and the number of rounds."""
    state, context = initial_state(indices, candidates, graphs=graphs)
    thresholds = graph_matching.get("minimumSimilarity", {})
    text_evidence = graph_matching.get("textEvidence")
    semantic_ids, semantic_events, semantics, rounds = set(), {}, None, 0
    while True:
        rounds += 1
        snapshot = {field: deepcopy(state.get(field)) for field in SNAPSHOT_FIELDS}
        event_count = len(context["events"])
        added = run_structural_phases(candidates, state, context)
        refined = refine_semantic_proposals(indices, candidates, state, thresholds,
                                            text_evidence=text_evidence, glossary=glossary)
        added += refined["proposals"]
        if semantics is not None and not added:
            # A round without a new pair must not alter what the previous rounds established.
            state.update(snapshot)
            del context["events"][event_count:]
            break
        state["proposals"].extend(refined["proposals"])
        semantic_ids |= {(item["referenceId"], item["studentId"]) for item in refined["proposals"]}
        semantic_events.update({item["id"]: item for item in refined["decisionEvents"]})
        for item in added:
            item.setdefault("round", rounds)
        for item in state["proposals"]:
            item.setdefault("round", rounds)
        semantics = refined
        if not added:
            break
    semantics = {**semantics,
                 "proposals": sorted((item for item in state["proposals"] if (item["referenceId"], item["studentId"]) in semantic_ids),
                                     key=lambda item: (item["referenceId"], item["studentId"])),
                 "decisionEvents": sorted(semantic_events.values(), key=lambda item: item["id"])}
    return finish_state(state, context), semantics, rounds
