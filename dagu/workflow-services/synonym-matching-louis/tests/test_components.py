"""Komponentenpaarung, fehlende Bestandteile und unveränderte öffentliche Struktur."""

import json
from pathlib import Path
from unittest.mock import Mock

import jsonschema
import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.combinations import SEMANTIC_FEATURES, SEMANTIC_METHODS, semantic_fusion
from synonym_matching.components import label_components


@pytest.fixture
def component_engine(monkeypatch):
    monkeypatch.setattr('synonym_matching.preprocessing._compound_words',
                        lambda: {'gebäude', 'nummer', 'gerät', 'raum'})
    engine = MatchingEngine({'methods': ['component_matching']})
    backend = engine.backends['component_matching']

    def compute(reference, student):
        shape = (len(reference), len(student))
        values = np.array([[1. if a['label'].lower() == b['label'].lower() else .2
                            for b in student] for a in reference]).reshape(shape)
        scores = {name: values.copy() for name in SEMANTIC_METHODS}
        scores['wordnet'][:] = 0
        scores['label_part_compatibility'][:] = 1
        features = {name: np.zeros(shape) for name in SEMANTIC_FEATURES}
        # Zählwerte > 1 dürfen nicht als neue öffentliche Similarity-Scores erscheinen.
        features['pair_known'][:] = 1
        features['reference_synset_count'][:] = features['student_synset_count'][:] = 2
        scores.update({f'wordnet_{name}': a for name, a in features.items()})
        return {'scores': scores, 'semantic_features': {'wordnet': features}}

    monkeypatch.setattr(backend.engine, 'compute_scores', Mock(side_effect=compute))
    return engine


def element(identifier, label, language='de'):
    return {'id': identifier, 'label': label, 'language': language}


def test_split_once_preserves_duplicates_and_requires_language(component_engine):
    assert label_components('GebäudeNr.', 'de') == ['Gebäude', 'Nummer']
    assert label_components('Geräteraum', 'de') == ['geräte', 'raum']
    assert label_components('buildingNumber', 'en') == ['building', 'Number']
    assert label_components('Nummer Nummer', 'de') == ['Nummer', 'Nummer']
    assert label_components('', None) == []
    with pytest.raises(ValueError, match='de/en'):
        label_components('Gebäude', None)


def test_matching_and_missing_parts_are_aggregated_without_fixed_conflict_penalty(component_engine):
    engine = component_engine
    result = engine.match([element('r', 'GebäudeNr.')],
                          [element('s1', 'Gebäudenummer'), element('s2', 'Gebäude')])
    np.testing.assert_allclose(result['combinedScores'], [[1, .5]])
    assert result['scores']['component_matching_wordnet_reference_ambiguous'] == [[1, .5]]
    assert 'component_matching_wordnet_reference_synset_count' not in result['scores']
    root = Path(__file__).resolve().parents[1]
    jsonschema.validate({'synonymMatrix': result['synonymMatrix']},
                        json.loads((root / 'schemas/output.schema.json').read_text()))
    evidence = engine.backends['component_matching'].evidence
    nested = engine.backends['component_matching'].engine
    assert nested.compute_scores.call_count == 1
    reference_parts, student_parts = nested.compute_scores.call_args.args
    assert len(reference_parts) == len({(p['label'], p['language']) for p in reference_parts})
    assert len(student_parts) == len({(p['label'], p['language']) for p in student_parts})
    shape = tuple(evidence['shape'])
    matrices = {name: np.asarray(values).reshape(shape) for name, values in evidence['scores'].items()}
    features = {name: matrices[f'wordnet_{name}'] for name in SEMANTIC_FEATURES}
    np.testing.assert_allclose(semantic_fusion(matrices, features, disabled=['conflicts']),
                               evidence['combinedScores'])
    assert len(evidence['alignments'][0][0]) == 2
    assert len(evidence['alignments'][0][1]) == 1
    # Ein gemeinsamer Attributbestandteil kann den Mittelwert weiterhin anheben.
    other = engine.match([element('r', 'Gerätenummer')], [element('s', 'Raumnummer')])
    assert other['combinedScores'][0][0] == pytest.approx(.6)


def test_components_handle_order_duplicates_empty_sets_and_empty_labels(component_engine):
    engine = component_engine
    result = engine.match([element('r', 'Gebäude Nummer')], [element('s', 'Nummer Gebäude')])
    np.testing.assert_allclose(result['combinedScores'], [[1]])
    result = engine.match([element('r', 'Nummer Nummer')], [element('s', 'Nummer')])
    assert result['combinedScores'] == [[.5]]
    assert engine.match([], [element('s', 'Gebäude')])['combinedScores'] == []
    result = engine.match([element('r', '')], [element('s', 'Gebäude')])
    assert result['combinedScores'] == [[0]]
    assert result['synonymMatrix'][0]['matches'] == []

