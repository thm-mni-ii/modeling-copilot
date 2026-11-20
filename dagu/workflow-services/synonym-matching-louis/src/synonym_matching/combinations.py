"""Kombiniere Einzelmatrizen mit festen Rechenregeln."""

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
    """Wähle Scores, begrenze Cosinuswerte und rufe die konfigurierte Kombination auf."""
    names = config.get("methods", list(matrices))
    if not names or len(set(names)) != len(names) or set(names) - matrices.keys():
        raise ValueError("combiner methods must be a nonempty unique subset of computed methods")
    values = {name: matrices[name] for name in names}
    kind = config.get("kind", "mean")
    if kind == "variant":
        # Varianten wählen und begrenzen ihre Einzelwerte bereits über _select().
        return evaluate_variant(config["name"], values, **config.get("options", {}))
    if kind not in COMBINERS:
        raise ValueError(f"unknown combiner: {kind}")
    options = {key: value for key, value in config.items() if key not in {"kind", "methods"}}
    return COMBINERS[kind](_select(values, names), **options)


STRINGS = ('levenshtein', 'jaro_winkler', 'char_trigram')
TOKENS = ('token_jaccard', 'token_sort_ratio')
EMBEDDINGS = ('translated_embedding', 'multilingual')
EVIDENCE_FEATURES = ('pair_known', 'reference_synset_count', 'student_synset_count',
                     'reference_hypernym', 'reference_hyponym', 'antonym')
SEMANTIC_METHODS = STRINGS + ('translated_embedding', 'wordnet', 'label_part_compatibility')
SEMANTIC_FEATURES = EVIDENCE_FEATURES + ('path_similarity', 'wup_similarity', 'taxonomy_available')
SEMANTIC_ABLATIONS = {'strings', 'coverage', 'ambiguity', 'synsets', 'relations', 'ontology', 'conflicts'}
SEMANTIC_POLICY = {
    'embedding_weight': .75, 'synset_floor': .9, 'ontology_boost': .1,
    'relation_penalty': .5, 'ontology_penalty': .25, 'conflict_penalty': .5,
}
COMPONENT_EVIDENCE_POLICY = {
    'string_weight': .25, 'lexicon_weight': .3, 'rules': True,
    'synonym_floor': .9, 'relation_cap': 0.,
    'synonym_rule': True, 'relation_rules': True,
}


def component_evidence_options(options=None):
    """Prüfe die wenigen numerischen Gewichte und schaltbaren Evidenzregeln."""
    if not isinstance(options if options is not None else {}, dict):
        raise ValueError('component evidence options must be an object')
    options = options or {}
    if set(options) - COMPONENT_EVIDENCE_POLICY.keys():
        raise ValueError('unknown component evidence option')
    result = {**COMPONENT_EVIDENCE_POLICY, **options}
    for name, value in result.items():
        if name in {'rules', 'synonym_rule', 'relation_rules'}:
            if type(value) is not bool:
                raise ValueError(f'{name} must be boolean')
        elif type(value) not in (int, float) or not np.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f'{name} must be in [0,1]')
    return result


def component_evidence_fusion(features, **options):
    """Gewichtete Ähnlichkeitsbasis, partielle Synonymie und separate Regeln.

    Unbekannte Lexikonanteile erhalten als neutralen Ersatz den Basisscore.
    Antonym-/Hierarchieevidenz begrenzt; vollständige eindeutige Synonymie hebt an.
    Ontologische Nähe bleibt Diagnose und bestätigt keine Gleichwertigkeit.
    """
    policy = component_evidence_options(options)
    names = ('string_similarity', 'embedding_similarity', 'lexicon_coverage',
             'shared_synset_fraction', 'full_synonym_evidence', 'antonym_evidence',
             'hierarchy_evidence')
    if set(names) - features.keys():
        raise ValueError('missing component evidence features')
    arrays = [np.asarray(features[name], dtype=float) for name in names]
    if (arrays[0].ndim != 2 or any(a.shape != arrays[0].shape or not np.isfinite(a).all()
                                  for a in arrays)):
        raise ValueError('component evidence requires finite matrices of equal shape')
    string, embedding, coverage, shared, synonym, antonym, hierarchy = arrays
    coverage, shared = np.clip(coverage, 0, 1), np.clip(shared, 0, 1)
    if (shared > coverage + 1e-12).any():
        raise ValueError('synset agreement cannot exceed lexicon coverage')
    weight = policy['string_weight']
    base = weight * np.clip(string, 0, 1) + (1 - weight) * np.clip(embedding, 0, 1)
    lexical = shared + (1 - coverage) * base
    score = (1 - policy['lexicon_weight']) * base + policy['lexicon_weight'] * lexical
    if policy['rules']:
        counter = (antonym == 1) | (hierarchy == 1)
        if policy['synonym_rule']:
            score = np.where((synonym == 1) & ~counter,
                             np.maximum(score, policy['synonym_floor']), score)
        if policy['relation_rules']:
            score = np.where(counter, np.minimum(score, policy['relation_cap']), score)
    return np.clip(score, 0, 1)


