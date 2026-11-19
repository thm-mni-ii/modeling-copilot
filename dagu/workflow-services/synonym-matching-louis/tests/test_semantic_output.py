"""Bedeutungsmerkmale erweitern scores, nicht die öffentliche Ausgabestruktur."""

import json
import os
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from synonym_matching import MatchingEngine, match
from synonym_matching.combinations import EVIDENCE_FEATURES, evidence_fusion
from synonym_matching.config import validate_config
from synonym_matching.lexicons import semantic_features

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'schemas/output.schema.json').read_text())


def test_group_coverage_distinguishes_unknown_and_does_not_affect_mean(tmp_path):
    lexicon = tmp_path / 'thesaurus.txt'
    lexicon.write_text('Kunde;Abnehmer\nLieferant;Zulieferer\n')
    result = match([{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
                   [{'id': 's1', 'label': 'Lieferant', 'language': 'de'},
                    {'id': 's2', 'label': 'UnbekanntXYZ', 'language': 'de'}],
                   {'methods': ['openthesaurus'], 'lexicons': {'openthesaurus': str(lexicon)},
                    'semantic_features': {'openthesaurus': []}})
    jsonschema.validate(result, SCHEMA)
    known, unknown = result['synonymMatrix'][0]['matches']
    assert known['combinedScore'] == unknown['combinedScore'] == 0
    assert known['scores']['openthesaurus_shared_group'] == 0
    assert known['scores']['openthesaurus_reference_known'] == 1
    assert known['scores']['openthesaurus_student_known'] == 1
    assert unknown['scores']['openthesaurus_student_known'] == 0
    assert unknown['scores']['openthesaurus_pair_known'] == 0
    assert not any('antonym' in name for name in known['scores'])
    assert set(known) == {'submissionElement', 'scores', 'combinedScore'}


def test_service_and_research_rule_use_same_unrounded_features(monkeypatch):
    engine = MatchingEngine({'methods': ['levenshtein', 'wordnet'],
                             'combiner': {'kind': 'evidence', 'baseline': 'levenshtein',
                                          'lexicon': 'wordnet'}})
    backend = engine.backends['wordnet']
    monkeypatch.setattr(engine.translator, 'translate', lambda texts, languages: texts)
    monkeypatch.setattr(backend, 'lookup', lambda text: {'sense'})
    monkeypatch.setattr(backend, 'matrix', lambda a, b: np.array([[1., 0.]]))
    values = {name: np.ones((1, 2)) if name in EVIDENCE_FEATURES[:3] else np.zeros((1, 2))
              for name in EVIDENCE_FEATURES}
    values['antonym'] = np.array([[0., 1.]])
    monkeypatch.setattr(backend, 'relation_features', lambda a, b, names: values)
    ref = [{'id': 'r', 'label': 'abc', 'language': 'en'}]
    student = [{'id': 's1', 'label': 'z', 'language': 'en'},
               {'id': 's2', 'label': 'abcx', 'language': 'en'}]
    raw = engine.compute_scores(ref, student)
    expected = evidence_fusion(raw['scores']['levenshtein'], raw['scores']['wordnet'],
                               raw['semantic_features']['wordnet'])
    output = engine.match(ref, student)
    np.testing.assert_array_equal(output['combinedScores'], expected)
    assert output['combinedScores'] == [[1, 0]]
    assert output['synonymMatrix'][0]['matches'][1]['scores']['wordnet_antonym'] == 1
    assert raw['scores']['wordnet_reference_known'].tolist() == [[1, 1]]


def test_raw_sense_counts_keep_their_scale_and_validate_against_schema(monkeypatch):
    engine = MatchingEngine({'methods': ['wordnet'],
                             'semantic_features': {'wordnet': ['reference_synset_count']}})
    monkeypatch.setattr(engine.translator, 'translate', lambda texts, languages: texts)
    monkeypatch.setattr(engine.backends['wordnet'], 'matrix', lambda a, b: np.zeros((1, 1)))
    monkeypatch.setattr(engine.backends['wordnet'], 'lookup', lambda text: {'one', 'two'})
    monkeypatch.setattr(engine.backends['wordnet'], 'relation_features',
                        lambda a, b, names: {'reference_synset_count': np.array([[2.]])})
    output = engine.match([{'id': 'r', 'label': 'x', 'language': 'en'}],
                          [{'id': 's', 'label': 'y', 'language': 'en'}])
    public = {'synonymMatrix': output['synonymMatrix']}
    jsonschema.validate(public, SCHEMA)
    candidate = public['synonymMatrix'][0]['matches'][0]
    assert candidate['scores']['wordnet_reference_synset_count'] == 2
    assert candidate['combinedScore'] == 0
    candidate['scores']['levenshtein'] = 2
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(public, SCHEMA)  # Nur Zählmerkmale dürfen den alten Wertebereich verlassen.


def test_crosslingual_source_known_is_different_from_link_available():
    backend = {'coverage': {'reference': [{'source_synset_count': 2, 'english_synset_count': 0}],
                           'student': [{'source_synset_count': 1, 'english_synset_count': 1}]}}
    result = semantic_features(backend, ['known'], ['known'], [], np.zeros((1, 1)))
    assert result['pair_known'][0, 0] == 1
    assert result['reference_linked'][0, 0] == 0 and result['student_linked'][0, 0] == 1


@pytest.mark.parametrize('features', [True, {'levenshtein': []}, {'wordnet': ['unknown']},
                                     {'wordnet': [['invalid']]}, {'openthesaurus': ['antonym']}])
def test_invalid_semantic_configuration_is_rejected(features):
    with pytest.raises(ValueError):
        validate_config({'methods': ['wordnet', 'openthesaurus'], 'semantic_features': features})


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='requires local wn data')
def test_real_numeric_features_in_public_matrix():
    requested = ['reference_synset_count', 'student_synset_count', 'antonym',
                 'reference_hypernym', 'reference_hyponym', 'path_similarity', 'wup_similarity']
    result = match([{'id': 'r', 'label': 'last name', 'language': 'en'}],
                   [{'id': 'synonym', 'label': 'family name', 'language': 'en'},
                    {'id': 'related', 'label': 'first name', 'language': 'en'},
                    {'id': 'unknown', 'label': 'UnknownFachtermXYZ', 'language': 'en'}],
                   {'methods': ['levenshtein', 'wordnet'], 'semantic_features': {'wordnet': requested},
                    'combiner': {'kind': 'mean', 'methods': ['levenshtein']}})
    jsonschema.validate(result, SCHEMA)
    matches = {m['submissionElement']['id']: m for m in result['synonymMatrix'][0]['matches']}
    assert matches['synonym']['scores']['wordnet_shared_synset'] == 1
    related = matches['related']['scores']
    assert related['wordnet_pair_known'] == 1 and related['wordnet_shared_synset'] == 0
    assert related['wordnet_wup_similarity'] > .8 and related['wordnet_taxonomy_available'] == 1
    unknown = matches['unknown']['scores']
    assert unknown['wordnet_student_known'] == unknown['wordnet_shared_synset'] == 0
    assert unknown['wordnet_taxonomy_available'] == 0
