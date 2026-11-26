"""Einmalige Labelzerlegung und Matching der separat bewerteten Bestandteile."""

import re

import numpy as np
from scipy.optimize import linear_sum_assignment

from .combinations import SEMANTIC_FEATURES, SEMANTIC_METHODS, STRINGS, semantic_fusion, string_ensemble
from .methods import label_part_compatibility
from .preprocessing import normalize, split_identifiers, split_label_parts


ATTRIBUTE_PARTS = {'nummer', 'number', 'raum', 'room'}


def label_components(text, language, *, targeted=False):
    """Nutze die vorhandene Zerlegung; unbekannte Wörter bleiben Bestandteile.

    Keine Rekursion, kein neues Wörterbuch. Wiederholte Bestandteile bleiben erhalten.
    Legacy trennt auch Mehrwortlabels; targeted erkennt nur Nummern-/Raumstrukturen
    und erhält mehrwortige Objektbezeichnungen als Ganzes.
    """
    text = normalize(text)
    if not text:
        return []
    if language not in {'de', 'en'}:
        raise ValueError('component matching requires explicit de/en language')
    if targeted and not re.search(r'.{3,}(?:nr\.?|nummer|number|raum|room)$', text, re.IGNORECASE):
        return [text]
    prepared = split_label_parts(text, language) if language == 'de' else split_identifiers(text)
    parts = prepared.split()
    if not targeted:
        return parts
    if len(parts) == 1:
        suffix = re.fullmatch(r'(.{3,}?)(nummer|number|raum|room)', prepared, re.IGNORECASE)
        if suffix:
            parts = list(suffix.groups())
    # Nur erkannte Nummern-/Raumstrukturen; normale Mehrwortlabels bleiben atomar.
    # Auch eine mehrwortige Objektbezeichnung wird als ein Bestandteil erhalten.
    if len(parts) > 1 and parts[-1].lower() in ATTRIBUTE_PARTS:
        return [' '.join(parts[:-1]), parts[-1]]
    return [text]


def merge_component_features(raw, reference, student, a, b, head):
    """Führe Merkmale einer ausgewählten Paarung zusammen, noch ohne Fusion.

    Scores werden gemittelt. Synonym-Evidenz erfordert vollständige Übereinstimmung.
    Relationen/Taxonomie des Objekts gelten nur bei synonymen übrigen Bestandteilen.
    """
    count = max(len(reference), len(student))
    matrices = raw['scores']
    features = raw['semantic_features']['wordnet']
    values = {name: float(matrices[name][a, b].sum() / count)
              for name in STRINGS + ('translated_embedding',)}
    shared = matrices['wordnet'][a, b] == 1
    complete = len(a) == len(reference) == len(student)
    values['wordnet'] = float(complete and shared.all())
    reference_counts = features['reference_synset_count'][reference, student[0]]
    student_counts = features['student_synset_count'][reference[0], student]
    known_reference = bool((reference_counts > 0).all())
    known_student = bool((student_counts > 0).all())
    merged = dict.fromkeys(SEMANTIC_FEATURES, 0.)
    merged.update(reference_known=float(known_reference), student_known=float(known_student),
                  pair_known=float(known_reference and known_student),
                  reference_synset_count=float(reference_counts.max()),
                  student_synset_count=float(student_counts.max()))
    context_matches = complete and head.any() and shared[~head].all()
    if context_matches:
        for name in ('reference_hypernym', 'reference_hyponym', 'antonym'):
            merged[name] = float((features[name][a[head], b[head]] == 1).any())
        available = (features['taxonomy_available'][a[head], b[head]] == 1).all()
        if available:
            merged['taxonomy_available'] = 1.
            for name in ('path_similarity', 'wup_similarity'):
                merged[name] = float(features[name][a[head], b[head]].mean())
    return values, merged


