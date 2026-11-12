"""Compute independent text-similarity evidence for one inventory pair."""

from copy import deepcopy

import numpy as np

from .methods.registry import METHOD_REGISTRY, PREPROCESSORS, resolve_methods


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
        return ("group", group) if isinstance(group, str) and group else None
    element_type = element.get("type")
    return ("type", element_type) if isinstance(element_type, str) and element_type else None


def _pair_key(element):
    language = _language_key(element)
    comparison = _comparison_key(element)
    return (*language, *comparison) if language is not None and comparison is not None else None


def _connection_key(text):
    if text["kind"] == "self":
        return "self", None
    label_id = text.get("connectionLabelId")
    if text["kind"] == "additionalLabel" and isinstance(label_id, str) and label_id:
        return "additionalLabel", label_id
    return None


def _prepare_text(text, preprocessing):
    for name in preprocessing:
        text = PREPROCESSORS[name](text)
    return text


def _valid_text_map(items, preprocessing, side):
    result = {}
    for item in items:
        if item["labelStatus"] != "present":
            continue
        text = _prepare_text(item["matchText"], preprocessing)
        if text:
            result[item["id"]] = text
        elif side == "element":
            raise ValueError(f"{item['id']}: preprocessing made a present label empty")
    return result


def _score_group(left_items, right_items, left_texts, right_texts, methods, method_states):
    pair_scores = {}
    for method in methods:
        method_left_texts = left_texts[method.name]
        method_right_texts = right_texts[method.name]
        left = list(dict.fromkeys(method_left_texts[item["id"]] for item in left_items
                                  if item["id"] in method_left_texts))
        right = list(dict.fromkeys(method_right_texts[item["id"]] for item in right_items
                                   if item["id"] in method_right_texts))
        if not left or not right:
            continue
        if method.name not in method_states:
            method_states[method.name] = method.initialize() if method.initialize is not None else None
        matrix = np.asarray(method.compute(method_states[method.name], left, right), dtype=np.float64)
        expected_shape = (len(left), len(right))
        minimum, maximum = method.score_range
        if (matrix.shape != expected_shape or not np.isfinite(matrix).all()
                or (matrix < minimum).any() or (matrix > maximum).any()):
            raise ValueError(f"invalid score matrix from {method.name}")
        text_scores = {
            (left_text, right_text): float(matrix[row, column])
            for row, left_text in enumerate(left)
            for column, right_text in enumerate(right)
        }
        for left_item in left_items:
            left_id = left_item["id"]
            if left_id not in method_left_texts:
                continue
            for right_item in right_items:
                right_id = right_item["id"]
                if right_id not in method_right_texts:
                    continue
                pair = (left_id, right_id)
                pair_scores.setdefault(pair, {})[method.name] = text_scores[
                    (method_left_texts[left_id], method_right_texts[right_id])
                ]
    expected_names = {method.name for method in methods}
    for pair, scores in pair_scores.items():
        if set(scores) != expected_names:
            continue
        if any(
            not isinstance(value, (int, float)) or not np.isfinite(value)
            or value < method.score_range[0] or value > method.score_range[1]
            for method in methods for value in (scores.get(method.name),)
        ):
            raise ValueError(f"invalid candidate scores for {pair}")
    return {
        pair: scores for pair, scores in pair_scores.items()
        if set(scores) == expected_names
    }


def _method_metadata(methods, config, method_states):
    metadata = []
    for method in methods:
        preprocessing = config["preprocessing"] if config["preprocessing"] is not None else list(method.preprocessing)
        entry = {
            "name": method.name,
            "scoreRange": list(method.score_range),
            "preprocessing": list(preprocessing),
            "parameters": deepcopy(method.parameters or {}),
        }
        if method.resource_metadata is not None:
            entry["resources"] = method.resource_metadata(method_states.get(method.name))
        metadata.append(entry)
    return metadata


