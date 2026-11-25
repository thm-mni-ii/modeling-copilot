"""Repeat the proposal phases until a round accepts no new pair (AP-03).

Decisions are monotone: a round only adds pairs, so the loop ends by itself. Every accepted pair
reserves both elements, which removes all other candidates of these elements in the next round
(early elimination). Hints never enter this loop; they are derived afterwards and never reserve.
"""

from copy import deepcopy

from context_evidence import context_proposals, interchangeable_proposals, neighbor_proposals
from correspondence_state import accept_proposals, finish_state, initial_state, reserved_ids, run_structural_phases
from artifacts import _key
from identity_evidence import normalized
from semantic_refinement import refine_semantic_proposals
from text_similarity import configured_tiers, pair_similarity, with_glossary

SNAPSHOT_FIELDS = ("childOwnerEvidence", "combinedChildEvidence")
EXACT_AFTER_CONTEXT = "exact_label_after_context"


def resolve(indices, candidates, graphs, graph_matching, glossary):
    """Return the final state (all accepted pairs), the semantic refinement and the number of rounds."""
    thresholds = graph_matching.get("minimumSimilarity", {})
    text_evidence = graph_matching.get("textEvidence")
    tiers = with_glossary(configured_tiers(candidates, {"minimumSimilarity": thresholds,
                                                        **({"textEvidence": text_evidence} if text_evidence is not None else {})}), glossary)
    similarity = pair_similarity(candidates, tiers, glossary) if tiers else {}
    exact = {(row["referenceElementId"], match["submissionElementId"]) for row in candidates["synonymMatrix"] for match in row["matches"]
             if normalized(row["referenceLabel"]) and normalized(row["referenceLabel"]) == normalized(match["submissionLabel"])}

    def text_ok(pair):
        return pair in exact or similarity.get(pair, {}).get("status") == "supported"
    contested = contested_exact_pairs(indices, candidates, exact, text_ok)
    state, context = initial_state(indices, candidates, graphs=graphs, contested=contested)
    semantic_ids, semantic_events, semantics, rounds = set(), {}, None, 0
    while True:
        rounds += 1
        snapshot = {field: deepcopy(state.get(field)) for field in SNAPSHOT_FIELDS}
        event_count = len(context["events"])
        added = run_structural_phases(candidates, state, context)
        refined = refine_semantic_proposals(indices, candidates, state, thresholds,
                                            text_evidence=text_evidence, glossary=glossary)
        added += refined["proposals"]
        # Graph context after text: first where it decides between text candidates (GM-47), then without text (GM-48).
        current = lambda: state | {"proposals": state["proposals"] + refined["proposals"]}
        phases = ((lambda: context_proposals(indices, current(), _reserved(state, refined), text_ok), False),
                  (lambda: neighbor_proposals(indices, current(), _reserved(state, refined)), False),
                  # GM-51: weaker duplicate rules only when nothing stronger is left, so they never preempt it.
                  (lambda: context_proposals(indices, current(), _reserved(state, refined), text_ok, loose=True), True),
                  # GM-52: context could not decide, so the exact label does.
                  (lambda: exact_after_context(_reserved(state, refined), contested), True),
                  (lambda: interchangeable_proposals(indices, current(), _reserved(state, refined), text_ok), True))
        for phase, fallback in phases:
            if fallback and added:
                break
            structural = accept_proposals(current(), phase(), context["events"])
            state["proposals"].extend(structural)
            added += structural
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


def contested_exact_pairs(indices, candidates, exact, text_ok):
    """GM-52: exact pairs whose reference element has another text-supported candidate of the same kind.

    Synonyms count like the exact label, so the graph context decides between them; a rival that matches
    another reference element exactly is that element's candidate, not a rival. Only a one-to-one exact
    label is deferred: a repeated one never anchored up front, so the context already decides there.
    """
    reference, student = indices["reference"].nodes, indices["student"].nodes
    elements = lambda r, s: reference[r]["kind"] == student[s]["kind"] == "modelElement" and _key(reference[r]) == _key(student[s])
    exact_students = {s for _, s in exact}
    rivals = {(row["referenceElementId"], match["submissionElementId"]) for row in candidates["synonymMatrix"] for match in row["matches"]
              if text_ok((row["referenceElementId"], match["submissionElementId"]))}
    unique = lambda r, s: sum(other[0] == r for other in exact) == 1 and sum(other[1] == s for other in exact) == 1
    return frozenset((r, s) for r, s in exact if elements(r, s) and unique(r, s) and any(
        other_r == r and other_s != s and other_s not in exact_students and elements(r, other_s) for other_r, other_s in rivals))


def exact_after_context(reserved, contested):
    used_ref, used_sub = reserved
    return [{"referenceId": r, "studentId": s, "reason": EXACT_AFTER_CONTEXT, "dependsOn": []}
            for r, s in sorted(contested) if r not in used_ref and s not in used_sub
            and sum(other[0] == r for other in contested) == 1 and sum(other[1] == s for other in contested) == 1]


def _reserved(state, refined):
    used_ref, used_sub = reserved_ids(state)
    return (used_ref | {item["referenceId"] for item in refined["proposals"]},
            used_sub | {item["studentId"] for item in refined["proposals"]})
