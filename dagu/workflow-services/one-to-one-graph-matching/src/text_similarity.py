"""Adapter from synonym-matching scores to threshold evidence; no correspondence choice."""

import math


def configured_thresholds(candidates, thresholds):
    """Validate per-method minimum similarities against the published score ranges."""
    if not isinstance(thresholds, dict):
        raise ValueError("graphMatching.minimumSimilarity must be an object")
    methods = {method["name"]: method["scoreRange"] for method in candidates["methods"]}
    for name, value in thresholds.items():
        if name not in methods:
            raise ValueError(f"minimum similarity references unknown method: {name}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"minimum similarity must be finite: {name}")
        lower, upper = methods[name]
        if not lower <= value <= upper:
            raise ValueError(f"minimum similarity outside score range: {name}")
    return dict(sorted(thresholds.items()))


def pair_similarity(candidates, thresholds):
    """Classify every admissible element pair as supported, below_threshold or unavailable."""
    thresholds = configured_thresholds(candidates, thresholds)
    ranges = {method["name"]: method["scoreRange"] for method in candidates["methods"]}
    pairs = {}
    for row in candidates["synonymMatrix"]:
        for match in row["matches"]:
            pair = (row["referenceElementId"], match["submissionElementId"])
            scores = match.get("scores") if match.get("scoreStatus") == "scored" else None
            available = {}
            for name in thresholds:
                score = scores.get(name) if isinstance(scores, dict) else None
                if score is None:
                    continue
                if (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
                        or not ranges[name][0] <= score <= ranges[name][1]):
                    raise ValueError(f"invalid candidate score: {name}")
                available[name] = score
            supported = sorted(name for name, score in available.items() if score >= thresholds[name])
            status = ("supported" if supported else
                      "below_threshold" if thresholds and len(available) == len(thresholds) else "unavailable")
            pairs[pair] = {"status": status, "scoreStatus": match.get("scoreStatus", "unavailable"),
                           "supportingMethods": supported, "scores": available}
    return thresholds, pairs
