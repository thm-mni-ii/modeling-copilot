"""Komponentenpaarung, fehlende Bestandteile und unveränderte öffentliche Struktur."""

import json
from pathlib import Path
from unittest.mock import Mock

import jsonschema
import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.combinations import SEMANTIC_FEATURES, SEMANTIC_METHODS, semantic_fusion
from synonym_matching.components import label_components, merge_component_features


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


def test_targeted_splitting_keeps_phrases_and_non_target_compounds(component_engine):
    assert label_components('Kunde registrieren', 'de', targeted=True) == ['Kunde registrieren']
    assert label_components('Vorname', 'de', targeted=True) == ['Vorname']
    assert label_components('Order Item', 'en', targeted=True) == ['Order Item']
    assert label_components('GebäudeNr.', 'de', targeted=True) == ['Gebäude', 'Nummer']
    assert label_components('Geräteraum', 'de', targeted=True) == ['geräte', 'raum']
    assert label_components('buildingNumber', 'en', targeted=True) == ['building', 'Number']
    assert label_components('XYZnummer', 'de', targeted=True) == ['XYZ', 'nummer']
    assert label_components('Laboratory room', 'en', targeted=True) == ['Laboratory', 'room']


def test_merge_scores_separately_but_not_synsets_or_relations():
    values = np.array([[.2, 0], [0, 1.]])
    matrices = {name: values.copy() for name in SEMANTIC_METHODS}
    matrices['translated_embedding'][0, 0] = .35
    matrices['wordnet'] = np.array([[0., 0], [0, 1.]])
    features = {name: np.zeros((2, 2)) for name in SEMANTIC_FEATURES}
    for name in SEMANTIC_FEATURES[:3]:
        features[name][:] = 1
    features['reference_hypernym'][0, 0] = 1
    features['antonym'][1, 1] = 1  # Relationsmerkmal nur im Zusatz, nicht im Objekt.
    features['taxonomy_available'][0, 0] = 1
    features['path_similarity'][0, 0] = .3
    features['wup_similarity'][0, 0] = .8
    raw = {'scores': matrices, 'semantic_features': {'wordnet': features}}
    indices = np.array([0, 1])
    head = np.array([True, False])
    scores, merged = merge_component_features(raw, [0, 1], [0, 1], indices, indices, head)
    assert scores['levenshtein'] == pytest.approx(.6)
    assert scores['translated_embedding'] == pytest.approx(.675)
    assert scores['wordnet'] == 0  # Gemeinsames Nummer reicht nicht.
    assert merged['reference_hypernym'] == 1
    assert merged['antonym'] == 0
    assert merged['path_similarity'] == .3  # Objektwert, kein Mittel mit dem Zusatz.
    assert merged['wup_similarity'] == .8
    features['student_synset_count'][0, :] = 0
    _, merged = merge_component_features(raw, [0, 1], [0, 1], indices, indices, head)
    assert merged['student_known'] == merged['pair_known'] == 0
    features['student_synset_count'][0, :] = 1
    matrices['wordnet'][1, 1] = 0
    _, merged = merge_component_features(raw, [0, 1], [0, 1], indices, indices, head)
    assert merged['reference_hypernym'] == merged['taxonomy_available'] == 0


def test_feature_first_service_fuses_once_after_aggregation(component_engine, monkeypatch):
    engine = MatchingEngine({'methods': ['component_feature_fusion']})
    backend = engine.backends['component_feature_fusion']
    compute = component_engine.backends['component_matching'].engine.compute_scores
    monkeypatch.setattr(backend.engine, 'compute_scores', compute)
    result = engine.match([element('r', 'Gerätenummer')], [element('s', 'Raumnummer')])
    assert result['scores']['component_feature_fusion_levenshtein'][0][0] == pytest.approx(.6)
    assert result['scores']['component_feature_fusion_translated_embedding'][0][0] == pytest.approx(.6)
    assert result['scores']['component_feature_fusion_wordnet_shared_synset'] == [[0]]
    assert result['combinedScores'][0][0] == pytest.approx(.3)  # Bestehende volle Fusion.
    evidence = backend.evidence
    assert 'combinedScores' not in evidence  # Kein vorzeitig fusionierter Komponentenscore.
    assert 'alignmentScores' in evidence
    np.testing.assert_allclose(semantic_fusion(
        {k: np.asarray(v) for k, v in evidence['whole_label_scores'].items()},
        {k: np.asarray(v) for k, v in evidence['whole_label_semantic_features'].items()}),
        result['combinedScores'])
    root = Path(__file__).resolve().parents[1]
    jsonschema.validate({'synonymMatrix': result['synonymMatrix']},
                        json.loads((root / 'schemas/output.schema.json').read_text()))
    unspecified = engine.match([element('r', 'Gerätenummer')], [element('s', 'Nummer')])
    # Der Zusatz darf nicht statt des eigentlichen Objekts als bester Partner dienen.
    assert unspecified['combinedScores'][0][0] == pytest.approx(.1)
    assert engine.match([], [element('s', 'Gebäude')])['combinedScores'] == []

