"""Strict validation prevents unnoticed experimental typos."""
import math
from copy import deepcopy
from .methods import DEFAULT_METHODS, EMBEDDING_MODELS, METHODS
from .preprocessing import Preprocessor


def validate_config(value=None):
    config = deepcopy(value if value is not None else {})
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    unknown = set(config) - {"methods", "preprocessing", "embedding_preprocessing", "embedding", "combiner", "seed"}
    if unknown:
        raise ValueError(f"unknown config fields: {sorted(unknown)}")
    methods = config.setdefault("methods", DEFAULT_METHODS.copy())
    if not isinstance(methods, list) or not methods or any(not isinstance(n, str) for n in methods):
        raise ValueError("methods must be a nonempty list of method names")
    if len(set(methods)) != len(methods) or set(methods) - METHODS.keys():
        raise ValueError("unknown or duplicate methods")
    config.setdefault("preprocessing", {"normalize": True})
    config.setdefault("embedding_preprocessing", {"normalize": True})
    Preprocessor(config["preprocessing"])
    Preprocessor(config["embedding_preprocessing"])
    seed = config.setdefault("seed", 42)
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer in [0, 2**32)")
    embedding = config.setdefault("embedding", {})
    if not isinstance(embedding, dict) or set(embedding) - EMBEDDING_MODELS.keys():
        raise ValueError("unknown embedding method configuration")
    for name, options in embedding.items():
        allowed = {"model", "revision", "batch_size"}
        if name == "translated_embedding":
            allowed |= {"translation_model", "translation_revision", "target_preprocessing"}
        if not isinstance(options, dict) or set(options) - allowed:
            raise ValueError("unknown embedding options")
        if type(options.get("batch_size", 32)) is not int or options.get("batch_size", 32) < 1:
            raise ValueError("batch_size must be a positive integer")
        for key in allowed - {"batch_size", "target_preprocessing"}:
            if key in options and (not isinstance(options[key], str) or not options[key]):
                raise ValueError(f"{key} must be a nonempty string")
        Preprocessor(options.get("target_preprocessing", {}))
    combiner = config.setdefault("combiner", {"kind": "mean"})
    if not isinstance(combiner, dict):
        raise ValueError("combiner must be an object")
    kind = combiner.setdefault("kind", "mean")
    allowed = {"kind", "methods"}
    if kind == "weighted_mean":
        allowed.add("weights")
    elif kind not in {"mean", "max"}:
        raise ValueError(f"unknown combiner: {kind}")
    if set(combiner) - allowed:
        raise ValueError("unknown combiner options")
    selected = combiner.setdefault("methods", methods.copy())
    if not isinstance(selected, list) or not selected or any(not isinstance(n, str) for n in selected):
        raise ValueError("combiner methods must be a nonempty list")
    if len(set(selected)) != len(selected) or set(selected) - set(methods):
        raise ValueError("combiner methods must be a unique subset of methods")
    if kind == "weighted_mean":
        weights = combiner.get("weights", {})
        if not isinstance(weights, dict) or set(weights) != set(selected):
            raise ValueError("weights must specify exactly the selected methods")
        if any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("weights must be finite, nonnegative and have positive sum")
    return config
