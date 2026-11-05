import json

import numpy as np
import pytest

from research.evaluation import select_matches
from research.compare import configurations, load_config, run_experiments
from synonym_matching.combinations import combine
from synonym_matching.config import validate_config
from synonym_matching.preprocessing import split_compounds


def test_assignment_optional_unmatched_and_rectangular():
    scores = np.array([[.9, .8], [.85, .1], [.1, .2]])
    valid = np.ones_like(scores, dtype=bool)
    selected = select_matches(scores, valid, .5, 'hungarian')
    assert selected.tolist() == [[False, True], [True, False], [False, False]]
    assert np.all(selected.sum(axis=0) <= 1)
    assert np.all(selected.sum(axis=1) <= 1)
    assert not select_matches(scores, valid, .99, 'hungarian').any()
    assert select_matches(np.zeros((0, 3)), np.zeros((0, 3)), .5, 'hungarian').shape == (0, 3)


def test_threshold_applied_before_optimization():
    # Choosing the full assignment first would consume column 0 with a rejected edge.
    scores = np.array([[.9, .6], [.59, 0]])
    chosen = select_matches(scores, np.ones((2, 2), dtype=bool), .6, 'hungarian')
    assert chosen.tolist() == [[True, False], [False, False]]


def test_mutual_best_ties_and_invalid_cells():
    scores = np.array([[.8, .8], [.8, .1]])
    valid = np.array([[True, True], [False, True]])
    assert select_matches(scores, valid, .5, 'mutual_best').tolist() == [[True, True], [False, False]]
    assert select_matches(np.ones((2, 2)), np.ones((2, 2)), .5, 'mutual_best').all()


def only(config, *names):
    """Aktiviere nur die genannten Verfahren; Kombinationen ohne sie werden übersprungen."""
    for name, method in config['methods'].items():
        method['enabled'] = name in names
    return config


def test_configurations_has_no_aliases_and_three_unique_weights():
    config = load_config()
    config['preprocessing'] = {'lowercase': ['normalize', 'lowercase']}
    specs = list(configurations(config)[0].values())
    names = [s['name'] for s in specs]
    assert len(names) == len(set(names))
    assert not set(names) & {'translation_string', 'translation_monolingual',
                             'multilingual_only', 'string_multilingual', 'weighted_fusion'}
    weighted = [s for s in specs if s['combiner'].get('name') == 'weighted_fusion'
                and not s.get('global_ranking')]
    weights = [s['combiner']['options']['embedding_weight'] for s in weighted]
    assert sorted(weights) == [.25, .5, .75]
    raw = {n: np.full((1, 1), .2) for n in ('levenshtein', 'jaro_winkler', 'char_trigram')}
    raw['multilingual'] = np.full((1, 1), .8)
    values = [float(combine(raw, s['combiner'])[0, 0]) for s in weighted]
    assert sorted(values) == pytest.approx([.35, .5, .65])


def test_research_configurations_use_service_methods_and_combiners():
    config = load_config()
    for spec in configurations(config)[0].values():
        if any('files' in config['methods'][name] for name in spec['methods']):
            continue
        service_config = {key: spec[key] for key in ('methods', 'preprocessing',
                                                     'embedding_preprocessing', 'combiner')}
        validated = validate_config(service_config)
        assert validated['methods'] == spec['methods']
        assert validated['combiner']['kind'] == spec['combiner']['kind']


def test_duplicate_pipelines_are_skipped_but_real_ablations_stay():
    config = only(load_config(), 'levenshtein', 'jaro_winkler')
    config['preprocessing'] = {'a': ['normalize'], 'b': ['normalize'], 'c': ['normalize', 'lowercase']}
    config['combinations'] = [
        {'name': 'x', 'weights': {'levenshtein': 1, 'jaro_winkler': 1}},
        {'name': 'y', 'weights': {'levenshtein': 2, 'jaro_winkler': 2}}]
    definitions, skipped = configurations(config)
    assert {n.split('/')[0] for n in definitions} == {'a', 'c'}
    assert 'a/x' in definitions and 'c/x' in definitions and 'a/y' not in definitions
    assert {s['name'] for s in skipped} >= {'b/levenshtein', 'b/x', 'a/y'}


def test_unknown_method_in_combination_is_an_error():
    config = load_config()
    config['combinations'] = [{'name': 'bad', 'weights': {'nope': 1}}]
    with pytest.raises(ValueError):
        configurations(config)


def test_compounds_uses_lexicon_and_keeps_other_languages(monkeypatch):
    monkeypatch.setattr('synonym_matching.preprocessing._compound_words',
                        lambda: {'kunde', 'daten', 'rechnung', 'adresse'})
    assert split_compounds('Kundendaten Rechnungsadresse', 'de') == 'kunde daten rechnung adresse'
    assert split_compounds('unbekannt', 'de') == 'unbekannt'
    assert split_compounds('Kundendaten', 'en') == 'Kundendaten'


def test_run_stores_raw_features_once_and_api_unchanged(tmp_path):
    data = {'cases': [{'id': 'test', 'case_number': 23, 'title': 'candidates',
            'reference': [{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
            'student': [{'id': 's1', 'label': 'kunde', 'language': 'de'},
                        {'id': 's2', 'label': 'Lieferant', 'language': 'de'}],
            'annotations': [['correct', 'incorrect']]}]}
    output = tmp_path / 'run.json'
    config = only(load_config(), 'levenshtein', 'jaro_winkler', 'char_trigram', 'exact_match')
    config['preprocessing'] = {'raw': [], 'lower': ['lowercase']}
    assert run_experiments(data, output, config) == []
    run = json.loads(output.read_text())
    keys = [(f['method'], tuple(f['preprocessing']), f['case']) for f in run['features']]
    assert len(keys) == len(set(keys))
    assert sum(d['name'] == 'exact_match' for d in run['definitions'].values()) == 1
    assert set(run['records'][0]['decisions']) == {'threshold', 'mutual_best', 'hungarian'}
    assert run['dataset'] == data
    assert 'threshold' in run['rankings']
    assert {p.name for p in tmp_path.iterdir()} == {'run.json'}
    with pytest.raises(FileExistsError):
        run_experiments(data, output, config)
