"""Fixed score aggregation functions."""

import numpy as np


def mean(matrices):
    """Mittle die Matrizen elementweise mit gleichem Gewicht."""
    return np.stack(list(matrices.values())).mean(axis=0)


def maximum(matrices):
    """Wähle an jeder Matrixposition den höchsten Score."""
    return np.stack(list(matrices.values())).max(axis=0)


def weighted_mean(matrices, *, weights):
    """Mittle die Matrizen mit geprüften, nichtnegativen Gewichten."""
    names = list(matrices)
    if set(weights) != set(names):
        raise ValueError("weights must specify exactly the selected methods")
    w = np.array([weights[n] for n in names], dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError("weights must be finite, nonnegative and have positive sum")
    return np.average(np.stack(list(matrices.values())), axis=0, weights=w)


COMBINERS = {"mean": mean, "max": maximum, "weighted_mean": weighted_mean}


def combine(matrices, config):
    """Configuration adapter: select features, clip cosine, call one function."""
    names = config.get("methods", list(matrices))
    if not names or len(set(names)) != len(names) or set(names) - matrices.keys():
        raise ValueError("combiner methods must be a nonempty unique subset of computed methods")
    values = {name: np.clip(matrices[name], 0, 1) for name in names}
    kind = config.get("kind", "mean")
    if kind == "variant":
        from .variants import evaluate_variant
        return evaluate_variant(config["name"], values, **config.get("options", {}))
    if kind not in COMBINERS:
        raise ValueError(f"unknown combiner: {kind}")
    options = {key: value for key, value in config.items() if key not in {"kind", "methods"}}
    return COMBINERS[kind](values, **options)
