"""Hints: positive but insufficient evidence for learners; never counted, never evidence (AP-05 to AP-09).

Hints are derived after every identity decision from read-only inputs. They never enter proposals,
`dependsOn`, facts or eliminations, so mapping and recognition are identical with and without them.
Every parameter comes from the frozen `comparisonConfig.graphMatching.hints`.
"""

import math
from collections import defaultdict

from artifacts import content_hash
from correspondence_state import _neighbors
from text_similarity import GLOSSARY_TIER, GLOSSARY_VETO
from word_parts import relation, vocabulary

CONFIG_KEYS = {"textBand": float, "minimumNeighbors": int, "minimumChildren": int, "showReferenceText": bool}
SOURCES = ("text_band", "neighbor_profile", "child_overlap")


def hint_config(graph_matching):
    """The frozen hint parameters, or None when the evaluation input predates hints."""
    config = graph_matching.get("hints")
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) != set(CONFIG_KEYS):
        raise ValueError(f"graphMatching.hints requires exactly {', '.join(sorted(CONFIG_KEYS))}")
    for key, kind in CONFIG_KEYS.items():
        value = config[key]
        if kind is bool:
            valid = type(value) is bool
        elif kind is int:
            valid = type(value) is int and value >= 1
        else:
            valid = type(value) in (int, float) and math.isfinite(value) and 0 <= value < 1
        if not valid:
            raise ValueError(f"invalid graphMatching.hints.{key}")
    return dict(config)


def _criterion(row, method):
    return next((item for item in row["criteria"] if item["method"] == method), {})


def derive_hints(indices, candidates, rows, similarity, tiers, combined, config):
    """Collect hints per open element pair; pairs whose hints contradict each other are withdrawn."""
    if config is None:
        return {"configurationStatus": "not_configured", "items": [], "withdrawnCount": 0}
    reference_nodes = indices["reference"].nodes
    rows = {(row["referenceId"], row["studentId"]): row for row in rows
            if reference_nodes[row["referenceId"]]["kind"] == "modelElement"}
    certain = {pair for pair, row in rows.items() if row["status"] == "uniquely_supported"}
    certain_ref, certain_sub = {r for r, _ in certain}, {s for _, s in certain}
    open_pairs = {pair: row for pair, row in rows.items() if pair[0] not in certain_ref and pair[1] not in certain_sub
                  and _criterion(row, "type_compatibility").get("result") == "satisfied"
                  and similarity.get(pair, {}).get("veto") not in ("digit_mismatch", GLOSSARY_VETO)}
    labels = {(row["referenceElementId"], match["submissionElementId"]): (row["referenceLabel"], match["submissionLabel"])
              for row in candidates["synonymMatrix"] for match in row["matches"]}
    words = vocabulary(text for pair in labels.values() for text in pair)
    neighbors = {side: _neighbors(index) for side, index in indices.items()}
    to_reference = {s: r for r, s in certain}

    def support(pair):
        """Certain neighbour pairs that connect to both elements of the pair."""
        return {(to_reference[n], n) for n in neighbors["student"][pair[1]]
                if to_reference.get(n) in neighbors["reference"][pair[0]]}

    found = defaultdict(dict)
    _text_band(open_pairs, similarity, tiers, config, labels, words, support, found)
    _neighbor_profile(open_pairs, similarity, config, support, found)
    _child_overlap(open_pairs, combined, config, found)
    by_reference, by_student = defaultdict(set), defaultdict(set)
    for pair in found:
        by_reference[pair[0]].add(pair)
        by_student[pair[1]].add(pair)
    # Two hints for one element would contradict each other; a hint must be a single safe suggestion.
    contradicting = {pair for pair in found if len(by_reference[pair[0]]) > 1 or len(by_student[pair[1]]) > 1}
    items = []
    for pair in sorted(found.keys() - contradicting):
        reference_label, student_label = labels.get(pair, (None, None))
        item = {"referenceId": pair[0], "studentId": pair[1], "kind": "label_differs",
                "sources": [source for source in SOURCES if source in found[pair]],
                "evidence": {source: found[pair][source] for source in SOURCES if source in found[pair]},
                "wordRelation": relation(reference_label, student_label, words) if reference_label and student_label else None}
        item["id"] = "hint:" + content_hash(item)
        items.append(item)
    return {"configurationStatus": "configured", "items": items, "withdrawnCount": len(contradicting)}