def semantic_fusion(matrices, features, *, disabled=()):
    """Vollständige experimentelle Fusion mit einzeln abschaltbaren Merkmalsgruppen.

    Feste Heuristik, nicht kalibriert: 75 % Embedding + 25 % String-Ensemble.
    Eindeutige Synonyme heben an, Gegenrelationen und Labelkonflikte senken ab.
    Taxonomie beeinflusst nur bereits explizit belegte Beziehungen, nie allein.
    Abdeckungs- und Lesartenmasken können redundant sein; die Ablation zeigt das.
    """
    if (not isinstance(disabled, (list, tuple))
            or any(not isinstance(name, str) or name not in SEMANTIC_ABLATIONS for name in disabled)
            or len(disabled) != len(set(disabled))):
        raise ValueError('invalid semantic ablations')
    if set(SEMANTIC_METHODS) - matrices.keys() or set(SEMANTIC_FEATURES) - features.keys():
        raise ValueError('semantic fusion requires all base scores and semantic features')
    arrays = [np.asarray(matrices[name], dtype=float) for name in SEMANTIC_METHODS]
    arrays += [np.asarray(features[name], dtype=float) for name in SEMANTIC_FEATURES]
    shape = arrays[0].shape
    if (len(shape) != 2 or any(a.shape != shape or not np.isfinite(a).all() for a in arrays)):
        raise ValueError('semantic fusion requires finite matrices of the same shape')
    values = _select(matrices, SEMANTIC_METHODS)
    scores = values['translated_embedding'].copy()
    if 'strings' not in disabled:
        weight = SEMANTIC_POLICY['embedding_weight']
        scores = weight * scores + (1 - weight) * string_ensemble(values)

    known = np.asarray(features['pair_known']) == 1
    if 'coverage' in disabled:
        known = np.ones(shape, dtype=bool)
    unambiguous = ((np.asarray(features['reference_synset_count']) == 1)
                   & (np.asarray(features['student_synset_count']) == 1))
    if 'ambiguity' in disabled:
        unambiguous = np.ones(shape, dtype=bool)
    usable = known & unambiguous
    shared = np.asarray(matrices['wordnet']) == 1
    counter = np.logical_or.reduce([
        np.asarray(features[name]) == 1
        for name in ('reference_hypernym', 'reference_hyponym', 'antonym')])
    if 'relations' in disabled:
        counter = np.zeros(shape, dtype=bool)
    boost = np.full(shape, SEMANTIC_POLICY['synset_floor'])
    penalty = np.full(shape, SEMANTIC_POLICY['relation_penalty'])
    if 'ontology' not in disabled:
        available = np.asarray(features['taxonomy_available']) == 1
        ontology = (np.clip(features['path_similarity'], 0, 1)
                    + np.clip(features['wup_similarity'], 0, 1)) / 2
        boost = np.where(available, boost + SEMANTIC_POLICY['ontology_boost'] * ontology, boost)
        penalty = np.where(available, penalty + SEMANTIC_POLICY['ontology_penalty'] * (1 - ontology), penalty)
    if 'synsets' not in disabled:
        scores = np.where(usable & shared & ~counter, np.maximum(scores, boost), scores)
    if 'relations' not in disabled:
        scores = np.where(usable & ~shared & counter, scores * (1 - penalty), scores)
    if 'conflicts' not in disabled:
        scores *= 1 - SEMANTIC_POLICY['conflict_penalty'] * (1 - values['label_part_compatibility'])
    return np.clip(scores, 0, 1)


