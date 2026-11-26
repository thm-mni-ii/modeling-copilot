"""Neue Regeln bleiben optionale, getrennte Ablationen."""

from types import SimpleNamespace

import numpy as np
import pytest

from research.compare_lingua import linked_cross_language
from research.decision_tree import decide, production_modules
from research.compare_embeddings import tree_scores


def features(**changes):
    return {'pair_known': 1, 'reference_synset_count': 2, 'student_synset_count': 2,
            'shared_synset': 0, 'antonym': 0, 'reference_hypernym': 0,
            'reference_hyponym': 0, **changes}


def test_exact_priority_changes_only_explicit_exact_pairs():
    values = features(antonym=1)
    text = {'status': 'supported', 'tier': 'canonical'}
    assert decide(values, text)[0] == 'open'
    assert decide(values, text, exact_first=True, exact_equal=True) == ('confirmed', 'normalized_exact')
    assert decide(values, text, exact_first=True, exact_equal=False)[0] == 'open'
    assert decide(values, text, exact_first=True, exact_equal=True, valid=False)[0] == 'not_evaluable'


def test_linked_features_only_replace_cross_source_pairs():
    labels = {'reference': [{'label': 'Raum'}], 'student': [{'label': 'Room'}, {'label': 'Zimmer'}]}
    routes = {'reference': [{'allowed_lexicons': ['de']}],
              'student': [{'allowed_lexicons': ['en']}, {'allowed_lexicons': ['de']}]}
    base = {'pair_known': [[0, 1]], 'shared_synset': [[0, 1]]}
    lexicons = SimpleNamespace(matrices=lambda *a, **kw: (
        np.array([[1., 0.]]), {'pair_known': np.array([[1., 0.]])}, None))
    result, mask = linked_cross_language(lexicons, labels, routes, base)
    assert result == {'pair_known': [[1, 1]], 'shared_synset': [[1, 1]]}
    assert mask.tolist() == [[True, False]]
    assert base['shared_synset'] == [[0, 1]]


def test_unlinked_cross_source_pair_stays_unknown():
    labels = {'reference': [{'label': 'Unbekannt'}], 'student': [{'label': 'Unknown'}]}
    routes = {'reference': [{'allowed_lexicons': ['de']}], 'student': [{'allowed_lexicons': ['en']}]}
    lexicons = SimpleNamespace(matrices=lambda *a, **kw: (
        np.zeros((1, 1)), {'pair_known': np.zeros((1, 1))}, None))
    result, _ = linked_cross_language(lexicons, labels, routes, {'pair_known': [[0]], 'shared_synset': [[0]]})
    assert result['pair_known'] == [[0]]


@pytest.mark.parametrize(('left', 'right', 'confirmed'), [
    (' Kunde ', 'kunde', True), ('Gebäude', 'Geba\u0308ude', True),
    ('Gebäude', 'Gebaeude', False), ('Raum 1', 'Raum 2', False),
])
def test_exact_normalization_does_not_remove_umlauts_or_digits(left, right, confirmed):
    _, adapter = production_modules()
    case = {'reference': [{'id': 'r', 'label': left}], 'student': [{'id': 's', 'label': right}]}
    feature = {'scores': {'damerau_canonical': [[1.]]},
               'lexicons': {'test': {k: [[v]] for k, v in features(antonym=1).items()}}}
    settings = {'thresholds': {'spelling': .85, 'meaning_floor': .7}}
    result = tree_scores(case, feature, np.array([[.9]]), .85, settings, adapter,
                         decision_options={'exact_first': True})['test']
    assert bool(result['scores'][0][0]) is confirmed
