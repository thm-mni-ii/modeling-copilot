"""Steuert den Ablauf vom Labelpaar bis zur vollständigen Synonymmatrix.

Zeilen gehören zur Musterlösung, Spalten zur Schülerlösung. Die Engine liefert
ungerundete Scores; erst die Ausgabeformatierung rundet sie für JSON.
"""

import math

import numpy as np

from .cache import Cache
from .combinations import combine
from .config import validate_config
from .lexicons import OpenThesaurus, WordNet
from .methods import EMBEDDING_MODELS, METHODS, METHOD_TRAITS, EmbeddingMethod
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

    def __init__(self, config=None, translator=None):
        """Prüfe die Konfiguration und bereite die ausgewählten Verfahren vor.

        Ein übergebener Übersetzer wird mitbenutzt, damit mehrere Engines das
        Übersetzungsmodell nur einmal laden.
        """
        self.config = validate_config(config)
        self.cache = Cache()
        translation_options = self.config['embedding'].get(
            'translated_embedding', {}
        )
        # Alle übersetzenden Teile (Schritt 'translate', Verfahren) teilen sich einen Übersetzer.
        self.translator = translator or Translator(translation_options, self.cache)
        self.string_preprocessor = Preprocessor(self.config['preprocessing'], self.translator)
        self.embedding_preprocessor = Preprocessor(
            self.config['embedding_preprocessing'], self.translator
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
        if 'translated_embedding' in self.backends:
            self.backends['translated_embedding'].translator = self.translator

    def _prepare_texts(self, name, labels, string_texts, embedding_texts,
                       string_languages, embedding_languages, has_pairs):
        """Bereite Texte nur für das gerade ausgeführte Verfahren vor.

        Die Sprachen sind die nach dem Preprocessing: Ein Text nach dem Schritt
        'translate' gilt als englisch und wird nicht ein zweites Mal übersetzt.
        """
        texts, languages = string_texts, string_languages
        traits = METHOD_TRAITS.get(name, ())
        backend = self.backends.get(name)
        if isinstance(backend, EmbeddingMethod) and has_pairs:
            texts = backend.prepare(embedding_texts, embedding_languages)
        if 'translate' in traits and has_pairs:
            texts = self.translator.translate(string_texts, string_languages)
        if 'german_only' in traits and has_pairs:
            for text, language in zip(texts, languages):
                if text.strip() and language != 'de':
                    raise ValueError('OpenThesaurus requires explicit de language')
        if 'original_text' in traits:
            # Stemming oder Lowercasing dürfen keinen exakten Treffer erzeugen.
            texts = [normalize(element['label']) for element in labels]
        return texts

    def compute_scores(self, reference, student):
        """Berechne ungerundete NumPy-Matrizen ohne Kombination und Kandidatenlisten.

        Der Forschungspfad kombiniert dieselben Rohscores mehrfach. Deshalb werden
        hier weder Kandidaten sortiert noch Matrizen in JSON-Listen umgewandelt.
        """
        reference = elements(reference, 'reference')
        student = elements(student, 'student')
        labels = reference + student
        split = len(reference)
        shape = (len(reference), len(student))
        label_texts = [element['label'] for element in labels]
        languages = [element.get('language') for element in labels]

        string_texts, string_languages = self.string_preprocessor.process_many(
            label_texts, languages
        )
        embedding_texts = embedding_languages = None
        if any(name in EMBEDDING_MODELS for name in self.methods):
            embedding_texts, embedding_languages = self.embedding_preprocessor.process_many(
                label_texts, languages
            )

        valid = nonempty_pairs(
            [element['label'] for element in reference],
            [element['label'] for element in student],
        )
        matrices = {}
        processed_labels = {}
        usable_pairs = {}
        for name, function in self.methods.items():
            texts = self._prepare_texts(
                name, labels, string_texts, embedding_texts, string_languages,
                embedding_languages, bool(reference and student),
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

        return {
            'referenceElements': reference,
            'studentElements': student,
            'shape': list(shape),
            'scores': matrices,
            'processedLabels': processed_labels,
            'validPairs': valid,
            'usablePairs': usable_pairs,
        }

    def match(self, reference, student, *, threshold=None):
        """Berechne Scores, kombiniere sie und baue die sortierte Synonymmatrix.

        Der Threshold filtert nur Kandidaten; die vollständigen Rohmatrizen
        bleiben für bestehende Aufrufer im Ergebnis erhalten.
        """
        if threshold is not None:
            if (type(threshold) not in (float, int)
                    or not math.isfinite(threshold)
                    or not 0 <= threshold <= 1):
                raise ValueError('threshold must be null or a finite number in [0, 1]')

        result = self.compute_scores(reference, student)
        reference = result['referenceElements']
        student = result['studentElements']
        shape = tuple(result['shape'])
        matrices = result['scores']
        valid = result['validPairs']
        usable_pairs = result['usablePairs']
        processed_labels = result['processedLabels']
        contributing = self.config['combiner']['methods']
        if self.config['combiner']['kind'] == 'variant':
            from .combinations import REQUIRES
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


def match(reference, student, config=None, *, threshold=None):
    """Vergleiche zwei Labelmengen mit den konfigurierten Verfahren.

    Ohne Konfiguration gilt die vorläufige 50:50-String-/Embedding-Pipeline.
    Über ``methods`` und ``combiner`` können andere Verfahren gewählt werden. IDs und Originaltexte
    bleiben erhalten; nur die ausgegebenen Scores werden auf vier Stellen gerundet.
    """
    result = MatchingEngine(config).match(reference, student, threshold=threshold)
    return {'synonymMatrix': format_synonym_matrix(result['synonymMatrix'])}
