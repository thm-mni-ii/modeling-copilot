"""Prüfe die konservative Regel, nicht eine behauptete semantische Qualität."""

import json

import numpy as np
import pytest

from research import compare
from research.experiments import configurations, load_config
from synonym_matching.combinations import EVIDENCE_FEATURES, evidence_fusion


def test_only_single_sense_nonconflicting_evidence_changes_scores():
    baseline = np.array([[.2, .9, .8, .7, .6, .8, .3, .9]])
    synonyms = np.array([[1, 0, 0, 1, 1, 0, 0, 0]])
    features = {
        'pair_known': [[1, 1, 0, 1, 1, 1, 1, 1]],
        'reference_synset_count': [[1, 1, 1, 2, 1, 3, 1, 1]],
        'student_synset_count': [[1, 1, 0, 1, 1, 1, 1, 1]],
        'reference_hypernym': [[0, 0, 0, 0, 1, 0, 0, 0]],
        'reference_hyponym': [[0, 0, 0, 0, 0, 0, 0, 1]],
        'antonym': [[0, 1, 0, 0, 0, 1, 0, 0]],
        'wup_similarity': np.full((1, 8), .99),  # Hohe Nähe ist keine Synonymbestätigung.
    }
    scores = evidence_fusion(baseline, synonyms, features)
    np.testing.assert_allclose(scores, [[1, 0, .8, .7, .6, .8, .3, 0]])
    np.testing.assert_allclose(baseline, [[.2, .9, .8, .7, .6, .8, .3, .9]])


def test_evidence_shapes_missing_features_and_empty_matrices():
    empty = np.empty((0, 2))
    assert evidence_fusion(empty, empty, dict.fromkeys(EVIDENCE_FEATURES, empty)).shape == (0, 2)
    with pytest.raises(ValueError):
        evidence_fusion(np.zeros((1, 1)), np.zeros((1, 1)), {})
    features = dict.fromkeys(EVIDENCE_FEATURES, np.ones((1, 1)))
    with pytest.raises(ValueError):
        evidence_fusion(np.zeros((1, 2)), np.zeros((1, 1)), features)
    with pytest.raises(ValueError):
        evidence_fusion(np.array([[np.nan]]), np.ones((1, 1)), features)


def test_same_evidence_mix_with_other_aliases_is_not_repeated():
    config = load_config()
    config['chains']['embedding_alias'] = config['chains']['trans_emb']
    config['chains']['lexicon_alias'] = config['chains']['wordnet']
    config['mixes'].append({'name': 'duplicate_evidence', 'evidence': True,
                            'parts': ['embedding_alias', 'lexicon_alias']})
    definitions, skipped = configurations(config)
    assert 'duplicate_evidence' not in definitions
    assert any(item['name'] == 'duplicate_evidence' for item in skipped)


def test_selected_experiment_uses_features_and_records_changes(tmp_path, monkeypatch):
    config = load_config()
    config['chains'] = {'base': ['normalize', 'translated_embedding'], 'lex': ['normalize', 'wordnet']}
    config['mixes'] = [{'name': 'fused', 'evidence': True, 'parts': ['base', 'lex']}]
    case = {'id': 'test', 'case_number': 1, 'title': 'Regeltest',
            'reference': [{'id': 'r', 'label': 'Referenz', 'language': 'de'}],
            'student': [{'id': f's{i}', 'label': f'Kandidat {i}', 'language': 'de'} for i in range(3)],
            'annotations': [['correct', 'incorrect', 'incorrect']]}

    def cached_features(cases, definitions, methods):
        assert list(definitions) == ['fused']
        result = {}
        for alias, scores in [('base', [[.2, .9, .3]]), ('lex', [[1, 0, 0]])]:
            item = {'status': 'ok', 'scores': scores, 'shape': [1, 3], 'seconds': 0,
                    'load_seconds': 0, 'eligible': [[True, True, True]],
                    'processedLabels': {'reference': ['Referenz'],
                                        'student': ['Kandidat 0', 'Kandidat 1', 'Kandidat 2']}}
            if alias == 'lex':
                item['relation_features'] = {
                    name: [[1, 1, 0]] if name in EVIDENCE_FEATURES[:3]
                    else [[0, 1, 0]] if name == 'antonym' else [[0, 0, 0]]
                    for name in EVIDENCE_FEATURES}
            result[tuple(config['chains'][alias]), 'test'] = item
        return result, {}, [], {}, None

    monkeypatch.setattr(compare, 'calculate_features', cached_features)
    output = tmp_path / 'evidence.json'
    assert compare.run_experiments({'cases': [case]}, output, config, only=['fused']) == []
    payload = json.loads(output.read_text())
    assert payload['selected_experiments'] == ['fused']
    assert len(payload['records']) == 1
    record = payload['records'][0]
    assert record['combinedScores'] == [[1, 0, .3]]
    assert [change['reason'] for change in record['evidence_changes']] == [
        'single_sense_synonym', 'single_sense_counterrelation']
    assert record['decisions']['threshold']['metrics']['fp'] == 0
    with pytest.raises(ValueError, match='experiment selection'):
        compare.run_experiments({'cases': [case]}, tmp_path / 'bad.json', config, only=['unknown'])
    config['methods']['wordnet']['relation_features'] = []
    with pytest.raises(ValueError, match='all evidence features'):
        configurations(config)
