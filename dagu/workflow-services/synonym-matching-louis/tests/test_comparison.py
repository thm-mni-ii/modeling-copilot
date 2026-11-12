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


def only(config, *aliases):
    """Nutze nur die genannten Ketten; Mischungen nur, wenn alle ihre Ketten dabei sind."""
    config['chains'] = {a: c for a, c in config['chains'].items() if a in aliases}
    config['mixes'] = [m for m in config['mixes']
                       if set(m.get('weights') or m['parts']) <= set(aliases)]
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


def test_resource_hash_uses_download_manifest_only_when_size_matches(tmp_path, monkeypatch):
    from research import compare

    monkeypatch.setattr(compare, 'ROOT', tmp_path)
    folder = tmp_path / '.cache/word-vectors'
    folder.mkdir(parents=True)
    model = folder / 'model.bin'
    model.write_bytes(b'abc')
    manifest = folder / 'huggingface-download-manifest.json'
    entry = {'path': '.cache/word-vectors/model.bin', 'bytes': 3, 'sha256': 'aus-manifest'}
    manifest.write_text(json.dumps([entry]))
    assert compare.resource_hash(model) == ('aus-manifest', 'manifest')
    manifest.write_text(json.dumps([{**entry, 'bytes': 4}]))
    digest, source = compare.resource_hash(model)
    assert source == 'berechnet' and digest == compare.sha256(model)


