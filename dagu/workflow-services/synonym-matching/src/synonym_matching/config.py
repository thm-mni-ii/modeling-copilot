"""Freeze the existing reference default without introducing workflow tuning."""

from copy import deepcopy

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
DEFAULT_CONFIG = {
    "methods": ["levenshtein", "jaro_winkler", "char_trigram", "multilingual"],
    "preprocessing": ["normalize"],
    "embedding_preprocessing": ["normalize"],
    "embedding": {"multilingual": {
        "model": MODEL_NAME, "revision": MODEL_REVISION, "batch_size": 32,
        "device": "cpu", "normalize_embeddings": True, "local_files_only": True,
    }},
    "combiner": {"kind": "variant", "name": "weighted_fusion",
                 "methods": ["levenshtein", "jaro_winkler", "char_trigram", "multilingual"],
                 "options": {"embedding_weight": 0.5}},
}


def resolve_config(comparison_config):
    if not isinstance(comparison_config, dict):
        raise ValueError("comparisonConfig must be an object")
    semantics = comparison_config.get("semantics", {})
    if not isinstance(semantics, dict) or semantics:
        raise ValueError("comparisonConfig.semantics must be absent or empty; this V1 step uses the documented default")
    return deepcopy(DEFAULT_CONFIG)
