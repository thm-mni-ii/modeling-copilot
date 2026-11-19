"""Einmalige Labelzerlegung und Matching der separat bewerteten Bestandteile."""

import numpy as np
from scipy.optimize import linear_sum_assignment

from .combinations import SEMANTIC_METHODS, semantic_fusion
from .preprocessing import normalize, split_identifiers, split_label_parts


def label_components(text, language):
    """Nutze die vorhandene Zerlegung; unbekannte Wörter bleiben Bestandteile.

    Keine Rekursion, kein neues Wörterbuch. Wiederholte Bestandteile bleiben erhalten.
    Englische Mehrwortlabels und camelCase werden ebenfalls getrennt.
    """
    text = normalize(text)
    if not text:
        return []
    if language not in {'de', 'en'}:
        raise ValueError('component matching requires explicit de/en language')
    text = split_label_parts(text, language) if language == 'de' else split_identifiers(text)
    return text.split()


class ComponentMatching:
    """Bewerte eindeutige Komponenten gebündelt und verwende Modelle mehrfach."""

    def __init__(self, config, translator):
        # Der Import ist lokal, weil die normale Engine dieses Backend erzeugt.
        # Die innere Engine enthält ausschließlich vorhandene, nichtrekursive Methoden.
        from .service import MatchingEngine

        self.engine = MatchingEngine({
            'methods': list(SEMANTIC_METHODS),
            'preprocessing': ['normalize'], 'embedding_preprocessing': ['normalize'],
            'embedding': config['embedding'], 'lexicons': config['lexicons'],
            'seed': config['seed'],
            'combiner': {'kind': 'semantic', 'disabled': ['conflicts']},
        }, translator)
        self.features = {}
        self.evidence = {}

    def matrix(self, left, right, *, left_languages, right_languages):
        """Erzeuge Gesamtlabelscores durch optimale Paarung und Mittelwert.

        Alle Einzelscores werden über dieselbe Paarung aggregiert. Fehlende Partner
        zählen als 0; geteilt wird durch die größere Anzahl von Bestandteilen.
        Lexikon-Zählwerte bleiben intern; öffentlich erscheinen Mehrdeutigkeitsanteile.
        """
        shape = (len(left), len(right))
        unique = []
        indices = []
        for texts, languages in [(left, left_languages), (right, right_languages)]:
            parts = [[(word, language) for word in label_components(text, language)]
                     for text, language in zip(texts, languages, strict=True)]
            keys = list(dict.fromkeys(key for group in parts for key in group))
            positions = {key: i for i, key in enumerate(keys)}
            unique.append([{'id': str(i), 'label': word, 'language': lang}
                           for i, (word, lang) in enumerate(keys)])
            indices.append([[positions[key] for key in group] for group in parts])

        raw = self.engine.compute_scores(*unique)
        combined = semantic_fusion(raw['scores'], raw['semantic_features']['wordnet'],
                                   disabled=['conflicts'])
        # Kompatibilität wurde für dieselbe vorhandene Fusion berechnet, hier aber
        # ausdrücklich deaktiviert. Sie ist kein Bestandteil des neuen Scores.
        matrices = {name: values for name, values in raw['scores'].items()
                    if name != 'label_part_compatibility'}
        public = {}
        for name, values in matrices.items():
            if name.endswith('_synset_count'):
                name = name.replace('_synset_count', '_ambiguous')
                values = (values > 1).astype(float)
            public[name] = values
        self.features = {name: np.zeros(shape) for name in public}
        result = np.zeros(shape)
        alignments = [[[] for _ in right] for _ in left]
        for i, reference in enumerate(indices[0]):
            for j, student in enumerate(indices[1]):
                count = max(len(reference), len(student))
                if not reference or not student:
                    continue
                local = combined[np.ix_(reference, student)]
                rows, columns = linear_sum_assignment(local, maximize=True)
                a = np.asarray(reference)[rows]
                b = np.asarray(student)[columns]
                result[i, j] = combined[a, b].sum() / count
                for name, values in public.items():
                    self.features[name][i, j] = values[a, b].sum() / count
                alignments[i][j] = list(zip(a.tolist(), b.tolist()))
        self.evidence = {
            'policy': {'split_depth': 1, 'matching': 'optimal_1to1', 'aggregation': 'mean',
                       'unmatched_score': 0, 'component_fusion': 'semantic_without_conflicts'},
            'config': self.engine.config,
            'reference_components': unique[0], 'student_components': unique[1],
            'reference_indices': indices[0], 'student_indices': indices[1],
            'scores': {name: values.tolist() for name, values in raw['scores'].items()},
            'combinedScores': combined.tolist(), 'shape': list(combined.shape),
            'alignments': alignments,
        }
        return result
