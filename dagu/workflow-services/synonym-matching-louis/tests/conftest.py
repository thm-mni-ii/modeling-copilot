"""Leichte Testdoubles: keine Modellgewichte im normalen Testlauf."""

import numpy as np
import pytest

from synonym_matching.lexicons import LexiconMatcher, RELATION_FEATURES
from synonym_matching.methods import SentenceEmbedding
from synonym_matching import MatchingPipeline


@pytest.fixture
def fake_pipeline(monkeypatch):
    def matrix(self, left, right):
        return np.asarray([[1. if a == b and a else .6 if a and b else 0.
                            for b in right] for a in left]).reshape(len(left), len(right))
    monkeypatch.setattr(SentenceEmbedding, 'matrix', matrix)
    monkeypatch.setattr(LexiconMatcher, 'route', lambda *args: None)
    monkeypatch.setattr(LexiconMatcher, 'pair_features', lambda *args, **kwargs: {
        **dict.fromkeys(RELATION_FEATURES, 0.), 'shared_synset': 0.,
        'reference_known': 0., 'student_known': 0., 'reference_linked': 0.,
        'student_linked': 0., 'cross_language': 0.})
    return MatchingPipeline()
