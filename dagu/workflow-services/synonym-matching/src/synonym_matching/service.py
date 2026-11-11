"""Compute full, unrounded candidate evidence for exactly one inventory pair."""

import numpy as np

from .combinations import combine, describe
from .methods.char_trigram import compute as char_trigram
from .methods.jaro_winkler import compute as jaro_winkler
from .methods.levenshtein import compute as levenshtein
from .methods.multilingual import MultilingualMethod
from .preprocessing import normalize


def compare_pair(inventories, config):
    elements = {side: sorted(data["elements"], key=lambda item: item["id"])
                for side, data in inventories.items()}
    usable = {side: [element for element in items if element["labelStatus"] == "present"]
              for side, items in elements.items()}
    texts = {side: [normalize(element["matchText"]) for element in items] for side, items in usable.items()}
    if any(not text for values in texts.values() for text in values):
        raise ValueError("normalization made a declared usable text empty")
    left, right = texts["reference"], texts["student"]
    embedding = MultilingualMethod(config["embedding"]["multilingual"])
    scores = {"levenshtein": levenshtein(left, right), "jaro_winkler": jaro_winkler(left, right),
              "char_trigram": char_trigram(left, right), "multilingual": embedding.compute(left, right)}
    shape = (len(left), len(right))
    methods = []
    for name, matrix in scores.items():
        minimum = -1 if name == "multilingual" else 0
        if (matrix.shape != shape or not np.isfinite(matrix).all()
                or (matrix < minimum).any() or (matrix > 1).any()):
            raise ValueError(f"invalid score matrix from {name}")
        methods.append({"name": name, "rawScoreRange": [minimum, 1], "combinationContributionRange": [0, 1],
                        "contributesToCombination": True})
    combined = combine(scores, config["combiner"])
    if combined.shape != shape or not np.isfinite(combined).all() or (combined < 0).any() or (combined > 1).any():
        raise ValueError("invalid combined score matrix")

    rows = {}
    for row_index, reference in enumerate(usable["reference"]):
        order = sorted(range(len(right)), key=lambda column: (-combined[row_index, column], usable["student"][column]["id"]))
        rows[reference["id"]] = [
            {"submissionElementId": usable["student"][column]["id"],
             "scores": {name: float(matrix[row_index, column]) for name, matrix in scores.items()},
             "combinedScore": float(combined[row_index, column]), "aliasEvidence": []}
            for column in order
        ]
    matrix = [{"referenceElementId": element["id"], "matches": rows.get(element["id"], [])}
              for element in elements["reference"]]
    unscored = [{"side": side, "id": element["id"],
                 "reason": "missing_text" if element["labelStatus"] == "missing" else "unsupported_text"}
                for side, items in elements.items() for element in items if element["labelStatus"] != "present"]
    processed = {side: [{"id": element["id"], "texts": {name: text for name in scores}}
                        for element, text in zip(items, texts[side], strict=True)] for side, items in usable.items()}
    return {"synonymMatrix": matrix, "unscoredElements": unscored, "processedTexts": processed,
            "evaluatedPairCount": len(left) * len(right), "methods": methods, "combiner": describe(config["combiner"]),
            "resources": {"multilingual": embedding.resource_metadata()}}
