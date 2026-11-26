"""Gleichwertige Bestandteile ohne Objekt-/Attributrollen, dann Evidenzfusion."""

import re

import numpy as np
from scipy.optimize import linear_sum_assignment

from .combinations import SEMANTIC_FEATURES, STRINGS, string_ensemble
from .preprocessing import (_compound_words, expand_abbreviations, normalize,
                            split_identifiers, split_label_parts)


def general_components(text, language):
    """Zerlege nur bei sichtbaren Indizien; bekannte Ganzwörter bleiben erhalten."""
    text = normalize(text)
    if not text:
        return []
    if language not in {'de', 'en'}:
        raise ValueError('component evidence requires explicit de/en language')
    expanded = expand_abbreviations(text, language)
    identified = split_identifiers(expanded)
    # Sichtbare Grenzen auf beiden Seiten gleich behandeln. Punkte sind keine
    # pauschalen Trenner; Nr. wurde bereits aufgelöst. E-Mail bleibt ein Begriff.
    parts = []
    for token in identified.split():
        parts.extend([token] if token.casefold() == 'e-mail' else
                     re.split(r'(?<=[^\W\d_])[-‐‑–](?=[^\W\d_])', token))
    if len(parts) > 1 or identified != text:
        return parts
    if language == 'de' and text.isalpha() and text.lower() not in _compound_words():
        return split_label_parts(text, language).split()
    return [text]


