"""Registry for independently configured text-similarity methods."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from .char_trigram import compute as char_trigram
from .jaro_winkler import compute as jaro_winkler
from .levenshtein import compute as levenshtein
from .multilingual import MultilingualMethod
from ..preprocessing import normalize

ScoreMatrix = NDArray[np.float64]
PREPROCESSORS = {"normalize": normalize}
MULTILINGUAL_PARAMETERS = {
    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "revision": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    "batch_size": 32,
    "device": "cpu",
    "normalize_embeddings": True,
    "local_files_only": True,
}


@dataclass(frozen=True)
class MethodDefinition:
    name: str
    score_range: tuple[float, float]
    compute: Callable[[object | None, list[str], list[str]], ScoreMatrix]
    preprocessing: tuple[str, ...] = ("normalize",)
    parameters: dict | None = None
    initialize: Callable[[], object] | None = None
    resource_metadata: Callable[[object | None], dict] | None = None


def _simple(compute):
    return lambda _state, left, right: np.asarray(compute(left, right), dtype=np.float64)


def _create_multilingual():
    return MultilingualMethod(deepcopy(MULTILINGUAL_PARAMETERS))


def _multilingual(state, left, right):
    return np.asarray(state.compute(left, right), dtype=np.float64)


def _multilingual_resources(state):
    if state is None:
        return {**deepcopy(MULTILINGUAL_PARAMETERS), "resolvedRevision": None,
                "status": "not_needed_no_usable_pairs", "maxSequenceLength": None}
    return state.resource_metadata()


METHOD_REGISTRY = {
    "levenshtein": MethodDefinition("levenshtein", (0, 1), _simple(levenshtein)),
    "jaro_winkler": MethodDefinition("jaro_winkler", (0, 1), _simple(jaro_winkler)),
    "char_trigram": MethodDefinition("char_trigram", (0, 1), _simple(char_trigram)),
    "multilingual": MethodDefinition(
        "multilingual", (-1, 1), _multilingual, parameters=MULTILINGUAL_PARAMETERS,
        initialize=_create_multilingual, resource_metadata=_multilingual_resources,
    ),
}
DEFAULT_METHODS = tuple(METHOD_REGISTRY)


def resolve_methods(names: list[str]) -> list[MethodDefinition]:
    methods = []
    for name in names:
        if not isinstance(name, str) or name not in METHOD_REGISTRY:
            raise ValueError(f"unknown similarity method: {name!r}")
        methods.append(METHOD_REGISTRY[name])
    return methods
