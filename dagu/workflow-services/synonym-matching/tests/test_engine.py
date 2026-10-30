import numpy as np
import pytest
from synonym_matching import MatchingEngine
from synonym_matching.combiners import combine
from synonym_matching.methods import damerau_levenshtein, levenshtein, char_trigram, EmbeddingMethod
from synonym_matching.preprocessing import Preprocessor


def test_matrix_orientation_ids_duplicates_and_threshold():
    engine = MatchingEngine({'methods': ['levenshtein']})
    refs = [{'id': 7, 'label': 'Kunde'}, {'id': '7', 'label': 'Kunde'}]
    result = engine.match(refs, ['Kund', 'Kunde', 'Lieferant'], threshold=1)
    assert result['shape'] == [2, 3]
    assert result['referenceElements'] == refs
    assert result['scores']['levenshtein'][0][:2] == [.8, 1]
    assert result['scores']['levenshtein'][0] == result['scores']['levenshtein'][1]
    assert [r['matches'][0]['submissionElement']['id'] for r in result['synonymMatrix']] == ['student:1'] * 2


@pytest.mark.parametrize('left,right,shape', [([], [], [0, 0]), ([], ['a'], [0, 1]), (['a'], [], [1, 0])])
def test_empty_shapes(left, right, shape):
    result = MatchingEngine().match(left, right)
    assert result['shape'] == shape
    assert result['combinedScores'] == ([[]] if shape == [1, 0] else [])


def test_blank_labels_never_become_candidates_even_at_zero():
    result = MatchingEngine().match([' ', ''], ['', 'x'], threshold=0)
    assert result['combinedScores'] == [[0, 0], [0, 0]]
    assert all(not row['matches'] for row in result['synonymMatrix'])


def test_true_damerau_transposition_and_short_ngrams():
    assert damerau_levenshtein(['ab'], ['ba'])[0, 0] == .5
    assert levenshtein(['ab'], ['ba'])[0, 0] == 0
    assert char_trigram(['x'], ['x', 'y']).tolist() == [[1, 0]]


def test_preprocessing_is_explicit():
    assert Preprocessor({'normalize': False}).process(' A\tB ') == ' A\tB '
    assert Preprocessor().process(' A\tB ') == 'A B'
    assert Preprocessor().process('a\u0308') == 'ä'
    assert Preprocessor({'split_identifiers': True, 'lowercase': True}).process('createAccount') == 'create account'
    with pytest.raises(ValueError, match='explicit language'):
        Preprocessor({'lemmatize': True}).process('Kunde')


@pytest.mark.parametrize('config', [
    {'methods': []}, {'methods': ['typo']}, {'methods': ['levenshtein', 'levenshtein']},
    {'preprocessing': {'lowercasing': True}}, {'seed': -1}, {'other': 1},
    {'combiner': {'kind': 'weighted_mean', 'weights': {}}},
    {'methods': ['levenshtein'], 'combiner': {'kind': 'weighted_mean', 'weights': {'levenshtein': -1}}},
])
def test_bad_config(config):
    with pytest.raises(ValueError):
        MatchingEngine(config)


@pytest.mark.parametrize('threshold', [-1, 2, float('nan'), True, '0.5'])
def test_bad_threshold(threshold):
    with pytest.raises(ValueError):
        MatchingEngine().match(['x'], ['x'], threshold=threshold)


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        MatchingEngine().match([{'id': 'x', 'label': 'a'}, {'id': 'x', 'label': 'b'}], [])


def test_weighted_scores_and_cosine_clipping():
    scores = {'a': np.array([[-.5, .2]]), 'b': np.array([[1, .8]])}
    result = combine(scores, {'kind': 'weighted_mean', 'weights': {'a': 1, 'b': 3}})
    assert result.tolist()[0] == pytest.approx([.75, .65])
    assert scores['a'][0, 0] == -.5


def test_ties_have_stable_order():
    result = MatchingEngine().match(['a'], ['a', 'a'])
    row = result['synonymMatrix'][0]
    assert [m['submissionElement']['id'] for m in row['matches']] == ['student:0', 'student:1']


def test_embedding_batches_unique_labels_and_reuses_cache(monkeypatch):
    from synonym_matching.cache import Cache
    import synonym_matching.methods as methods
    monkeypatch.setattr(methods, 'version', lambda _: 'test')
    method = EmbeddingMethod('multilingual', {}, Cache())
    method.model, method.revision = object(), 'test-revision'
    calls = []
    def encode(texts):
        calls.append(texts)
        return [[1., 0.] if t == 'a' else [0., 1.] for t in texts]
    monkeypatch.setattr(method, '_encode', encode)
    assert method.matrix(['a', 'a'], ['b', 'a']).tolist() == [[0, 1], [0, 1]]
    method.matrix(['a'], ['b'])
    assert calls == [['a', 'b']]


def test_display_rounding_preserves_threshold_decisions():
    from synonym_matching.engine import format_synonym_matrix
    engine = MatchingEngine()
    result = engine.match(['Kunde'], ['Kund'], threshold=.79532)
    matrix = result['synonymMatrix']
    displayed = format_synonym_matrix(matrix)
    assert displayed[0]['matches'][0]['combinedScore'] == .7953
    assert matrix[0]['matches'][0]['combinedScore'] > .79532
    assert not engine.match(['Kunde'], ['Kund'], threshold=.79534)['synonymMatrix'][0]['matches']
    assert set(displayed[0]) == {'referenceElement', 'matches'}
    assert set(displayed[0]['matches'][0]) == {'submissionElement', 'scores', 'combinedScore'}
