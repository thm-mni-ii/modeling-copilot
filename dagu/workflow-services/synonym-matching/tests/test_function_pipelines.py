import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.methods import METHODS, levenshtein, jaro_winkler, char_ngram
from synonym_matching.preprocessing import apply_pipeline, normalize, lowercase, Preprocessor
from synonym_matching.combiners import mean, maximum, weighted_mean


def test_functions_compose_without_engine():
    steps = [normalize, lowercase]
    left = [apply_pipeline(' Kunde ', steps)]
    right = [apply_pipeline('KUND', steps)]
    matrices = {'levenshtein': levenshtein(left, right), 'jaro_winkler': jaro_winkler(left, right)}
    assert mean(matrices)[0, 0] == pytest.approx(.88)
    assert maximum(matrices)[0, 0] == pytest.approx(.96)
    assert weighted_mean(matrices, weights={'levenshtein': 3, 'jaro_winkler': 1})[0, 0] == pytest.approx(.84)


def test_pipeline_order_and_empty_pipeline():
    def decorate(text, language=None):
        return 'X' + text
    assert apply_pipeline('A', [decorate, lowercase]) == 'xa'
    assert apply_pipeline('A', [lowercase, decorate]) == 'Xa'
    assert Preprocessor([]).process(' A ') == ' A '


def test_named_pipeline_is_equivalent_to_legacy_configuration():
    named = MatchingEngine({'preprocessing': ['normalize', 'lowercase']}).match([' Kunde '], ['KUND'])
    legacy = MatchingEngine({'preprocessing': {'normalize': True, 'lowercase': True}}).match([' Kunde '], ['KUND'])
    assert named['scores'] == legacy['scores']
    assert named['combinedScores'] == legacy['combinedScores']
    assert named['config']['preprocessing'] == ['normalize', 'lowercase']


def test_custom_method_needs_no_engine_changes(monkeypatch):
    def xy(left, right):
        return np.full((len(left), len(right)), .42)
    monkeypatch.setitem(METHODS, 'xy', xy)
    result = MatchingEngine({'methods': ['xy']}).match(['a'], ['b', 'c'])
    assert result['scores']['xy'] == [[.42, .42]]
    assert result['combinedScores'] == [[.42, .42]]


def test_invalid_ngram_size_and_step():
    with pytest.raises(ValueError):
        char_ngram(['a'], ['a'], n=0)
    with pytest.raises(ValueError):
        Preprocessor(['unknown'])
