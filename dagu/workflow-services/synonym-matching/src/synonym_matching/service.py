"""Compute complete candidate evidence for one inventory pair."""

import numpy as np
from numpy.typing import NDArray

from .combinations import combine, describe
from .methods.char_trigram import compute as char_trigram
from .methods.jaro_winkler import compute as jaro_winkler
from .methods.levenshtein import compute as levenshtein
from .methods.multilingual import MultilingualMethod
from .preprocessing import normalize

SCORERS = {
    "levenshtein": levenshtein,
    "jaro_winkler": jaro_winkler,
    "char_trigram": char_trigram,
}


def _language_key(element):
    language = element.get("language")
    if not isinstance(language, dict):
        return None
    language_id, version_id = language.get("languageId"), language.get("versionId")
    if not isinstance(language_id, str) or not language_id or not isinstance(version_id, str) or not version_id:
        return None
    return language_id, version_id


def _comparison_key(element):
    group = element.get("comparisonGroup")
    if group is not None:
        return ("group", group) if isinstance(group, str) else None
    element_type = element.get("type")
    if isinstance(element_type, str) and element_type:
        return "type", element_type
    return None


def _pair_key(element):
    language = _language_key(element)
    comparison = _comparison_key(element)
    return (*language, *comparison) if language is not None and comparison is not None else None


def _connection_key(text):
    if text["kind"] == "self":
        return "self", None
    if text["kind"] == "additionalLabel" and isinstance(text.get("connectionLabelId"), str):
        return "additionalLabel", text["connectionLabelId"]
    return None


def compare_pair(inventories, config):
    elements = {
        side: sorted(data["elements"], key=lambda item: item["id"])
        for side, data in inventories.items()
    }
    buckets = {side: {} for side in elements}
    for side, items in elements.items():
        for element in items:
            key = _pair_key(element)
            if key is not None:
                buckets[side].setdefault(key, []).append(element)

    eligible = {}
    for key, references in buckets["reference"].items():
        for reference in references:
            eligible[reference["id"]] = {
                student["id"]: key[2]
                for student in buckets["student"].get(key, [])
            }

    normalized = {side: {} for side in elements}
    processed = {side: [] for side in elements}
    for side, items in elements.items():
        for element in items:
            if element["labelStatus"] != "present":
                continue
            text = normalize(element["matchText"])
            if not text:
                raise ValueError(f"{side} element {element['id']}: normalization made a present label empty")
            normalized[side][element["id"]] = text
            processed[side].append({"id": element["id"], "text": text})

    connection_texts = {
        side: sorted(data.get("connectionTexts", []), key=lambda item: item["id"])
        for side, data in inventories.items()
    }
    connection_candidates = {}
    for reference in connection_texts["reference"]:
        key = _connection_key(reference)
        if key is None:
            connection_candidates[reference["id"]] = []
            continue
        connection_candidates[reference["id"]] = [
            student for student in connection_texts["student"]
            if _connection_key(student) == key
        ]

    score_lookup = {}
    method_metadata = [
        {"name": name, "rawScoreRange": [0, 1], "combinationContributionRange": [0, 1],
         "contributesToCombination": True}
        for name in SCORERS
    ]
    method_metadata.append({"name": "multilingual", "rawScoreRange": [-1, 1],
                            "combinationContributionRange": [0, 1], "contributesToCombination": True})
    embedding = MultilingualMethod(config["embedding"]["multilingual"])
    for key, references in buckets["reference"].items():
        students = buckets["student"].get(key, [])
        if not students:
            continue
        scored_references = [item for item in references if item["id"] in normalized["reference"]]
        scored_students = [item for item in students if item["id"] in normalized["student"]]
        if not scored_references or not scored_students:
            continue
        left = [normalized["reference"][item["id"]] for item in scored_references]
        right = [normalized["student"][item["id"]] for item in scored_students]
        scores: dict[str, NDArray[np.float64]] = {
            name: np.asarray(scorer(left, right), dtype=np.float64)
            for name, scorer in SCORERS.items()
        }
        scores["multilingual"] = np.asarray(embedding.compute(left, right), dtype=np.float64)
        shape = (len(left), len(right))
        for name, matrix in scores.items():
            minimum = -1 if name == "multilingual" else 0
            if (matrix.shape != shape or not np.isfinite(matrix).all()
                    or (matrix < minimum).any() or (matrix > 1).any()):
                raise ValueError(f"invalid score matrix from {name}")
        combined = combine(scores, config["combiner"])
        if (combined.shape != shape or not np.isfinite(combined).all()
                or (combined < 0).any() or (combined > 1).any()):
            raise ValueError("invalid combined score matrix")
        for row, reference in enumerate(scored_references):
            for column, student in enumerate(scored_students):
                score_lookup[(reference["id"], student["id"])] = {
                    "scores": {name: float(matrix[row, column]) for name, matrix in scores.items()},
                    "combinedScore": float(combined[row, column]),
                }
    scored_count = len(score_lookup)

    matrix = []
    candidate_count = 0
    unavailable_count = 0
    for reference in elements["reference"]:
        matches = []
        for student_id, basis in eligible.get(reference["id"], {}).items():
            candidate_count += 1
            scored = score_lookup.get((reference["id"], student_id))
            if scored is None:
                unavailable_count += 1
                matches.append({
                    "submissionElementId": student_id, "comparisonBasis": basis,
                    "scoreStatus": "unavailable", "scores": None, "combinedScore": None,
                    "aliasEvidence": [],
                })
            else:
                matches.append({
                    "submissionElementId": student_id, "comparisonBasis": basis,
                    "scoreStatus": "scored", **scored, "aliasEvidence": [],
                })
        matches.sort(key=lambda item: (
            item["scoreStatus"] != "scored",
            -(item["combinedScore"] or 0),
            item["submissionElementId"],
        ))
        matrix.append({"referenceElementId": reference["id"], "matches": matches})

    connection_matrix = []
    connection_pair_count = 0
    for reference in connection_texts["reference"]:
        matches = []
        for student in connection_candidates.get(reference["id"], []):
            connection_pair_count += 1
            statuses = {reference["labelStatus"], student["labelStatus"]}
            unavailable_reason = (
                "unsupported_text" if "unsupported" in statuses
                else "missing_text" if "missing" in statuses
                else "connection_owner_compatibility_not_in_inventory"
            )
            matches.append({
                "submissionConnectionTextId": student["id"],
                "referenceOwnerConnectionId": reference["ownerConnectionId"],
                "submissionOwnerConnectionId": student["ownerConnectionId"],
                "kind": reference["kind"],
                "connectionLabelId": reference["connectionLabelId"],
                "scoreStatus": "unavailable",
                "scores": None,
                "combinedScore": None,
                "unavailableReason": unavailable_reason,
            })
        connection_matrix.append({"referenceConnectionTextId": reference["id"], "matches": matches})

    unscored = [{"side": side, "id": element["id"],
                 "reason": "missing_text" if element["labelStatus"] == "missing" else "unsupported_text"}
                for side, items in elements.items() for element in items if element["labelStatus"] != "present"]
    return {
        "synonymMatrix": matrix,
        "connectionTextMatrix": connection_matrix,
        "unscoredElements": unscored,
        "processedTexts": processed,
        "candidatePairCount": candidate_count,
        "scoredPairCount": scored_count,
        "unavailablePairCount": unavailable_count,
        "connectionTextPairCount": connection_pair_count,
        "methods": method_metadata,
        "combiner": describe(config["combiner"]),
        "resources": {"multilingual": embedding.resource_metadata()},
    }
