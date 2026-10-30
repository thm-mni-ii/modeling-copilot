"""Steuert den Ablauf vom Labelpaar bis zur vollständigen Synonymmatrix.

Zeilen gehören zur Musterlösung, Spalten zur Schülerlösung. Die Engine liefert
ungerundete Scores; erst der CLI-Aufrufer rundet sie für die JSON-Ausgabe.
"""

import math
import random

import numpy as np

from .cache import Cache
from .combiners import combine
from .config import validate_config
from .lexicons import OpenThesaurus, WordNet
from .methods import EMBEDDING_MODELS, METHODS, EmbeddingMethod
from .preprocessing import Preprocessor, normalize
from .translation import Translator


def format_synonym_matrix(matrix):
    """Erzeuge eine Kopie mit gerundeten Scores, ohne Entscheidungen zu ändern."""
    formatted_rows = []
    for row in matrix:
        formatted_matches = []
        for match in row['matches']:
            formatted_match = match.copy()
            formatted_match['scores'] = {
                name: round(score, 4) for name, score in match['scores'].items()
            }
            formatted_match['combinedScore'] = round(match['combinedScore'], 4)
            formatted_matches.append(formatted_match)

        formatted_row = row.copy()
        formatted_row['matches'] = formatted_matches
        formatted_rows.append(formatted_row)
    return formatted_rows


def elements(values, prefix):
    """Prüfe Elemente und ergänze IDs, wenn die Eingabe nur aus Strings besteht.

    Bereits vorhandene IDs bleiben unverändert. Die Zahl 7 und der String '7'
    sind unterschiedliche IDs. Doppelte IDs innerhalb einer Liste sind ungültig.
    """
    if not isinstance(values, list):
        raise ValueError(f'{prefix} elements must be a list')

    result = []
    used_ids = set()
    for index, value in enumerate(values):
        if isinstance(value, str):
            item = {'id': f'{prefix}:{index}', 'label': value}
        else:
            item = value

        if not isinstance(item, dict) or not isinstance(item.get('label'), str):
            raise ValueError('every element must have a string label')
        if type(item.get('id')) not in (str, int) or item['id'] == '':
            raise ValueError('element IDs must be nonempty strings or integers')

        identifier = (type(item['id']), item['id'])
        if identifier in used_ids:
            raise ValueError(f"duplicate {prefix} ID: {item['id']}")
        used_ids.add(identifier)

        if 'language' in item:
            if not isinstance(item['language'], str) or not item['language']:
                raise ValueError('language must be a nonempty string')

        element = {'id': item['id'], 'label': item['label']}
        if 'language' in item:
            element['language'] = item['language']
        result.append(element)
    return result


def nonempty_pairs(reference_texts, student_texts):
    """Markiere die Matrixpositionen, an denen beide Texte nicht leer sind."""
    reference_valid = np.array(
        [bool(text.strip()) for text in reference_texts], dtype=bool
    )
    student_valid = np.array(
        [bool(text.strip()) for text in student_texts], dtype=bool
    )
    # Aus einer Spalte und einer Zeile entsteht die Referenz×Schüler-Maske.
    return reference_valid[:, None] & student_valid[None, :]


def build_candidates(reference, student, matrices, combined, valid, threshold):
    """Baue sortierte Kandidatenlisten aus ungerundeten Score-Matrizen."""
    rows = []
    for row_index, reference_element in enumerate(reference):
        order = sorted(
            range(len(student)),
            key=lambda column: (-combined[row_index, column], column),
        )
        matches = []
        for column in order:
            if not valid[row_index, column]:
                continue
            score = combined[row_index, column]
            if threshold is not None and score < threshold:
                continue
            matches.append({
                'submissionElement': student[column],
                'scores': {
                    name: float(matrix[row_index, column])
                    for name, matrix in matrices.items()
                },
                'combinedScore': float(score),
            })
        rows.append({'referenceElement': reference_element, 'matches': matches})
    return rows