def test_run_experiments_stores_load_seconds_separately_from_compute(tmp_path):
    data = {'cases': [{'id': 'test', 'case_number': 1, 'title': 'x',
            'reference': [{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
            'student': [{'id': 's', 'label': 'Kunde', 'language': 'de'}],
            'annotations': [['correct']]}]}
    config = only(load_config(), 'lev')
    config['preprocessing'] = {'raw': []}
    output = tmp_path / 'run.json'
    run_experiments(data, output, config)
    run = json.loads(output.read_text())
    assert all('load_seconds' in f and f['seconds'] >= 0 for f in run['features'])
    assert 'model_load_seconds' in run


def test_research_configurations_use_service_methods_and_combiners():
    config = load_config()
    for spec in configurations(config)[0].values():
        chains = spec['chains'].values()
        # Wortvektoren, 'translate' und Ketten-Mischungen sind reine Forschungsschreibweisen.
        if (any('files' in config['methods'][chain[-1]] or 'translate' in chain for chain in chains)
                or set(spec['combiner'].get('weights', spec['methods'])) - set(spec['methods'])):
            continue
        service_config = {key: spec[key] for key in ('methods', 'preprocessing',
                                                     'embedding_preprocessing', 'combiner')}
        validated = validate_config(service_config)
        assert validated['methods'] == spec['methods']
        assert validated['combiner']['kind'] == spec['combiner']['kind']


def test_duplicate_pipelines_are_skipped_but_real_ablations_stay():
    config = load_config()
    config['preprocessing'] = {'a': ['normalize'], 'b': ['normalize'], 'c': ['normalize', 'lowercase']}
    config['chains'] = {'lev': ['$pre', 'levenshtein'], 'jw': ['$pre', 'jaro_winkler'],
                        'lev_plain': ['normalize', 'levenshtein']}
    config['mixes'] = [{'name': 'x', 'weights': {'lev': 1, 'jw': 1}},
                       {'name': 'y', 'weights': {'lev': 2, 'jw': 2}}]
    definitions, skipped = configurations(config)
    assert {'a/x', 'c/x', 'normalize → levenshtein',
            'normalize+lowercase → levenshtein'} <= set(definitions)
    assert 'a/y' not in definitions and 'b/x' not in definitions
    # 'b' wiederholt 'a'; 'lev_plain' wiederholt 'normalize → levenshtein' aus dem Platzhalter.
    assert {s['name'] for s in skipped} >= {'b/x', 'a/y', 'normalize → levenshtein'}


def test_chains_and_mixes_are_validated_and_named_automatically():
    config = load_config()
    config['preprocessing'] = {'raw': []}
    config['chains'] = {'lev': ['normalize', 'levenshtein'],
                        'multi': ['normalize', 'multilingual'],
                        'lev_en': ['normalize', 'stem', 'translate', 'levenshtein']}
    config['mixes'] = [{'weights': {'lev': 1, 'multi': 3}}]
    definitions, _ = configurations(config)
    assert 'normalize+stem+translate → levenshtein' in definitions
    mix = definitions['25% normalize → levenshtein + 75% normalize → multilingual']
    assert mix['combiner']['weights'] == {'normalize → levenshtein': 1, 'normalize → multilingual': 3}
    for bad in (['normalize', 'nope', 'levenshtein'], ['translate', 'translate', 'levenshtein'],
                ['normalize', 'unknown_method'], ['$pre', '$pre', 'levenshtein']):
        config['chains'] = {'bad': bad}
        config['mixes'] = []
        with pytest.raises(ValueError):
            configurations(config)


def test_mix_with_unknown_chain_or_missing_variant_part_is_an_error():
    config = load_config()
    config['mixes'] = [{'name': 'bad', 'weights': {'nope': 1}}]
    with pytest.raises(ValueError):
        configurations(config)
    config = load_config()
    config['mixes'] = [{'name': 'bad', 'variant': 'weighted_fusion', 'parts': ['lev', 'jw']}]
    with pytest.raises(ValueError):
        configurations(config)


def test_compounds_uses_lexicon_and_keeps_other_languages(monkeypatch):
    monkeypatch.setattr('synonym_matching.preprocessing._compound_words',
                        lambda: {'kunde', 'daten', 'rechnung', 'adresse'})
    assert split_compounds('Kundendaten Rechnungsadresse', 'de') == 'kunde daten rechnung adresse'
    assert split_compounds('unbekannt', 'de') == 'unbekannt'
    assert split_compounds('Kundendaten', 'en') == 'Kundendaten'


def test_preprocessing_limits_apply_to_varying_parts_of_mixes():
    config = load_config()
    config['preprocessing'] = {'plain': ['normalize'], 'lower': ['normalize', 'lowercase'],
                               'stem': ['normalize', 'stem']}
    config['methods']['levenshtein']['preprocessing_steps'] = ['normalize', 'lowercase']
    config['chains'] = {'lev': ['$pre', 'levenshtein'], 'multi': ['normalize', 'multilingual']}
    config['mixes'] = [{'name': 'hybrid', 'weights': {'lev': 1, 'multi': 1}}]
    specs, _ = configurations(config)
    assert {'plain/hybrid', 'lower/hybrid'} <= specs.keys()
    assert 'stem/hybrid' not in specs
    assert not any('stem' in chain for spec in specs.values() for chain in spec['chains'].values())
    assert specs['lower/hybrid']['chains']['normalize → multilingual'] == ['normalize', 'multilingual']


def test_default_experiments_keep_preprocessing_method_specific():
    config = load_config()
    specs, _ = configurations(config)
    for spec in specs.values():
        for chain in spec['chains'].values():
            if chain[-1] in {'multilingual', 'translated_embedding'} or 'files' in config['methods'][chain[-1]]:
                assert not {'stem', 'remove_stopwords'} & set(chain)
    assert all(not method['lowercase'] for method in config['methods'].values() if 'files' in method)
    assert 'normalize+lemmatize → odenet' in specs
    assert 'normalize+translate+lemmatize → wordnet' in specs
    assert 'odenet_multi_25_75' in specs and 'odenet_multi_75_25' in specs
    assert config['chains']['ft_en_lemma'] == ['normalize', 'translate', 'lemmatize', 'fasttext_en_matching']
    assert config['chains']['ft_en_identifiers'] == ['normalize', 'split_identifiers', 'translate', 'fasttext_en_matching']


def test_run_stores_raw_features_once_and_api_unchanged(tmp_path):
    data = {'cases': [{'id': 'test', 'case_number': 23, 'title': 'candidates',
            'reference': [{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
            'student': [{'id': 's1', 'label': 'kunde', 'language': 'de'},
                        {'id': 's2', 'label': 'Lieferant', 'language': 'de'}],
            'annotations': [['correct', 'incorrect']]}]}
    output = tmp_path / 'run.json'
    config = only(load_config(), 'lev', 'jw', 'trigram', 'exact')
    config['preprocessing'] = {'raw': [], 'lower': ['lowercase']}
    assert run_experiments(data, output, config) == []
    run = json.loads(output.read_text())
    keys = [(f['method'], tuple(f['preprocessing']), f['case']) for f in run['features']]
    assert len(keys) == len(set(keys))
    assert sum(d['methods'] == ['exact_match'] for d in run['definitions'].values()) == 1
    assert set(run['records'][0]['decisions']) == {'threshold', 'mutual_best', 'hungarian'}
    assert run['dataset'] == data
    assert 'threshold' in run['rankings']
    assert {p.name for p in tmp_path.iterdir()} == {'run.json'}
    with pytest.raises(FileExistsError):
        run_experiments(data, output, config)
