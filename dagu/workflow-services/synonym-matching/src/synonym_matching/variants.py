"""Named experiments over reusable score matrices. No model loading or I/O here.

Every function returns one matrix of the same shape. Base scores remain untouched.
All variants are fixed combinations; no training is performed.
"""

import numpy as np

from .combiners import mean, maximum, weighted_mean

STRINGS = ('levenshtein', 'jaro_winkler', 'char_trigram')
TOKENS = ('token_jaccard', 'token_sort_ratio')
EMBEDDINGS = ('translated_embedding', 'multilingual')


def _select(scores, names):
    """Wähle Einzelmatrizen aus und begrenze Kopien auf [0, 1]."""
    return {name: np.clip(np.asarray(scores[name], dtype=float), 0, 1) for name in names}


def string_ensemble(scores):
    """Mittle Levenshtein, Jaro-Winkler und Zeichen-Trigramme."""
    return mean(_select(scores, STRINGS))


def token_ensemble(scores):
    """Mittle Token-Jaccard und Token Sort Ratio."""
    return mean(_select(scores, TOKENS))


def character_token_ensemble(scores):
    """Gewichte das String- und Token-Ensemble gleich."""
    return mean({'characters': string_ensemble(scores), 'tokens': token_ensemble(scores)})


def translation_string(scores):
    """Verwende den Stringscore nach Übersetzung."""
    return _select(scores, ('translated_string',))['translated_string']


def translation_monolingual(scores):
    """Verwende das monolinguale Embedding nach Übersetzung."""
    return _select(scores, ('translated_embedding',))['translated_embedding']


def multilingual_only(scores):
    """Verwende nur den direkten multilingualen Embeddingscore."""
    return _select(scores, ('multilingual',))['multilingual']


def embedding_ensemble(scores):
    """Mittle beide Embedding-Pfade."""
    return mean(_select(scores, EMBEDDINGS))


def string_multilingual(scores):
    """Mittle String-Ensemble und multilinguales Embedding."""
    return mean({'strings': string_ensemble(scores), 'embedding': multilingual_only(scores)})


def string_translation_embedding(scores):
    """Mittle String-Ensemble und übersetztes Embedding."""
    return mean({'strings': string_ensemble(scores), 'embedding': translation_monolingual(scores)})


def string_both_embeddings(scores):
    """Gewichte String-Ensemble und beide Embeddings mit je einem Drittel."""
    return mean({'strings': string_ensemble(scores), **_select(scores, EMBEDDINGS)})


def weighted_fusion(scores, *, embedding_weight=0.5):
    """Kombiniere String und Embedding mit einstellbarem Embeddinggewicht."""
    if (type(embedding_weight) not in (float, int)
            or not np.isfinite(embedding_weight)
            or not 0 <= embedding_weight <= 1):
        raise ValueError('embedding_weight must be in [0,1]')
    matrices = {
        'strings': string_ensemble(scores),
        'embedding': multilingual_only(scores),
    }
    weights = {'strings': 1 - embedding_weight, 'embedding': embedding_weight}
    return weighted_mean(matrices, weights=weights)


def maximum_fusion(scores):
    """Verwende den höheren String- oder Embeddingscore."""
    return maximum({'strings': string_ensemble(scores), 'embedding': multilingual_only(scores)})


def geometric_fusion(scores):
    # A zero component deliberately vetoes the geometric mean.
    """Berechne das geometrische Mittel; ein Nullscore wirkt als Veto."""
    return np.sqrt(string_ensemble(scores) * multilingual_only(scores))


def exact_match_fusion(scores):
    """Setze echte Textgleichheit auf 1, sonst verwende den Hybridscore."""
    base = string_multilingual(scores)
    return np.where(np.asarray(scores['exact_match']) == 1, 1.0, base)


def context_aware(scores, *, penalty=0.5):
    """Penalize row/column competitors without promoting weak absolute scores.

    Competition is computed inside one task only. Ties incur no arbitrary ID-based
    preference. No one-to-one assignment, softmax probability or label information.
    """
    if type(penalty) not in (float, int) or not np.isfinite(penalty) or not 0 <= penalty <= 1:
        raise ValueError('penalty must be in [0,1]')
    base = string_multilingual(scores)
    if base.size == 0:
        return base
    row_gap = base.max(axis=1, keepdims=True) - base
    column_gap = base.max(axis=0, keepdims=True) - base
    return np.clip(base - penalty * (row_gap + column_gap) / 2, 0, 1)


# Explizite Zuordnung zwischen Konfigurationsnamen und Funktionen.
VARIANTS = {
    'string_ensemble': string_ensemble,
    'token_ensemble': token_ensemble,
    'character_token_ensemble': character_token_ensemble,
    'translation_string': translation_string,
    'translation_monolingual': translation_monolingual,
    'multilingual_only': multilingual_only,
    'embedding_ensemble': embedding_ensemble,
    'string_multilingual': string_multilingual,
    'string_translation_embedding': string_translation_embedding,
    'string_both_embeddings': string_both_embeddings,
    'weighted_fusion': weighted_fusion,
    'maximum_fusion': maximum_fusion,
    'geometric_fusion': geometric_fusion,
    'exact_match_fusion': exact_match_fusion,
    'context_aware': context_aware,
}

REQUIRES = {
    'string_ensemble': ('levenshtein', 'jaro_winkler', 'char_trigram'),
    'token_ensemble': ('token_jaccard', 'token_sort_ratio'),
    'character_token_ensemble': STRINGS + TOKENS,
    'translation_string': ('translated_string',),
    'translation_monolingual': ('translated_embedding',),
    'multilingual_only': ('multilingual',),
    'embedding_ensemble': ('translated_embedding', 'multilingual'),
    'string_multilingual': ('levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'),
    'string_translation_embedding': STRINGS + ('translated_embedding',),
    'string_both_embeddings': STRINGS + EMBEDDINGS,
    'weighted_fusion': ('levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'),
    'maximum_fusion': ('levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'),
    'geometric_fusion': ('levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'),
    'exact_match_fusion': STRINGS + ('multilingual', 'exact_match'),
    'context_aware': ('levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'),
}


def evaluate_variant(name, scores, **options):
    """Prüfe benötigte Scores und Matrixformen, dann rufe die Variante auf."""
    if name not in VARIANTS:
        raise ValueError(f'unknown variant: {name}')
    missing = set(REQUIRES[name]) - scores.keys()
    if missing:
        raise ValueError(f'{name} needs scores: {sorted(missing)}')
    shapes = {np.asarray(scores[n]).shape for n in REQUIRES[name]}
    if len(shapes) != 1 or len(next(iter(shapes))) != 2:
        raise ValueError('all feature matrices must have the same two-dimensional shape')
    result = VARIANTS[name](scores, **options)
    if result.shape not in shapes or not np.isfinite(result).all():
        raise ValueError(f'invalid output from {name}')
    return result
