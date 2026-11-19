"""Adapter from synonym-matching scores to tiered threshold evidence; no correspondence choice.

A tier is a named group of per-method minimum similarities. Tiers are ordered by
evidence strength; a pair belongs to the first tier in which any of its methods
reaches the threshold. The legacy `minimumSimilarity` object is a single tier.
"""

import math
import re

LEGACY_TIER = "minimumSimilarity"
# Character-level comparators; a near spelling only counts as a typo if both labels start alike.
CHARACTER_METHODS = {"levenshtein", "levenshtein_canonical", "damerau_canonical", "jaro_winkler", "char_trigram"}
UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _start(label):
    return re.sub(r"[\W_]+", "", label.casefold().translate(UMLAUTS))[:2]


def text_veto(reference_label, student_label):
    """Guards for tiered text evidence: differing numbers on both sides, or a different word start."""
    reference_digits, student_digits = re.findall(r"\d+", reference_label), re.findall(r"\d+", student_label)
    if reference_digits and student_digits and reference_digits != student_digits:
        return "digit_mismatch"
    # Typos rarely hit the first letters; real-word neighbours do (VersuchsNr./BesuchsNr.).
    if _start(reference_label) != _start(student_label):
        return "start_mismatch"
    return None


def configured_thresholds(candidates, thresholds):
    """Validate per-method minimum similarities against the published score ranges."""
    if not isinstance(thresholds, dict):
        raise ValueError("graphMatching.minimumSimilarity must be an object")
    if not thresholds:
        return {}
    methods ={method["name"]: method["scoreRange"] for method in candidates["methods"]}
    for name, value in thresholds.items():
        if name not in methods:
            raise ValueError(f"minimum similarity references unknown method: {name}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"minimum similarity must be finite: {name}")
        lower, upper = methods[name]
        if not lower <= value <= upper:
            raise ValueError(f"minimum similarity outside score range: {name}")
    return dict(sorted(thresholds.items()))


def configured_tiers(candidates, graph_matching):
    """Resolve the ordered tier policy; `{}` and no tiers mean `not_configured`."""
    if not isinstance(graph_matching, dict):
        raise ValueError("comparisonConfig.graphMatching must be an object")
    legacy = graph_matching.get("minimumSimilarity", {})
    text_evidence = graph_matching.get("textEvidence")
    if text_evidence is None:
        thresholds = configured_thresholds(candidates, legacy)
        return [{"name": LEGACY_TIER, "minimumSimilarity": thresholds}] if thresholds else []
    if legacy:
        raise ValueError("graphMatching.minimumSimilarity and textEvidence are mutually exclusive")
    if not isinstance(text_evidence, dict) or set(text_evidence) != {"tiers"}:
        raise ValueError("graphMatching.textEvidence must be an object with tiers only")
    tiers = text_evidence["tiers"]
    if not isinstance(tiers, list) or not tiers:
        raise ValueError("graphMatching.textEvidence.tiers must be a non-empty array")
    resolved, names = [], set()
    for tier in tiers:
        if not isinstance(tier, dict) or not {"name", "minimumSimilarity"} <= set(tier) <= {"name", "minimumSimilarity", "confirmationFloor"}:
            raise ValueError("each text evidence tier needs name and minimumSimilarity, optionally confirmationFloor")
        name = tier["name"]
        if not isinstance(name, str) or not name or name in names or name == LEGACY_TIER:
            raise ValueError("text evidence tier names must be unique non-empty strings")
        names.add(name)
        thresholds = configured_thresholds(candidates, tier["minimumSimilarity"])
        if not thresholds:
            raise ValueError(f"text evidence tier needs at least one method: {name}")
        floor = configured_thresholds(candidates, tier.get("confirmationFloor", {}))
        if any(method not in thresholds or value > thresholds[method] for method, value in floor.items()):
            raise ValueError(f"confirmationFloor must name tier methods below their threshold: {name}")
        resolved.append({"name": name, "minimumSimilarity": thresholds, **({"confirmationFloor": floor} if floor else {})})
    return resolved


def tier_methods(tiers):
    return sorted({name for tier in tiers for name in tier["minimumSimilarity"]})


def _tier_verdict(tiers, scores):
    for index, tier in enumerate(tiers):
        supported = sorted(name for name, threshold in tier["minimumSimilarity"].items()
                           if name in scores and scores[name] >= threshold)
        if supported:
            return index, supported, None
    # Below every threshold but above a tier's floor: text alone does not decide, structure may confirm.
    grey = next((index for index, tier in enumerate(tiers)
                 if any(name in scores and scores[name] >= value
                        for name, value in tier.get("confirmationFloor", {}).items())), None)
    return None, [], grey


def pair_similarity(candidates, tiers):
    """Classify every admissible element pair as supported, below_threshold or unavailable.

    Supported pairs carry the rank and name of their strongest tier; a lower rank is stronger.
    """
    ranges = {method["name"]: method["scoreRange"] for method in candidates["methods"]}
    methods = tier_methods(tiers)
    legacy = bool(legacy_thresholds(tiers))
    pairs = {}
    for row in candidates["synonymMatrix"]:
        for match in row["matches"]:
            pair = (row["referenceElementId"], match["submissionElementId"])
            scores = match.get("scores") if match.get("scoreStatus") == "scored" else None
            available = {}
            for name in methods:
                score = scores.get(name) if isinstance(scores, dict) else None
                if score is None:
                    continue
                if (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
                        or not ranges[name][0] <= score <= ranges[name][1]):
                    raise ValueError(f"invalid candidate score: {name}")
                available[name] = score
            # Guards apply to tiered text evidence only; the legacy single threshold stays reproducible.
            veto = None if legacy else text_veto(row["referenceLabel"], match["submissionLabel"])
            usable = ({} if veto == "digit_mismatch" else
                      {name: score for name, score in available.items() if name not in CHARACTER_METHODS}
                      if veto == "start_mismatch" else available)
            rank, supported, grey = _tier_verdict(tiers, usable)
            if veto and (rank, supported, grey) == _tier_verdict(tiers, available):
                veto = None  # report a guard only where it changed the verdict
            status = ("supported" if rank is not None else
                      "below_threshold" if methods and len(available) == len(methods) else "unavailable")
            pairs[pair] = {"status": status, "scoreStatus": match.get("scoreStatus", "unavailable"),
                           "supportingMethods": supported, "scores": available,
                           "tier": tiers[rank]["name"] if rank is not None else None, "tierRank": rank, "greyRank": grey, "veto": veto}
    return pairs


def legacy_thresholds(tiers):
    """The single-tier `minimumSimilarity` view that downstream checks compare with the frozen config."""
    return tiers[0]["minimumSimilarity"] if len(tiers) == 1 and tiers[0]["name"] == LEGACY_TIER else {}