class MatchingEngine:
    """Verbindet Preprocessing, Einzelmethoden und Score-Kombination.

    Eine Instanz kann mehrfach verwendet werden. Modelle und berechnete
    Übersetzungen/Embeddings bleiben dabei im Speicher und werden wiederverwendet.
    """

    def __init__(self, config=None):
        """Prüfe die Konfiguration und bereite die ausgewählten Verfahren vor."""
        self.config = validate_config(config)
        self.cache = Cache()
        self.string_preprocessor = Preprocessor(self.config['preprocessing'])
        self.embedding_preprocessor = Preprocessor(
            self.config['embedding_preprocessing']
        )
        self.methods = {}
        self.backends = {}
        for name in self.config['methods']:
            self.methods[name] = METHODS[name]
            if name in EMBEDDING_MODELS:
                options = self.config['embedding'].get(name, {})
                self.backends[name] = EmbeddingMethod(name, options, self.cache)
            elif name == 'wordnet':
                self.backends[name] = WordNet(self.config['lexicons'].get(name))
            elif name == 'openthesaurus':
                path = self.config['lexicons'].get(name)
                self.backends[name] = OpenThesaurus(path)

        translation_options = self.config['embedding'].get(
            'translated_embedding', {}
        )
        self.translator = Translator(translation_options, self.cache)
        if 'translated_embedding' in self.backends:
            # Alle übersetzenden Methoden teilen sich denselben Übersetzer.
            self.backends['translated_embedding'].translator = self.translator
        random.seed(self.config['seed'])
        np.random.seed(self.config['seed'])

    def _prepare_texts(self, name, labels, string_texts, embedding_texts,
                       languages, has_pairs):
        """Bereite Texte nur für das gerade ausgeführte Verfahren vor."""
        texts = string_texts
        backend = self.backends.get(name)
        if isinstance(backend, EmbeddingMethod) and has_pairs:
            texts = backend.prepare(embedding_texts, languages)
        if name in {'translated_string', 'wordnet'} and has_pairs:
            texts = self.translator.translate(string_texts, languages)
        if name == 'openthesaurus' and has_pairs:
            for text, language in zip(texts, languages):
                if text.strip() and language != 'de':
                    raise ValueError('OpenThesaurus requires explicit de language')
        if name == 'exact_match':
            # Stemming oder Lowercasing dürfen keinen exakten Treffer erzeugen.
            texts = [normalize(element['label']) for element in labels]
        return texts

    def match(self, reference, student, *, threshold=None):
        """Berechne alle Paar-Scores und die daraus abgeleitete Synonymmatrix.

        Args:
            reference: Labels oder Element-Dictionaries der Musterlösung.
            student: Labels oder Element-Dictionaries der Schülerlösung.
            threshold: Optionaler Mindestscore für die Kandidatenlisten.

        Returns:
            Dictionary mit vollständigen Einzel-/Combined-Matrizen und einer
            Synonymmatrix. Der Threshold filtert nur die Kandidatenlisten.
        """
        if threshold is not None:
            if (type(threshold) not in (float, int)
                    or not math.isfinite(threshold)
                    or not 0 <= threshold <= 1):
                raise ValueError('threshold must be null or a finite number in [0, 1]')

        reference = elements(reference, 'reference')
        student = elements(student, 'student')
        labels = reference + student
        split = len(reference)
        shape = (len(reference), len(student))
        languages = [element.get('language') for element in labels]

        string_texts = [
            self.string_preprocessor.process(element['label'], element.get('language'))
            for element in labels
        ]
        embedding_texts = None
        if any(name in EMBEDDING_MODELS for name in self.methods):
            embedding_texts = [
                self.embedding_preprocessor.process(element['label'], element.get('language'))
                for element in labels
            ]

        valid = nonempty_pairs(
            [element['label'] for element in reference],
            [element['label'] for element in student],
        )
        matrices = {}
        processed_labels = {}
        usable_pairs = {}
        for name, function in self.methods.items():
            texts = self._prepare_texts(
                name, labels, string_texts, embedding_texts, languages,
                bool(reference and student),
            )
            left = texts[:split]
            right = texts[split:]
            backend = self.backends.get(name)
            if backend is None:
                matrix = function(left, right)
            else:
                matrix = function(left, right, backend=backend)

            if matrix.shape != shape or not np.isfinite(matrix).all():
                raise ValueError(f'invalid score matrix from {name}')
            usable_pairs[name] = nonempty_pairs(left, right)
            matrix[~usable_pairs[name]] = 0
            matrix[~valid] = 0
            matrices[name] = matrix
            processed_labels[name] = {'reference': left, 'student': right}

        contributing = self.config['combiner']['methods']
        if self.config['combiner']['kind'] == 'variant':
            from .variants import REQUIRES
            contributing = REQUIRES[self.config['combiner']['name']]

        # Mindestens ein beteiligtes Verfahren braucht zwei verwendbare Texte.
        usable_combined = np.zeros(shape, dtype=bool)
        for name in contributing:
            usable_combined |= usable_pairs[name]
        valid &= usable_combined

        combined = combine(matrices, self.config['combiner'])
        if combined.shape != shape or not np.isfinite(combined).all():
            raise ValueError('combiner returned an invalid score matrix')
        combined = np.clip(combined, 0, 1)
        combined[~valid] = 0
        candidates = build_candidates(
            reference, student, matrices, combined, valid, threshold
        )
        return {
            'referenceElements': reference,
            'studentElements': student,
            'shape': list(shape),
            'scores': {name: matrix.tolist() for name, matrix in matrices.items()},
            'combinedScores': combined.tolist(),
            'synonymMatrix': candidates,
            'processedLabels': processed_labels,
        }
