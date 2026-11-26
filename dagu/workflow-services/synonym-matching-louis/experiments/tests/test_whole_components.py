"""Gespeicherte Zweige fair mischen und an denselben Kandidaten auswerten."""

import json

import numpy as np
import pytest

from research.compare_whole_components import run_comparison
from research.experiments import load_config


def saved_inputs(tmp_path):
    case = {'id': 'c', 'case_number': 1, 'title': 'Konkurrenz',
            'reference': [{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
            'student': [{'id': 's1', 'label': 'Abnehmer', 'language': 'de'},
                        {'id': 's2', 'label': 'Lieferant', 'language': 'de'}],
            'annotations': [['correct', 'incorrect']], 'changed_student_ids': ['s1', 's2']}
    common = {'seed': 42, 'threshold': .5, 'dataset': {'cases': [case]},
              'provenance': {'models': {'translated_embedding': {'revision': 'fixed'},
                                       'translation': 'fixed'}}}
    whole = {**common, 'features': [
        {'case': 'c', 'chain': ['normalize', name], 'status': 'ok',
         'scores': [[.8, .2]], 'eligible': [[True, True]]}
        for name in ('levenshtein', 'jaro_winkler', 'char_trigram', 'translated_embedding')]}
    component = {**common, 'features': [{
        'case': 'c', 'chain': ['normalize', 'component_evidence'], 'status': 'ok',
        'eligible': [[True, True]], 'component_features': {
            'string_similarity': [[.2, .8]], 'embedding_similarity': [[.2, .8]]}}]}
    paths = [tmp_path / 'whole.json', tmp_path / 'components.json']
    for path, payload in zip(paths, [whole, component]):
        path.write_text(json.dumps(payload))
    return paths


def test_endpoints_mixture_and_changed_label_evaluation(tmp_path):
    paths = saved_inputs(tmp_path)
    output = tmp_path / 'result.json'
    result = run_comparison(*paths, output, load_config())
    records = {r['experiment']: r for r in result['records']}
    np.testing.assert_allclose(records['whole_1_components_0']['combinedScores'], [[.8, .2]])
    np.testing.assert_allclose(records['whole_0_components_1']['combinedScores'], [[.2, .8]])
    np.testing.assert_allclose(records['whole_0.75_components_0.25']['combinedScores'], [[.65, .35]])
    assert records['whole_1_components_0']['decisions']['threshold']['metrics']['tp'] == 1
    assert records['whole_0_components_1']['decisions']['threshold']['metrics']['fp'] == 1
    assert 'changed_labels' in result['rankings']
    assert json.loads(output.read_text())['sources']['whole']['sha256']
    with pytest.raises(FileExistsError):
        run_comparison(*paths, output, load_config())


@pytest.mark.parametrize('change', ['dataset', 'seed', 'model'])
def test_incompatible_sources_are_rejected(tmp_path, change):
    paths = saved_inputs(tmp_path)
    payload = json.loads(paths[1].read_text())
    if change == 'dataset':
        payload['dataset']['cases'][0]['student'].reverse()
    elif change == 'seed':
        payload['seed'] = 7
    else:
        payload['provenance']['models']['translation'] = 'other'
    paths[1].write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        run_comparison(*paths, tmp_path / 'result.json', load_config())


def test_same_candidate_mask_and_no_silent_case_loss(tmp_path):
    paths = saved_inputs(tmp_path)
    payload = json.loads(paths[1].read_text())
    payload['features'][0]['eligible'] = [[True, False]]
    paths[1].write_text(json.dumps(payload))
    result = run_comparison(*paths, tmp_path / 'masked.json', load_config())
    assert all(r['decisions']['threshold']['metrics']['fp'] == 0 for r in result['records'])
    payload['features'][0]['status'] = 'unsupported'
    paths[1].write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='no common'):
        run_comparison(*paths, tmp_path / 'unsupported.json', load_config())
