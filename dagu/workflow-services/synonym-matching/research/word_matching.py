"""Greedy-Wort-Matching mit lokalen, vortrainierten Vektoren. Kein Modelltraining."""

import re

import numpy as np

from synonym_matching.preprocessing import Preprocessor, _language_model
from synonym_matching.cache import Cache
from synonym_matching.translation import Translator
from synonym_matching.service import nonempty_pairs


def greedy_matching(scores, delta=.2):
    """Wähle jeweils das größte Paar, entferne Zeile/Spalte und normiere wie im Paper.

    Zeilen/Spalten werden bei Gleichstand in Eingabereihenfolge gewählt.
    Einseitig leer ergibt nach der Formel delta, beidseitig leer explizit 0.
    """
    matrix = np.asarray(scores, dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all() or not 0 <= delta <= 1:
        raise ValueError('finite matrix and delta in [0,1] required')
    m, n = matrix.shape
    if max(m, n) == 0:
        return 0.0
    if min(m, n) == 0:
        return float(delta)
    remaining = matrix.copy()
    total = abs(m - n) * delta
    for _ in range(min(m, n)):
        row, column = np.unravel_index(remaining.argmax(), remaining.shape)
        total += remaining[row, column]
        remaining = np.delete(np.delete(remaining, row, axis=0), column, axis=1)
    return float(total / max(m, n))


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

    def __init__(self, config, translator=None, name="word_matching"):
        self.config = {'format': 'word2vec_text', 'delta': .2, 'nouns_only': False,
                       'lowercase': True, 'preprocessing': ['normalize', 'split_identifiers'],
                       'translate_to_en': False, **config}
        self.name = name
        self.preprocessor = Preprocessor(self.config['preprocessing'])
        self.files = config.get('files', {})
        if not self.files:
            raise ValueError('word vectors require files mapped by language')
        if len(self.files) > 1 and config.get('aligned') is not True:
            raise ValueError('multiple languages require explicitly aligned vector spaces')
        self.models = {}
        self.labels = {}
        self.translator = (translator or Translator({}, Cache())) if self.config['translate_to_en'] else None

    def prepare(self, element):
        key = (element['label'], element.get('language'))
        if key in self.labels:
            return self.labels[key]
        language = element.get('language')
        text = self.preprocessor.process(element['label'], language)
        if not text:
            return [], []
        if self.translator is not None:
            text = self.translator.translate([text], [language])[0]
            language = 'en'
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
        self.labels[key] = (words, vectors)
        return words, vectors

    def matrix(self, reference, student):
        result = np.zeros((len(reference), len(student)))
        left = [self.prepare(element) for element in reference]
        right = [self.prepare(element) for element in student]
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
                result[i, j] = greedy_matching(np.clip(scores, 0, 1), self.config['delta'])
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
