"""Wort-Matching mit lokalen, vortrainierten Vektoren. Kein Modelltraining."""

import re

import numpy as np
from scipy.optimize import linear_sum_assignment

from synonym_matching.preprocessing import Preprocessor, _language_model
from synonym_matching.service import nonempty_pairs


def _checked(scores, delta):
    """Prüfe die Wortmatrix; liefere sie und das feste Ergebnis für leere Wortmengen."""
    matrix = np.asarray(scores, dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all() or not 0 <= delta <= 1:
        raise ValueError('finite matrix and delta in [0,1] required')
    m, n = matrix.shape
    if max(m, n) == 0:
        return matrix, 0.0
    if min(m, n) == 0:
        return matrix, float(delta)
    return matrix, None


def greedy_matching(scores, delta=.2):
    """Wähle jeweils das größte Paar, entferne Zeile/Spalte und normiere wie im Paper.

    Zeilen/Spalten werden bei Gleichstand in Eingabereihenfolge gewählt.
    Einseitig leer ergibt nach der Formel delta, beidseitig leer explizit 0.
    """
    matrix, empty = _checked(scores, delta)
    if empty is not None:
        return empty
    m, n = matrix.shape
    remaining = matrix.copy()
    total = abs(m - n) * delta
    for _ in range(min(m, n)):
        row, column = np.unravel_index(remaining.argmax(), remaining.shape)
        total += remaining[row, column]
        remaining = np.delete(np.delete(remaining, row, axis=0), column, axis=1)
    return float(total / max(m, n))


def optimal_matching(scores, delta=.2):
    """Wie greedy_matching, aber die 1:1-Wortpaare maximieren die Gesamtsumme (Hungarian)."""
    matrix, empty = _checked(scores, delta)
    if empty is not None:
        return empty
    m, n = matrix.shape
    rows, columns = linear_sum_assignment(matrix, maximize=True)
    return float((matrix[rows, columns].sum() + abs(m - n) * delta) / max(m, n))


def bidirectional_matching(scores, delta=.2):
    """Jedes Wort sucht sein bestes Gegenstück, in beide Richtungen; Mittel beider Richtungen.

    Kein 1:1: Mehrere Wörter dürfen dasselbe Gegenstück wählen. Dadurch ist der Wert
    symmetrisch. Leere Wortmengen verhalten sich wie bei greedy_matching.
    """
    matrix, empty = _checked(scores, delta)
    if empty is not None:
        return empty
    return float((matrix.max(axis=1).mean() + matrix.max(axis=0).mean()) / 2)


MATCHING = {'greedy': greedy_matching, 'optimal': optimal_matching,
            'bidirectional': bidirectional_matching}


def load_vectors(path, fmt):
    """Nutze native FastText-Binärmodelle und Gensim für reine Vektordateien."""
    if fmt == 'fasttext_bin':
        # Gensim kopiert hier große Matrizen und berechnet den ganzen Wortschatz.
        import fasttext
        return fasttext.load_model(str(path))
    from gensim.models import KeyedVectors
    if fmt not in {'word2vec_text', 'word2vec_binary', 'glove'}:
        raise ValueError(f'unknown vector format: {fmt}')
    # Einzelne Originalvokabulare enthalten ungültige UTF-8-Bytes in Wortschlüsseln.
    return KeyedVectors.load_word2vec_format(path, binary=fmt == 'word2vec_binary',
                                            no_header=fmt == 'glove', unicode_errors='replace')


class WordMatching:
    """Lade Vektoren einmal je Sprache und bereite jedes Label nur einmal vor."""

    def __init__(self, config, translator=None, name="word_matching", models=None):
        self.config = {'format': 'word2vec_text', 'delta': .2, 'nouns_only': False,
                       'lowercase': True, 'matching': 'greedy',
                       'preprocessing': ['normalize', 'split_identifiers'], **config}
        if self.config['matching'] not in MATCHING:
            raise ValueError(f"unknown matching: {self.config['matching']}")
        self.name = name
        # Dieselbe Vorverarbeitung wie im Service, inklusive des Schritts 'translate'.
        self.preprocessor = Preprocessor(self.config['preprocessing'], translator)
        self.files = config.get('files', {})
        if not self.files:
            raise ValueError('word vectors require files mapped by language')
        if len(self.files) > 1 and config.get('aligned') is not True:
            raise ValueError('multiple languages require explicitly aligned vector spaces')
        # Ein von außen übergebenes Dict teilt geladene Modelle zwischen Preprocessing-Varianten.
        self.models = {} if models is None else models
        self.labels = {}

    def prepare(self, element):
        return self.prepare_all([element])[0]

    def prepare_all(self, elements):
        """Bereite alle noch unbekannten Labels gebündelt vor (die Übersetzung läuft im Stapel)."""
        pending = {}
        for element in elements:
            key = (element['label'], element.get('language'))
            if key not in self.labels:
                pending[key] = element
        if pending:
            texts, languages = self.preprocessor.process_many(
                [label for label, _ in pending], [language for _, language in pending])
            for key, text, language in zip(pending, texts, languages):
                self.labels[key] = self._words_and_vectors(text, language)
        return [self.labels[(e['label'], e.get('language'))] for e in elements]

    def _words_and_vectors(self, text, language):
        if not text:
            return [], []
        if language not in self.files:
            raise ValueError(f'no word vectors configured for language {language!r}')
        if self.config.get('nouns_only', False):
            if language not in {'de', 'en'}:
                raise ValueError('noun filtering requires de/en spaCy models')
            words = [token.text for token in _language_model(language)(text)
                     if token.pos_ in {'NOUN', 'PROPN'}]
        else:
            words = re.findall(r"\w+(?:['’-]\w+)*", text, flags=re.UNICODE)
        if self.config.get('lowercase', True):
            words = [word.lower() for word in words]
        # Die Arbeit beschreibt Wortmengen, keine mehrfach gezählten identischen Wörter.
        words = list(dict.fromkeys(words))
        if words and language not in self.models:
            self.models[language] = load_vectors(self.files[language], self.config['format'])
        model = self.models.get(language, {})
        vectors = []
        for word in words:
            try:
                value = np.asarray(model[word], dtype=float)
                length = np.linalg.norm(value)
                if value.ndim != 1 or not np.isfinite(value).all() or length == 0:
                    raise KeyError(word)
                vectors.append(value / length)
            except KeyError:
                vectors.append(None)
        return words, vectors

    def matrix(self, reference, student):
        result = np.zeros((len(reference), len(student)))
        left = self.prepare_all(reference)
        right = self.prepare_all(student)
        for i, first in enumerate(left):
            for j, second in enumerate(right):
                if not reference[i]['label'].strip() or not student[j]['label'].strip():
                    continue
                scores = np.zeros((len(first[0]), len(second[0])))
                for a, vector_a in enumerate(first[1]):
                    for b, vector_b in enumerate(second[1]):
                        if vector_a is not None and vector_b is not None:
                            if vector_a.shape != vector_b.shape:
                                raise ValueError('word vectors must have the same dimension')
                            scores[a, b] = np.dot(vector_a, vector_b)
                result[i, j] = MATCHING[self.config['matching']](
                    np.clip(scores, 0, 1), self.config['delta'])
        return result

    def compute_scores(self, reference, student):
        """Liefere dieselben Rohscore-Felder wie der vorhandene Matching-Kern."""
        matrix = self.matrix(reference, student)
        valid = nonempty_pairs([e['label'] for e in reference], [e['label'] for e in student])
        texts = {side: [' '.join(self.prepare(e)[0]) for e in elements]
                 for side, elements in [('reference', reference), ('student', student)]}
        return {'shape': list(matrix.shape), 'scores': {self.name: matrix},
                'processedLabels': {self.name: texts}, 'validPairs': valid,
                'usablePairs': {self.name: valid}}
