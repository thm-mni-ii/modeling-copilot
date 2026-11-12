"""Resolve the small public method and preprocessing configuration."""

from copy import deepcopy
import math

from .methods.registry import DEFAULT_METHODS, METHOD_REGISTRY, PREPROCESSORS


def resolve_config(comparison_config):
    if not isinstance(comparison_config, dict):
        raise ValueError("comparisonConfig must be an object")
    semantics = comparison_config.get("semantics", {})
    if not isinstance(semantics, dict):
        raise ValueError("comparisonConfig.semantics must be an object")
    unknown_options = set(semantics) - {"methods", "preprocessing"}
    if unknown_options:
        raise ValueError(f"unsupported semantics options: {', '.join(sorted(unknown_options))}")
    methods = semantics.get("methods", list(DEFAULT_METHODS))
    if (not isinstance(methods, list) or not methods
            or any(not isinstance(name, str) for name in methods)):
        raise ValueError("comparisonConfig.semantics.methods must be a non-empty array of method names")
    if len(set(methods)) != len(methods):
        raise ValueError("comparisonConfig.semantics.methods must not contain duplicates")
    for name in methods:
        if name not in METHOD_REGISTRY:
            raise ValueError(f"unknown similarity method: {name!r}")
    preprocessing = semantics.get("preprocessing")
    if preprocessing is not None:
        if not isinstance(preprocessing, list) or any(not isinstance(name, str) for name in preprocessing):
            raise ValueError("comparisonConfig.semantics.preprocessing must be an array of names")
        if len(set(preprocessing)) != len(preprocessing):
            raise ValueError("comparisonConfig.semantics.preprocessing must not contain duplicates")
        unknown = set(preprocessing) - set(PREPROCESSORS)
        if unknown:
            raise ValueError(f"unknown text preprocessing: {', '.join(sorted(unknown))}")
    active_methods = [METHOD_REGISTRY[name] for name in methods]
    for method in active_methods:
        score_range = method.score_range
        if (not isinstance(score_range, (tuple, list)) or len(score_range) != 2
                or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in score_range)
                or score_range[0] > score_range[1]):
            raise ValueError(f"invalid score range registered for {method.name}")
        selected_preprocessing = preprocessing if preprocessing is not None else method.preprocessing
        unknown = set(selected_preprocessing) - set(PREPROCESSORS)
        if unknown:
            raise ValueError(
                f"method {method.name} requires unknown text preprocessing: {', '.join(sorted(unknown))}"
            )
    return {"methods": deepcopy(methods), "preprocessing": deepcopy(preprocessing)}