def evidence_fusion(baseline, synonyms, features):
    """Nutze Lexikonevidenz nur bei genau einer erfassten Lesart auf beiden Seiten.

    Gemeinsamer Synset ohne Gegenrelation → 1; explizite Gegenrelation ohne
    gemeinsamen Synset → 0. Unbekannte, mehrdeutige oder widersprüchliche Evidenz
    lässt den Basisscore unverändert. Das ist eine Heuristik, keine Kalibrierung.
    """
    if set(EVIDENCE_FEATURES) - features.keys():
        raise ValueError('evidence_fusion requires coverage, sense counts and relations')
    arrays = [np.asarray(value, dtype=float) for value in
              [baseline, synonyms, *[features[name] for name in EVIDENCE_FEATURES]]]
    if (arrays[0].ndim != 2 or any(a.shape != arrays[0].shape for a in arrays)
            or any(not np.isfinite(a).all() for a in arrays)):
        raise ValueError('evidence_fusion requires finite matrices of the same shape')
    scores = np.clip(arrays[0], 0, 1)
    shared = arrays[1] == 1
    known, left_count, right_count, hypernym, hyponym, antonym = arrays[2:]
    unambiguous = (known == 1) & (left_count == 1) & (right_count == 1)
    counter = (hypernym == 1) | (hyponym == 1) | (antonym == 1)
    scores[unambiguous & shared & ~counter] = 1
    scores[unambiguous & ~shared & counter] = 0
    return scores


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
    return weighted_fusion(scores, embedding_weight=0.5)


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
    """Berechne das geometrische Mittel; ein Nullscore wirkt als Veto."""
    return np.sqrt(string_ensemble(scores) * multilingual_only(scores))


def exact_match_fusion(scores):
    """Setze echte Textgleichheit auf 1, sonst verwende den Hybridscore."""
    base = string_multilingual(scores)
    exact = _select(scores, ('exact_match',))['exact_match']
    return np.where(exact == 1, 1.0, base)


def consensus_fusion(scores, *, max_gap=0.2):
    """Mittle beide Embedding-Pfade, wenn sie sich einig sind; sonst gilt der niedrigere.

    Einig heißt: Die Werte weichen höchstens um max_gap ab (fester Wert, nicht getunt).
    Bei Uneinigkeit erzeugt ein einzelner Pfad keinen hohen Combined Score.
    """
    if (type(max_gap) not in (float, int) or not np.isfinite(max_gap)
            or not 0 <= max_gap <= 1):
        raise ValueError('max_gap must be in [0,1]')
    values = _select(scores, EMBEDDINGS)
    first, second = values['translated_embedding'], values['multilingual']
    return np.where(np.abs(first - second) <= max_gap,
                    (first + second) / 2, np.minimum(first, second))


def context_aware(scores, *, penalty=0.5):
    """Senke Scores gegenüber stärkeren Kandidaten derselben Aufgabe ab.

    Gleichstände werden nicht über IDs aufgelöst. Das ist keine 1:1-Zuordnung
    und keine Wahrscheinlichkeit; zusätzliche Aufgabentexte werden nicht verwendet.
    """
    if type(penalty) not in (float, int) or not np.isfinite(penalty) or not 0 <= penalty <= 1:
        raise ValueError('penalty must be in [0,1]')
    base = string_multilingual(scores)
    if base.size == 0:
        return base
    row_gap = base.max(axis=1, keepdims=True) - base
    column_gap = base.max(axis=0, keepdims=True) - base
    return np.clip(base - penalty * (row_gap + column_gap) / 2, 0, 1)


def label_part_fusion(scores, *, penalty=0.5):
    """Senke den Basisscore bei expliziten Labelkonflikten, sonst unverändert.

    penalty ist ein fester experimenteller Abschlag, keine Wahrscheinlichkeit.
    Fehlender Konflikt erhöht den Score ausdrücklich nicht.
    """
    if type(penalty) not in (float, int) or not np.isfinite(penalty) or not 0 <= penalty <= 1:
        raise ValueError('penalty must be in [0,1]')
    values = _select(scores, ('translated_embedding', 'label_part_compatibility'))
    return values['translated_embedding'] * (1 - penalty * (1 - values['label_part_compatibility']))


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
    'consensus_fusion': consensus_fusion,
    'context_aware': context_aware,
    'label_part_fusion': label_part_fusion,
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
    'consensus_fusion': EMBEDDINGS,
    'context_aware': ('levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'),
    'label_part_fusion': ('translated_embedding', 'label_part_compatibility'),
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
