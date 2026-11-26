"""Direkter Laufzeitkern: frische Labelmengen hinein, vollständige Matrix heraus."""

import math

import numpy as np

from .decision import decide
from .lexicons import LexiconMatcher
from .methods import SentenceEmbedding
from .preprocessing import canonical, expanded, expand_modeling_abbreviations


def elements(items, prefix):
    """Originalmetadaten erhalten; Stringlisten bekommen stabile lokale IDs."""
    if not isinstance(items, list):
        raise ValueError('elements must be a list')
    result, used = [], set()
    for index, value in enumerate(items):
        item = {'id': f'{prefix}:{index}', 'label': value} if isinstance(value, str) else value
        if not isinstance(item, dict) or not isinstance(item.get('label'), str):
            raise ValueError('each element needs a string label')
        if type(item.get('id')) not in (str, int) or item['id'] == '':
            raise ValueError('each element needs a nonempty string/integer id')
        identity = (type(item['id']), item['id'])
        if identity in used:
            raise ValueError('duplicate element id within one input list')
        used.add(identity)
        result.append(item.copy())
    return result


def nonempty_pairs(left, right):
    """Leere Labels sind nicht bewertbar, behalten aber ihre Matrixposition."""
    return np.asarray([bool(t.strip()) for t in left], dtype=bool)[:, None] & np.asarray(
        [bool(t.strip()) for t in right], dtype=bool)[None, :]


class MatchingPipeline:
    """Ein wiederverwendbares Objekt pro Prozess, ohne Forschungsimporte."""

    def __init__(self, *, embedding_model='jina_de', lexicon_mode='odenet_linked',
                 spelling_threshold=.85, meaning_threshold=.85, exact_first=False,
                 lexicon_path=None):
        if lexicon_mode not in {'odenet', 'odenet_first', 'odenet_linked'}:
            raise ValueError('unknown lexicon mode')
        self.embedding_model, self.lexicon_mode = embedding_model, lexicon_mode
        self.spelling_threshold, self.meaning_threshold = spelling_threshold, meaning_threshold
        self.exact_first = exact_first
        self._validate_thresholds(spelling_threshold, meaning_threshold)
        if type(exact_first) is not bool:
            raise ValueError('exact_first must be boolean')
        self.embedding = SentenceEmbedding(embedding_model)
        self.lexicons = LexiconMatcher(lexicon_path)

    @staticmethod
    def _validate_thresholds(*values):
        if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError('thresholds must be finite numbers in [0,1]')

    def features(self, reference, student):
        """Rohmerkmale ungerundet berechnen; jedes Textlabel wiederverwenden."""
        from .methods import damerau_matrix
        reference, student = elements(reference, 'r'), elements(student, 's')
        labels = [[e['label'] for e in side] for side in (reference, student)]
        strings = [[canonical(t) for t in side] for side in labels]
        embedding = self.embedding.matrix(*[[expanded(t) for t in side] for side in labels])
        spelling = damerau_matrix(*strings)
        texts = [[expand_modeling_abbreviations(t) for t in side] for side in labels]
        routes = [[self.lexicons.route(raw, prepared, self.lexicon_mode) if raw.strip() else None
                   for raw, prepared in zip(original, prepared_side, strict=True)]
                  for original, prepared_side in zip(labels, texts, strict=True)] if nonempty_pairs(*labels).any() else [
                      [None for _ in side] for side in labels]
        values = []
        for i, a in enumerate(reference):
            row = []
            for j, b in enumerate(student):
                lex = self.lexicons.pair_features(texts[0][i], texts[1][j], routes[0][i], routes[1][j],
                                                 mode=self.lexicon_mode)
                row.append({'damerau_canonical': float(spelling[i,j]),
                            'embedding_similarity': float(embedding[i,j]), **lex})
            values.append(row)
        return {'reference': reference, 'student': student, 'scores': values,
                'routes': {'reference': routes[0], 'student': routes[1]}}

    def from_features(self, data, *, meaning_threshold=None, decimals=4):
        """Aus denselben Rohwerten verschiedene Thresholds prüfen, ohne neue Inferenz."""
        threshold = self.meaning_threshold if meaning_threshold is None else meaning_threshold
        self._validate_thresholds(threshold)
        matrix = []
        for i, a in enumerate(data['reference']):
            matches = []
            for j, b in enumerate(data['student']):
                scores = data['scores'][i][j]
                verdict, reason = decide(scores, a['label'], b['label'], spelling_threshold=self.spelling_threshold,
                                          meaning_threshold=threshold, exact_first=self.exact_first)
                shown = scores.copy() if decimals is None else {k: round(v, decimals) for k, v in scores.items()}
                matches.append({'submissionElement': b, 'scores': shown, 'verdict': verdict, 'reason': reason})
            matrix.append({'referenceElement': a, 'matches': matches})
        return {'synonymMatrix': matrix}

    def match(self, reference, student):
        """Öffentliche Funktion: keine Filterung, kein künstlicher Combined Score."""
        return self.from_features(self.features(reference, student))
