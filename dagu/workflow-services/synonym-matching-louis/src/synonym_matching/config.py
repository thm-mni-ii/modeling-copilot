"""Prüfe Konfigurationen, damit unbekannte Optionen nicht unbemerkt bleiben."""

import math
from copy import deepcopy

from .methods import EMBEDDING_MODELS, METHODS
from .preprocessing import Preprocessor
from .lexicons import RELATION_FEATURES

# Vorläufige Auswahl aus dem Vergleich auf allen 35 auswertbaren Szenarien.
# Das String-Ensemble und das multilinguale Embedding erhalten je 50 Prozent.
DEFAULT_CONFIG = {
    'methods': ['levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'],
    'preprocessing': ['normalize'],
    'embedding_preprocessing': ['normalize'],
    'combiner': {'kind': 'variant', 'name': 'weighted_fusion',
                 'options': {'embedding_weight': 0.5}},
}


def validate_config(value=None):
    """Prüfe die Benutzerkonfiguration und ergänze Standardwerte in einer Kopie."""
    config = deepcopy(value if value is not None else {})
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    allowed_fields = {
        "methods", "preprocessing", "embedding_preprocessing", "embedding",
        "combiner", "seed", "lexicons", "semantic_features",
    }
    unknown = set(config) - allowed_fields
    if unknown:
        raise ValueError(f"unknown config fields: {sorted(unknown)}")
    if 'methods' not in config:
        for name, default in DEFAULT_CONFIG.items():
            config.setdefault(name, deepcopy(default))
    methods = config['methods']
    if (not isinstance(methods, list) or not methods
            or any(not isinstance(name, str) for name in methods)):
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
    _validate_embeddings(embedding)
    lexicons = config.setdefault("lexicons", {})
    if not isinstance(lexicons, dict) or set(lexicons) - {"wordnet", "openthesaurus", "odenet"}:
        raise ValueError("lexicons supports wordnet/odenet data directories and openthesaurus text path")
    if any(not isinstance(path, str) or not path for path in lexicons.values()):
        raise ValueError("lexicon paths must be nonempty strings")
    combiner = config.setdefault("combiner", {"kind": "mean"})
    _validate_combiner(combiner, methods)
    semantic = config.setdefault('semantic_features', {})
    if not isinstance(semantic, dict):
        raise ValueError('semantic_features must map selected lexicons to feature lists')
    if combiner['kind'] == 'evidence':
        from .combinations import EVIDENCE_FEATURES
        semantic.setdefault(combiner['lexicon'], list(EVIDENCE_FEATURES))
    for name, features in semantic.items():
        if (name not in {'wordnet', 'odenet', 'openthesaurus', 'wn_translation'} or name not in methods
                or not isinstance(features, list)
                or any(not isinstance(f, str) or f not in RELATION_FEATURES for f in features)
                or len(features) != len(set(features))
                or (name in {'openthesaurus', 'wn_translation'} and features)):
            raise ValueError('invalid semantic_features source or feature list')
    if combiner['kind'] == 'evidence' and set(EVIDENCE_FEATURES) - set(semantic[combiner['lexicon']]):
        raise ValueError('evidence combiner requires all six lexicon evidence features')
    return config


def _validate_embeddings(embedding):
    """Prüfe Modellnamen, Batchgrößen und erlaubte Übersetzungsoptionen."""
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


def _validate_combiner(combiner, methods):
    """Prüfe Kombination, benötigte Einzelmethoden und optionale Gewichte."""
    if not isinstance(combiner, dict):
        raise ValueError("combiner must be an object")
    kind = combiner.setdefault("kind", "mean")
    allowed = {"kind", "methods"}
    if kind == "weighted_mean":
        allowed.add("weights")
    elif kind == "variant":
        allowed |= {"name", "options"}
        from .combinations import VARIANTS
        if combiner.get("name") not in VARIANTS:
            raise ValueError("unknown variant")
        if not isinstance(combiner.get("options", {}), dict):
            raise ValueError("variant options must be an object")
    elif kind == 'evidence':
        allowed |= {'baseline', 'lexicon'}
        baseline, lexicon = combiner.get('baseline'), combiner.get('lexicon')
        if (not isinstance(baseline, str) or not isinstance(lexicon, str)
                or baseline not in methods or lexicon not in {'wordnet', 'odenet'}
                or lexicon not in methods or baseline == lexicon):
            raise ValueError('evidence combiner requires distinct baseline and WordNet/OdeNet methods')
    elif kind not in {"mean", "max"}:
        raise ValueError(f"unknown combiner: {kind}")
    if set(combiner) - allowed:
        raise ValueError("unknown combiner options")
    default_methods = [combiner['baseline'], combiner['lexicon']] if kind == 'evidence' else methods.copy()
    selected = combiner.setdefault("methods", default_methods)
    if (not isinstance(selected, list) or not selected
            or any(not isinstance(name, str) for name in selected)):
        raise ValueError("combiner methods must be a nonempty list")
    if len(set(selected)) != len(selected) or set(selected) - set(methods):
        raise ValueError("combiner methods must be a unique subset of methods")
    if kind == 'evidence' and set(selected) != set(default_methods):
        raise ValueError('evidence combiner methods must contain exactly baseline and lexicon')
    if kind == "variant":
        from .combinations import REQUIRES
        if set(REQUIRES[combiner["name"]]) - set(selected):
            raise ValueError("variant requires additional base methods")
    if kind == "weighted_mean":
        weights = combiner.get("weights", {})
        if not isinstance(weights, dict) or set(weights) != set(selected):
            raise ValueError("weights must specify exactly the selected methods")
        invalid_weights = any(
            type(weight) not in (int, float)
            or not math.isfinite(weight)
            or weight < 0
            for weight in weights.values()
        )
        if invalid_weights or sum(weights.values()) <= 0:
            raise ValueError("weights must be finite, nonnegative and have positive sum")