class ComponentMatching:
    """Bewerte eindeutige Komponenten gebündelt und verwende Modelle mehrfach."""

    def __init__(self, config, translator, *, feature_first=False):
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
        self.feature_first = feature_first

    def matrix(self, left, right, *, left_languages, right_languages):
        """Paare Bestandteile und aggregiere je nach gewähltem Experiment.

        Legacy: Mittel der fusionierten Komponentenscores. Feature-first: separate
        Merkmalsaggregation, dann volle Fusion. Fehlende Partner zählen als 0.
        Lexikon-Zählwerte bleiben intern; öffentlich erscheinen Mehrdeutigkeitsanteile.
        """
        shape = (len(left), len(right))
        unique = []
        indices = []
        roles = []
        for texts, languages in [(left, left_languages), (right, right_languages)]:
            parts = [[(word, language) for word in label_components(text, language,
                                                                  targeted=self.feature_first)]
                     for text, language in zip(texts, languages, strict=True)]
            keys = list(dict.fromkeys(key for group in parts for key in group))
            positions = {key: i for i, key in enumerate(keys)}
            unique.append([{'id': str(i), 'label': word, 'language': lang}
                           for i, (word, lang) in enumerate(keys)])
            indices.append([[positions[key] for key in group] for group in parts])
            roles.append([['object'] + ['attribute'] * (len(group) - 1) if group else []
                          for group in parts])

        raw = self.engine.compute_scores(*unique)
        if self.feature_first:
            # Dieser Wert dient nur der Paarung, nicht als Komponenten-CombinedScore.
            combined = (np.clip(raw['scores']['translated_embedding'], 0, 1)
                        + string_ensemble(raw['scores'])) / 2
        else:
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
        merged_scores = {name: np.zeros(shape) for name in SEMANTIC_METHODS}
        merged_features = {name: np.zeros(shape) for name in
                           SEMANTIC_FEATURES + ('reference_known', 'student_known')}
        alignments = [[[] for _ in right] for _ in left]
        for i, reference in enumerate(indices[0]):
            for j, student in enumerate(indices[1]):
                count = max(len(reference), len(student))
                if not reference or not student:
                    continue
                local = combined[np.ix_(reference, student)]
                allowed = np.ones(local.shape, dtype=bool)
                if self.feature_first:
                    allowed = np.equal.outer(roles[0][i], roles[1][j])
                    local = np.where(allowed, local, -1)
                rows, columns = linear_sum_assignment(local, maximize=True)
                selected = allowed[rows, columns]
                rows, columns = rows[selected], columns[selected]
                a = np.asarray(reference)[rows]
                b = np.asarray(student)[columns]
                if self.feature_first:
                    head = np.array([roles[0][i][row] == 'object' for row in rows])
                    values, semantics = merge_component_features(raw, reference, student, a, b, head)
                    for name, value in values.items():
                        merged_scores[name][i, j] = value
                    for name, value in semantics.items():
                        merged_features[name][i, j] = value
                else:
                    result[i, j] = combined[a, b].sum() / count
                    for name, values in public.items():
                        self.features[name][i, j] = values[a, b].sum() / count
                alignments[i][j] = list(zip(a.tolist(), b.tolist()))
        if self.feature_first:
            # Genau dieselbe vollständige Fusion wie beim Gesamtlabel-Vergleich,
            # einschließlich der bisherigen optionalen Konfliktheuristik.
            merged_scores['label_part_compatibility'] = label_part_compatibility(left, right)
            result = semantic_fusion(merged_scores, merged_features)
            self.features = dict(merged_scores)
            self.features['wordnet_shared_synset'] = merged_scores['wordnet']
            for name, values in merged_features.items():
                if name.endswith('_synset_count'):
                    name = name.replace('_synset_count', '_ambiguous')
                    values = (values > 1).astype(float)
                self.features[f'wordnet_{name}'] = values
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
        if self.feature_first:
            self.evidence.pop('combinedScores')
            self.evidence.update(
                policy={'split_depth': 1, 'split': 'number_or_room_structure',
                        'matching': 'role_constrained_optimal_1to1',
                        'aggregation': 'feature_specific_then_semantic_fusion', 'unmatched_score': 0,
                        'alignment_basis': 'mean(string_ensemble, embedding)',
                        'final_fusion': 'semantic', 'conflict_rule': 'unchanged'},
                alignmentScores=combined.tolist(), reference_roles=roles[0], student_roles=roles[1],
                whole_label_scores={k: v.tolist() for k, v in merged_scores.items()},
                whole_label_semantic_features={k: v.tolist() for k, v in merged_features.items()},
            )
        return result
