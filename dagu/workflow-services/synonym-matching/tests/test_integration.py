"""Opt-in only: downloads model weights; never part of the offline test run."""
import os
import pytest
from synonym_matching import MatchingEngine

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get('RUN_MODEL_TESTS') != '1', reason='set RUN_MODEL_TESTS=1 to load real models')]


@pytest.mark.parametrize('method', ['multilingual', 'translated_embedding'])
def test_real_model_path(method):
    engine = MatchingEngine({'methods': [method]})
    refs = [{'id': 'r', 'label': 'Kunde', 'language': 'de'}]
    students = [{'id': 's', 'label': 'Customer', 'language': 'en'}]
    cold = engine.match(refs, students)
    misses = engine.cache.misses
    warm = engine.match(refs, students)
    assert cold['shape'] == [1, 1]
    assert engine.backends[method].revision
    assert -1 <= cold['scores'][method][0][0] <= 1
    assert warm['scores'] == cold['scores']
    assert engine.cache.misses == misses
