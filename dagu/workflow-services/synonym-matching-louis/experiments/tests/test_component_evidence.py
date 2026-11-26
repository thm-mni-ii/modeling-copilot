"""Rollenfreie Merkmalsaggregation und gewichtete Basis mit Evidenzregeln."""

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.component_evidence import general_components
from synonym_matching.combinations import (SEMANTIC_METHODS, SEMANTIC_FEATURES,
                                           component_evidence_fusion)
from synonym_matching.config import validate_config


def evidence():
    return {name: np.array([[value]]) for name, value in {
        'string_similarity': .6, 'embedding_similarity': .675,
        'lexicon_coverage': 1., 'shared_synset_fraction': .5,
        'full_synonym_evidence': 0., 'antonym_evidence': 0., 'hierarchy_evidence': 0.,
    }.items()}


def test_thought_experiment_unknown_evidence_and_strong_rules():
    f = evidence()
    assert component_evidence_fusion(f, rules=False, string_weight=.5)[0, 0] == pytest.approx(.59625)
    assert component_evidence_fusion(f, rules=False)[0, 0] == pytest.approx(.609375)
    f['lexicon_coverage'][:] = f['shared_synset_fraction'][:] = 0
    assert component_evidence_fusion(f)[0, 0] == pytest.approx(.65625)
    f['string_similarity'][:] = f['embedding_similarity'][:] = .9
    f['lexicon_coverage'][:] = 1
    f['antonym_evidence'][:] = 1
    assert component_evidence_fusion(f, rules=False)[0, 0] > .5
    assert component_evidence_fusion(f)[0, 0] == 0
    f['antonym_evidence'][:] = 0
    f['hierarchy_evidence'][:] = 1
    assert component_evidence_fusion(f)[0, 0] == 0
    f['hierarchy_evidence'][:] = 0
    f['full_synonym_evidence'][:] = f['shared_synset_fraction'][:] = 1
    assert component_evidence_fusion(f)[0, 0] >= .9


def test_synonym_and_counterrelation_rules_can_be_disabled_independently():
    f = evidence()
    f['string_similarity'][:] = f['embedding_similarity'][:] = .1
    f['shared_synset_fraction'][:] = f['full_synonym_evidence'][:] = 1
    assert component_evidence_fusion(f, synonym_rule=True, relation_rules=False)[0, 0] >= .9
    assert component_evidence_fusion(f, synonym_rule=False)[0, 0] < .9
    f['string_similarity'][:] = f['embedding_similarity'][:] = .9
    f['shared_synset_fraction'][:] = f['full_synonym_evidence'][:] = 0
    f['antonym_evidence'][:] = 1
    assert component_evidence_fusion(f, synonym_rule=False, relation_rules=True)[0, 0] == 0
    assert component_evidence_fusion(f, synonym_rule=True, relation_rules=False)[0, 0] > .5
    assert component_evidence_fusion(f, rules=False)[0, 0] > .5


def test_grid_is_unique_and_reuses_saved_features_without_models(tmp_path):
    from research.experiments import configurations, load_config
    from research.sweep_component_weights import run_sweep

    config = load_config()
    definitions, _ = configurations(config)
    options = [s['combiner']['options'] for s in definitions.values()
               if s['combiner']['kind'] == 'component_evidence']
    canonical = {(p['string_weight'], p['lexicon_weight'], p['rules'] and p['synonym_rule'],
                  p['rules'] and p['relation_rules']) for p in options}
    assert len(options) == len(canonical) == 64
    source = tmp_path / 'features.json'
    source.write_text(json.dumps({'threshold': .5, 'seed': 42, 'definitions': {}, 'records': [],
        'features': [{'chain': ['normalize', 'component_evidence'], 'case': 'x', 'status': 'ok',
                      'seconds': 1, 'eligible': [[True]],
                      'component_features': {k: v.tolist() for k, v in evidence().items()}}],
        'dataset': {'cases': [{'id': 'x', 'case_number': 1, 'title': 'Test',
                              'reference': [{'id': 'r', 'label': 'a'}],
                              'student': [{'id': 's', 'label': 'b'}],
                              'annotations': [['incorrect']]}]}}))
    output = tmp_path / 'sweep.json'
    result = run_sweep(source, output, config)
    assert len(result['records']) == 64
    assert all(r['feature_seconds'] == 0 for r in result['records'])
    with pytest.raises(FileExistsError):
        run_sweep(source, output, config)


