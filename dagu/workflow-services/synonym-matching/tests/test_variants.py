import json
import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.variants import VARIANTS, REQUIRES, evaluate_variant
from synonym_matching.methods import token_jaccard, token_sort_ratio, word_order
from synonym_matching.preprocessing import remove_stopwords, stem


def feature_matrices(shape=(2, 3)):
    base = np.linspace(.1, .9, np.prod(shape)).reshape(shape)
    return {name: base.copy() for names in REQUIRES.values() for name in names}


@pytest.mark.parametrize('name', list(VARIANTS))
def test_every_variant_returns_a_matrix_without_changing_inputs(name):
    scores = feature_matrices()
    before = {k: v.copy() for k, v in scores.items()}
    options = {}
    result = evaluate_variant(name, scores, **options)
    assert result.shape == (2, 3)
    assert np.isfinite(result).all()
    assert ((result >= 0) & (result <= 1)).all()
    for key in before:
        np.testing.assert_array_equal(scores[key], before[key])


def test_active_catalog():
    assert len(VARIANTS) == 15
    assert VARIANTS.keys() == REQUIRES.keys()


def test_token_order_is_not_a_set_score():
    left, right = ['customer pays supplier'], ['supplier pays customer']
    assert token_jaccard(left, right)[0, 0] == 1
    assert token_sort_ratio(left, right)[0, 0] == 1
    assert word_order(left, right)[0, 0] < 1


def test_context_uses_competing_candidates_and_preserves_ties():
    scores = feature_matrices((1, 2))
    result = evaluate_variant('context_aware', scores)
    assert result[0, 0] < scores['multilingual'][0, 0]
    assert result[0, 1] == scores['multilingual'][0, 1]
    tied = {n: np.full((2, 2), .2) for n in scores}
    np.testing.assert_allclose(evaluate_variant('context_aware', tied), .2)
    assert evaluate_variant('context_aware', {n: np.zeros((0, 2)) for n in scores}).shape == (0, 2)


def test_exact_rule_uses_original_labels_not_lowercased_text():
    config = {'methods': list(REQUIRES['exact_match_fusion']),
              'preprocessing': ['lowercase'],
              'combiner': {'kind': 'variant', 'name': 'exact_match_fusion'}}
    # Check exact feature without downloading an encoder.
    config['methods'] = ['exact_match']
    config['combiner'] = {'kind': 'mean'}
    result = MatchingEngine(config).match(['Kunde', ' ', 'Kunde'], ['kunde', '', ' Kunde '])
    assert result['scores']['exact_match'] == [[0, 0, 1], [0, 0, 0], [0, 0, 1]]


def test_geometric_zero_veto_and_weight_endpoints():
    scores = feature_matrices()
    scores['multilingual'][:] = 0
    assert not evaluate_variant('geometric_fusion', scores).any()
    assert not evaluate_variant('weighted_fusion', scores, embedding_weight=1).any()
    np.testing.assert_array_equal(evaluate_variant('weighted_fusion', scores, embedding_weight=0),
                                  evaluate_variant('string_ensemble', scores))










def test_stopword_ablation_can_remove_negation_and_produce_empty_labels():
    assert 'nicht' not in remove_stopwords('nicht bezahlt', 'de').split()
    assert remove_stopwords('the', 'en') == ''
    engine = MatchingEngine({'methods': ['token_jaccard'], 'preprocessing': ['remove_stopwords']})
    result = engine.match([{'id': 'r', 'label': 'the', 'language': 'en'}],
                          [{'id': 's', 'label': 'the', 'language': 'en'}], threshold=0)
    assert result['combinedScores'] == [[0]]
    assert result['synonymMatrix'][0]['matches'] == []


def test_stemming_without_extra_corpus_downloads():
    pytest.importorskip('nltk')
    assert stem('customers', 'en') == 'custom'
    assert stem('Rechnungen', 'de') == stem('Rechnung', 'de')