def _text_band(open_pairs, similarity, tiers, config, labels, words, support, found):
    """AP-06: below a tier threshold by less than the band, with context and as the only candidate."""
    band, banded = config["textBand"], {}
    for pair in open_pairs:
        text = similarity.get(pair)
        if not text or text["status"] != "below_threshold" or text["veto"]:
            continue
        hits = [{"tier": tier["name"], "method": method, "score": text["scores"][method], "threshold": threshold}
                for tier in tiers if tier["name"] != GLOSSARY_TIER for method, threshold in tier["minimumSimilarity"].items()
                if method in text["scores"] and threshold - band <= text["scores"][method] < threshold]
        if hits:
            banded[pair] = max(hits, key=lambda hit: hit["score"] - hit["threshold"])
    competing = set(banded) | {pair for pair in open_pairs if similarity.get(pair, {}).get("status") == "supported"}
    for pair, hit in banded.items():
        if any(other != pair and (other[0] == pair[0] or other[1] == pair[1]) for other in competing):
            continue
        owner = _criterion(open_pairs[pair], "identified_owner")
        if owner.get("result") == "violated":
            continue
        owner_certain = owner.get("result") == "satisfied"
        confirmed = support(pair)
        reference_label, student_label = labels.get(pair, (None, None))
        part_relation = relation(reference_label, student_label, words) if reference_label and student_label else None
        if not (owner_certain or confirmed or part_relation):
            continue
        found[pair]["text_band"] = {**hit, "band": band, "ownerIdentified": owner_certain,
                                    "confirmingNeighbors": [{"referenceId": r, "studentId": s} for r, s in sorted(confirmed)]}


def _neighbor_profile(open_pairs, similarity, config, support, found):
    """AP-07, replaces GM-18b as a mapping: certain neighbours favour one open main-element pair.

    A grey-zone text needs one confirming neighbour, no text needs `minimumNeighbors`. Any rival with at
    least as much support blocks, as does an equally supported rival with grey or supported text.
    """
    main = {pair for pair, row in open_pairs.items() if _criterion(row, "identified_owner").get("result") == "not_applicable"}
    profile = {pair: support(pair) for pair in main}
    for pair in sorted(main):
        confirmed = profile[pair]
        text = similarity.get(pair, {})
        grey = text.get("greyRank") is not None and text.get("status") != "supported"
        if len(confirmed) < (1 if grey else config["minimumNeighbors"]):
            continue
        rivals = [other for other in main if other != pair and (other[0] == pair[0] or other[1] == pair[1])]
        if any(len(profile[other]) > len(confirmed) or (len(profile[other]) == len(confirmed) and (
                not grey or similarity.get(other, {}).get("greyRank") is not None
                or similarity.get(other, {}).get("status") == "supported")) for other in rivals):
            continue
        found[pair]["neighbor_profile"] = {"greyText": grey, "rivalCount": len(rivals),
                                           "confirmingNeighbors": [{"referenceId": r, "studentId": s} for r, s in sorted(confirmed)]}


def _child_overlap(open_pairs, combined, config, found):
    """AP-08: the best child overlap of both elements.

    A closed composition that stayed open (blocked by a label conflict) competes too; excluding it would
    let a weaker pair win as the "best" one.
    """
    overlap = {}
    for row in combined:
        pair = (row["referenceId"], row["studentId"])
        union = row["expected"] + row["observed"] - row["matched"]
        if pair in open_pairs and row["matched"] >= config["minimumChildren"] and union:
            overlap[pair] = (row["matched"] / union, row)
    for pair, (value, row) in overlap.items():
        if all(other_value < value for other, (other_value, _) in overlap.items()
               if other != pair and (other[0] == pair[0] or other[1] == pair[1])):
            found[pair]["child_overlap"] = {"overlap": value, "matched": row["matched"],
                                            "expected": row["expected"], "observed": row["observed"],
                                            "minimumChildren": config["minimumChildren"]}
