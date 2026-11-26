"""Prüfe die feste Fusionsregel und ihre Ablationen ohne Modelltraining."""

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.combinations import (
    SEMANTIC_FEATURES, SEMANTIC_METHODS, semantic_fusion,
)
from synonym_matching.config import validate_config


def inputs(shape=(1, 5)):
    matrices = {name: np.full(shape, .4) for name in SEMANTIC_METHODS}
    matrices['translated_embedding'][:] = .8
    matrices['wordnet'][:] = 0
    matrices['label_part_compatibility'][:] = 1
    features = {name: np.zeros(shape) for name in SEMANTIC_FEATURES}
    for name in SEMANTIC_FEATURES[:3]:
        features[name][:] = 1
    return matrices, features


def test_positive_negative_ambiguous_unknown_and_ontology_only_evidence():
    matrices, features = inputs()
    matrices['wordnet'][0, [0, 2]] = 1
    features['antonym'][0, 1] = 1
    features['student_synset_count'][0, 2] = 3
    features['pair_known'][0, 3] = features['student_synset_count'][0, 3] = 0
    features['taxonomy_available'][:] = 1
    features['path_similarity'][:] = features['wup_similarity'][:] = 1
    before = {name: values.copy() for name, values in matrices.items()}
    np.testing.assert_allclose(semantic_fusion(matrices, features), [[1, .35, .7, .7, .7]])
    # Ontologie ohne positive Synonym-Evidenz darf keinen Score anheben.
    assert semantic_fusion(matrices, features, disabled=['ontology'])[0, 4] == pytest.approx(.7)
    assert semantic_fusion(matrices, features, disabled=['ambiguity'])[0, 2] == 1
    assert semantic_fusion(matrices, features, disabled=['synsets'])[0, 0] == pytest.approx(.7)
    assert semantic_fusion(matrices, features, disabled=['relations'])[0, 1] == pytest.approx(.7)
    assert semantic_fusion(matrices, features, disabled=['strings'])[0, 4] == pytest.approx(.8)
    for name in before:
        np.testing.assert_array_equal(matrices[name], before[name])


def test_conflicts_apply_after_lexical_boost_and_disabled_groups_are_validated():
    matrices, features = inputs((1, 1))
    matrices['wordnet'][:] = 1
    matrices['label_part_compatibility'][:] = 0
    assert semantic_fusion(matrices, features)[0, 0] == pytest.approx(.45)
    assert semantic_fusion(matrices, features, disabled=['conflicts'])[0, 0] == pytest.approx(.9)
    for disabled in [True, ['unknown'], ['strings', 'strings'], [[]]]:
        with pytest.raises(ValueError):
            semantic_fusion(matrices, features, disabled=disabled)
        with pytest.raises(ValueError):
            validate_config({'methods': list(SEMANTIC_METHODS),
                             'combiner': {'kind': 'semantic', 'disabled': disabled}})
    matrices['translated_embedding'][:] = np.nan
    with pytest.raises(ValueError, match='finite'):
        semantic_fusion(matrices, features)
    matrices, features = inputs((0, 2))
    assert semantic_fusion(matrices, features).shape == (0, 2)


def test_public_service_uses_same_kernel_and_preserves_output_schema(monkeypatch):
    from synonym_matching.methods import METHODS

    monkeypatch.setitem(METHODS, 'translated_embedding',
                        lambda left, right, backend: np.full((len(left), len(right)), .8))
    engine = MatchingEngine({'methods': list(SEMANTIC_METHODS),
                             'preprocessing': ['normalize'],
                             'combiner': {'kind': 'semantic'}})
    monkeypatch.setattr(engine.translator, 'translate', lambda texts, languages: texts)
    backend = engine.backends['wordnet']
    monkeypatch.setattr(backend, 'lookup', lambda text: set() if text == 'XYZ' else {'sense'})
    monkeypatch.setattr(backend, 'matrix', lambda a, b: np.array([[1., 0., 0.]]))
    _, features = inputs((1, 3))
    features['pair_known'][0, 2] = features['student_synset_count'][0, 2] = 0
    monkeypatch.setattr(backend, 'relation_features', lambda a, b, names: features)
    reference = [{'id': 'r', 'label': 'Nachname', 'language': 'de'}]
    student = [{'id': str(i), 'label': text, 'language': 'de'}
               for i, text in enumerate(['Familienname', 'Vorname', 'XYZ'])]
    raw = engine.compute_scores(reference, student)
    expected = semantic_fusion(raw['scores'], raw['semantic_features']['wordnet'])
    output = engine.match(reference, student)
    np.testing.assert_allclose(output['combinedScores'], expected)
    assert output['scores']['wordnet_student_known'] == [[1, 1, 0]]
    schema = Path(__file__).resolve().parents[1] / 'schemas/output.schema.json'
    jsonschema.validate({'synonymMatrix': output['synonymMatrix']}, json.loads(schema.read_text()))


def test_research_semantic_fusion_preserves_empty_matrix_shape(tmp_path, monkeypatch):
    from research import compare
    from research.experiments import load_config

    config = load_config()
    case = {'id': 'empty', 'case_number': 28, 'title': 'Leere Referenzmenge',
            'reference': [], 'student': [{'id': 's', 'label': 'Kunde', 'language': 'de'}],
            'annotations': []}

    def cached(cases, definitions, methods):
        features = {}
        for chain in definitions['semantic_full']['chains'].values():
            item = {'status': 'ok', 'scores': [], 'shape': [0, 1], 'seconds': 0,
                    'eligible': [], 'processedLabels': {'reference': [], 'student': ['Kunde']}}
            if chain[-1] == 'wordnet':
                item['relation_features'] = {name: [] for name in SEMANTIC_FEATURES}
            features[tuple(chain), 'empty'] = item
        return features, {}, [], {}, None

    monkeypatch.setattr(compare, 'calculate_features', cached)
    output = tmp_path / 'empty.json'
    assert compare.run_experiments({'cases': [case]}, output, config, only=['semantic_full']) == []
    record = json.loads(output.read_text())['records'][0]
    assert record['shape'] == [0, 1]
    assert record['decisions']['threshold']['metrics']['pairs'] == 0