@pytest.mark.parametrize('options', [{'string_weight': -1}, {'lexicon_weight': float('nan')},
                                    {'rules': 1}, {'unknown': .2}])
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValueError):
        validate_config({'methods': ['component_evidence'],
                         'combiner': {'kind': 'component_evidence', 'options': options}})


def test_general_splitting_does_not_use_roles_or_number_room_only_rules(monkeypatch):
    words = {'kunde', 'daten', 'gerät', 'raum', 'gebäude', 'nummer', 'vorname'}
    monkeypatch.setattr('synonym_matching.component_evidence._compound_words', lambda: words)
    monkeypatch.setattr('synonym_matching.preprocessing._compound_words', lambda: words)
    assert general_components('Kundendaten', 'de') == ['kunde', 'daten']
    assert general_components('Geräteraum', 'de') == ['geräte', 'raum']
    assert general_components('GebäudeNr.', 'de') == ['Gebäude', 'Nummer']
    assert general_components('customerName', 'en') == ['customer', 'Name']
    assert general_components('Vorname', 'de') == ['Vorname']
    assert general_components('Kunde registrieren', 'de') == ['Kunde', 'registrieren']


@pytest.mark.parametrize('text,language,expected', [
    ('Room number', 'en', ['Room', 'number']),
    ('Etagen-Nummer', 'de', ['Etagen', 'Nummer']),
    ('room_number', 'en', ['room', 'number']),
    ('roomNumber', 'en', ['room', 'Number']),
    ('RaumNr.', 'de', ['Raum', 'Nummer']),
    ('Room\nnumber', 'en', ['Room', 'number']),
    ('E-Mail', 'de', ['E-Mail']),
    ('E-Mail Adresse', 'de', ['E-Mail', 'Adresse']),
    ('3.14', 'en', ['3.14']),
    ('42-7', 'en', ['42-7']),
    ('v1.2', 'en', ['v1.2']),
    ('', 'de', []),
])
def test_visible_boundaries_preserve_fixed_terms_and_numbers(text, language, expected):
    assert general_components(text, language) == expected


def test_partial_synsets_remain_separate_from_whole_synonymy(monkeypatch):
    words = {'gerät', 'raum', 'nummer'}
    monkeypatch.setattr('synonym_matching.component_evidence._compound_words', lambda: words)
    monkeypatch.setattr('synonym_matching.preprocessing._compound_words', lambda: words)
    config = {'methods': ['component_evidence'],
              'combiner': {'kind': 'component_evidence', 'options': {'rules': True}}}
    engine = MatchingEngine(config)

    def compute(reference, student):
        shape = (len(reference), len(student))
        strings = np.zeros(shape)
        embedding = np.zeros(shape)
        shared = np.zeros(shape)
        for i, a in enumerate(reference):
            for j, b in enumerate(student):
                same = a['label'].lower() == b['label'].lower()
                strings[i, j], embedding[i, j], shared[i, j] = (1, 1, 1) if same else (.2, .35, 0)
        scores = {name: strings.copy() for name in SEMANTIC_METHODS}
        scores['translated_embedding'], scores['wordnet'] = embedding, shared
        features = {name: np.zeros(shape) for name in SEMANTIC_FEATURES}
        for name in SEMANTIC_FEATURES[:3]:
            features[name][:] = 1
        return {'scores': scores, 'semantic_features': {'wordnet': features}}

    backend = engine.backends['component_evidence']
    assert 'label_part_compatibility' not in backend.engine.methods
    monkeypatch.setattr(backend.engine, 'compute_scores', compute)
    def element(identifier, text):
        return {'id': identifier, 'label': text, 'language': 'de'}
    result = engine.match([element('r', 'Gerätenummer')], [element('s', 'Raumnummer')])
    assert result['scores']['component_evidence_string_similarity'] == [[.6]]
    assert result['scores']['component_evidence_embedding_similarity'] == [[.675]]
    assert result['scores']['component_evidence_shared_synset_fraction'] == [[.5]]
    assert result['scores']['component_evidence_shared_synset'] == [[0]]
    assert result['combinedScores'][0][0] == pytest.approx(.609375)
    assert backend.evidence['policy']['roles'] is False
    schema = Path(__file__).resolve().parents[1] / 'schemas/output.schema.json'
    jsonschema.validate({'synonymMatrix': result['synonymMatrix']}, json.loads(schema.read_text()))
    assert engine.match([], [element('s', 'Nummer')])['combinedScores'] == []