class ComponentEvidence:
    """Bündele Komponenten über die vorhandene Engine, ohne Rollen oder Konfliktregel."""

    def __init__(self, config, translator):
        from .service import MatchingEngine

        self.engine = MatchingEngine({
            'methods': list(STRINGS) + ['translated_embedding', 'wordnet'],
            'preprocessing': ['normalize'], 'embedding_preprocessing': ['normalize'],
            'embedding': config['embedding'], 'lexicons': config['lexicons'],
            'seed': config['seed'], 'semantic_features': {'wordnet': list(SEMANTIC_FEATURES)},
        }, translator)
        self.features = {}
        self.evidence = {}

    def matrix(self, left, right, *, left_languages, right_languages):
        unique, indices = [], []
        parsed = [
            [general_components(text, language) for text, language in zip(texts, languages, strict=True)]
            for texts, languages in [(left, left_languages), (right, right_languages)]
        ]
        for side, languages in zip(parsed, [left_languages, right_languages], strict=True):
            parts = side
            keys = list(dict.fromkeys((word, lang) for group, lang in zip(parts, languages, strict=True)
                                      for word in group))
            positions = {key: i for i, key in enumerate(keys)}
            unique.append([{'id': str(i), 'label': word, 'language': lang}
                           for i, (word, lang) in enumerate(keys)])
            indices.append([[positions[word, lang] for word in group]
                            for group, lang in zip(parts, languages, strict=True)])
        raw = self.engine.compute_scores(*unique)
        return self.aggregate(raw, unique, indices, left, right)

    def aggregate(self, raw, unique, indices, left, right):
        """Fasse feste Teilzuordnungen zusammen; auch mit gespeicherten Rohscores."""
        scores = raw['scores']
        semantics = raw['semantic_features']['wordnet']
        alignment = (string_ensemble(scores) + np.clip(scores['translated_embedding'], 0, 1)) / 2
        shape = (len(left), len(right))
        names = ('string_similarity', 'embedding_similarity', 'lexicon_coverage',
                 'reference_coverage', 'student_coverage', 'shared_synset_fraction',
                 'reference_ambiguity', 'student_ambiguity',
                 'shared_synset', 'full_synonym_evidence', 'antonym_relation',
                 'hypernym_relation', 'hyponym_relation', 'antonym_evidence',
                 'hierarchy_evidence', 'ontology_similarity', 'taxonomy_coverage')
        self.features = {name: np.zeros(shape) for name in names}
        for name in ('levenshtein', 'jaro_winkler', 'char_trigram'):
            self.features[name] = np.zeros(shape)
        pairs = [[[] for _ in right] for _ in left]
        for i, reference in enumerate(indices[0]):
            for j, student in enumerate(indices[1]):
                if not reference or not student:
                    continue
                rows, columns = linear_sum_assignment(alignment[np.ix_(reference, student)], maximize=True)
                a, b = np.asarray(reference)[rows], np.asarray(student)[columns]
                count = max(len(reference), len(student))
                pairs[i][j] = list(zip(a.tolist(), b.tolist()))
                for name in ('levenshtein', 'jaro_winkler', 'char_trigram'):
                    self.features[name][i, j] = scores[name][a, b].sum() / count
                f = self.features
                f['string_similarity'][i, j] = sum(f[n][i, j] for n in
                                                   ('levenshtein', 'jaro_winkler', 'char_trigram')) / 3
                f['embedding_similarity'][i, j] = scores['translated_embedding'][a, b].sum() / count
                known = semantics['pair_known'][a, b] == 1
                shared = scores['wordnet'][a, b] == 1
                unambiguous = ((semantics['reference_synset_count'][a, b] == 1)
                               & (semantics['student_synset_count'][a, b] == 1))
                complete = len(reference) == len(student) == len(a)
                f['lexicon_coverage'][i, j] = known.sum() / count
                f['reference_coverage'][i, j] = np.mean(
                    semantics['reference_synset_count'][reference, student[0]] > 0)
                f['student_coverage'][i, j] = np.mean(
                    semantics['student_synset_count'][reference[0], student] > 0)
                f['reference_ambiguity'][i, j] = np.mean(
                    semantics['reference_synset_count'][reference, student[0]] > 1)
                f['student_ambiguity'][i, j] = np.mean(
                    semantics['student_synset_count'][reference[0], student] > 1)
                f['shared_synset_fraction'][i, j] = shared.sum() / count
                f['shared_synset'][i, j] = float(complete and shared.all())
                for source, target in [('antonym', 'antonym_relation'),
                                       ('reference_hypernym', 'hypernym_relation'),
                                       ('reference_hyponym', 'hyponym_relation')]:
                    f[target][i, j] = (semantics[source][a, b] == 1).sum() / count
                antonym = semantics['antonym'][a, b] == 1
                hierarchy = ((semantics['reference_hypernym'][a, b] == 1)
                             | (semantics['reference_hyponym'][a, b] == 1))
                f['full_synonym_evidence'][i, j] = float(complete and shared.all()
                    and known.all() and unambiguous.all() and not (antonym | hierarchy).any())
                usable = known & unambiguous & ~shared
                f['antonym_evidence'][i, j] = float((antonym & usable).any())
                # Übertrage eine Hierarchiebeziehung nur bei synonymem Rest.
                candidates = hierarchy & usable
                f['hierarchy_evidence'][i, j] = float(complete and candidates.any()
                                                     and (shared | candidates).all())
                available = semantics['taxonomy_available'][a, b] == 1
                f['taxonomy_coverage'][i, j] = available.sum() / count
                if available.any():
                    q = (semantics['path_similarity'][a, b] + semantics['wup_similarity'][a, b]) / 2
                    f['ontology_similarity'][i, j] = q[available].mean()
        base = (self.features['string_similarity']
                + np.clip(self.features['embedding_similarity'], 0, 1)) / 2
        self.evidence = {
            'policy': {'roles': False, 'matching': 'optimal_1to1', 'split_depth': 1,
                       'unmatched_score': 0, 'aggregation': 'equal_component_weights'},
            'reference_components': unique[0], 'student_components': unique[1],
            'reference_indices': indices[0], 'student_indices': indices[1],
            'shape': list(alignment.shape), 'alignmentScores': alignment.tolist(),
            'alignments': pairs, 'scores': {k: v.tolist() for k, v in scores.items()},
            'whole_label_features': {k: v.tolist() for k, v in self.features.items()},
        }
        return base