def compare_pair(inventories, config):
    methods = resolve_methods(config["methods"])
    preprocessing = config["preprocessing"]
    elements = {
        side: sorted(data["elements"], key=lambda item: item["id"])
        for side, data in inventories.items()
    }
    connection_texts = {
        side: sorted(data.get("connectionTexts", []), key=lambda item: item["id"])
        for side, data in inventories.items()
    }
    active_preprocessing = preprocessing if preprocessing is not None else ["normalize"]
    prepared_elements = {
        side: {
            method.name: _valid_text_map(
                items,
                preprocessing if preprocessing is not None else list(method.preprocessing),
                "element",
            )
            for method in methods
        }
        for side, items in elements.items()
    }
    prepared_connections = {
        side: {
            method.name: _valid_text_map(
                items,
                preprocessing if preprocessing is not None else list(method.preprocessing),
                "connection",
            )
            for method in methods
        }
        for side, items in connection_texts.items()
    }
    processed_element_texts = {
        side: _valid_text_map(items, active_preprocessing, "element")
        for side, items in elements.items()
    }
    processed_connection_texts = {
        side: _valid_text_map(items, active_preprocessing, "connection")
        for side, items in connection_texts.items()
    }
    processed = {
        side: sorted(
            [{"id": identity, "text": text}
             for identity, text in {
                 **processed_element_texts[side], **processed_connection_texts[side],
             }.items()],
            key=lambda item: item["id"],
        )
        for side in elements
    }

    element_buckets = {side: {} for side in elements}
    for side, items in elements.items():
        for element in items:
            key = _pair_key(element)
            if key is not None:
                element_buckets[side].setdefault(key, []).append(element)

    method_states = {}
    element_scores = {}
    for key, references in element_buckets["reference"].items():
        submissions = element_buckets["student"].get(key, [])
        if not submissions:
            continue
        element_scores.update(_score_group(
            references, submissions, prepared_elements["reference"], prepared_elements["student"],
            methods, method_states,
        ))

    eligible = {}
    for key, references in element_buckets["reference"].items():
        for reference in references:
            eligible[reference["id"]] = {
                submission["id"]: key[2]
                for submission in element_buckets["student"].get(key, [])
            }

    matrix = []
    candidate_count = scored_count = unavailable_count = 0
    student_elements = {item["id"]: item for item in elements["student"]}
    student_status = {identity: item["labelStatus"] for identity, item in student_elements.items()}
    for reference in elements["reference"]:
        matches = []
        for submission_id, basis in eligible.get(reference["id"], {}).items():
            candidate_count += 1
            scores = element_scores.get((reference["id"], submission_id))
            if scores is None:
                unavailable_count += 1
                reason = "missing_text" if (
                    reference["labelStatus"] == "missing"
                    or student_status[submission_id] == "missing"
                ) else "unsupported_text"
                matches.append({
                    "submissionElementId": submission_id,
                    "submissionLabel": student_elements[submission_id]["matchText"],
                    "comparisonBasis": basis,
                    "scoreStatus": "unavailable", "unavailableReason": reason, "scores": None,
                })
            else:
                scored_count += 1
                matches.append({
                    "submissionElementId": submission_id,
                    "submissionLabel": student_elements[submission_id]["matchText"],
                    "comparisonBasis": basis,
                    "scoreStatus": "scored", "scores": scores,
                })
        matches.sort(key=lambda item: item["submissionElementId"])
        matrix.append({
            "referenceElementId": reference["id"],
            "referenceLabel": reference["matchText"],
            "matches": matches,
        })

    connection_buckets = {side: {} for side in connection_texts}
    for side, items in connection_texts.items():
        for text in items:
            key = _connection_key(text)
            if (key is None or text["labelStatus"] != "present"
                    or not any(text["id"] in prepared_connections[side][method.name] for method in methods)):
                continue
            connection_buckets[side].setdefault(key, []).append(text)
    connection_scores = {}
    for key, references in connection_buckets["reference"].items():
        submissions = connection_buckets["student"].get(key, [])
        if submissions:
            connection_scores.update(_score_group(
                references, submissions, prepared_connections["reference"],
                prepared_connections["student"],
                methods, method_states,
            ))
    connection_by_id = {
        side: {text["id"]: text for text in items}
        for side, items in connection_texts.items()
    }
    connection_matrix = [
        {
            "referenceConnectionTextId": reference_id,
            "submissionConnectionTextId": submission_id,
            "referenceOwnerConnectionId": connection_by_id["reference"][reference_id]["ownerConnectionId"],
            "submissionOwnerConnectionId": connection_by_id["student"][submission_id]["ownerConnectionId"],
            "referenceLabel": connection_by_id["reference"][reference_id]["matchText"],
            "submissionLabel": connection_by_id["student"][submission_id]["matchText"],
            "kind": connection_by_id["reference"][reference_id]["kind"],
            "connectionLabelId": connection_by_id["reference"][reference_id]["connectionLabelId"],
            "scores": scores,
        }
        for (reference_id, submission_id), scores in sorted(connection_scores.items())
    ]

    unscored = [
        {"side": side, "id": element["id"],
         "reason": "missing_text" if element["labelStatus"] == "missing" else "unsupported_text"}
        for side, items in elements.items() for element in items if element["labelStatus"] != "present"
    ]
    return {
        "synonymMatrix": matrix,
        "connectionTextMatrix": connection_matrix,
        "unscoredElements": unscored,
        "processedTexts": processed,
        "candidatePairCount": candidate_count,
        "scoredPairCount": scored_count,
        "unavailablePairCount": unavailable_count,
        "methods": _method_metadata(methods, config, method_states),
        "semanticConfig": {
            "methods": list(config["methods"]),
            "preprocessing": {
                method.name: list(config["preprocessing"] if config["preprocessing"] is not None
                                  else method.preprocessing)
                for method in methods
            },
        },
    }
