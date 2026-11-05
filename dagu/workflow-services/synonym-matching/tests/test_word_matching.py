import json

import numpy as np
import pytest
from types import SimpleNamespace

from research.word_matching import WordMatching, greedy_matching
from research.evaluation import global_ranking
from research.compare import run_experiments


def archive(path, words, vectors):
    pytest.importorskip('gensim')
    values = np.asarray(vectors, dtype=float)
    lines = [f'{len(words)} {values.shape[1]}']
    lines += [word + ' ' + ' '.join(str(value) for value in row)
              for word, row in zip(words, values, strict=True)]
    path.write_text('\n'.join(lines) + '\n')
    return str(path)


def test_greedy_is_not_hungarian_and_does_not_mutate_matrix():
    scores = np.array([[.9, .8], [.85, .1]])
    before = scores.copy()
    assert greedy_matching(scores) == pytest.approx(.5)
    # Global optimal wäre (.8 + .85) / 2; die Paper-Regel ist ausdrücklich greedy.
    assert greedy_matching(scores) != pytest.approx(.825)
    np.testing.assert_array_equal(scores, before)
    assert greedy_matching(np.array([[.9, .4, .1]])) == pytest.approx((.9 + 2 * .2) / 3)
    assert greedy_matching(np.zeros((0, 3))) == .2
    assert greedy_matching(np.zeros((0, 0))) == 0
    with pytest.raises(ValueError):
        greedy_matching([[float('nan')]])


def test_aligned_languages_unknown_words_and_label_cache(tmp_path):
    de = archive(tmp_path / 'de.vec', ['kunde', 'lieferant'], [[1, 0], [0, 1]])
    en = archive(tmp_path / 'en.vec', ['customer', 'supplier'], [[1, 0], [0, 1]])
    backend = WordMatching({'files': {'de': de, 'en': en}, 'format': 'word2vec_text', 'aligned': True})
    refs = [{'label': 'Kunde', 'language': 'de'}]
    students = [{'label': t, 'language': 'en'} for t in ('Customer', 'Supplier', 'unknown customer', '')]
    assert backend.matrix(refs, students).tolist()[0] == pytest.approx([1, 0, .6, 0])
    before = len(backend.labels)
    backend.matrix(refs, students)
    assert len(backend.labels) == before
    assert len(backend.models) == 2
    with pytest.raises(ValueError, match='aligned'):
        WordMatching({'files': {'de': de, 'en': en}, 'format': 'word2vec_text'})


def test_optional_noun_filter_and_explicit_translation(tmp_path, monkeypatch):
    path = archive(tmp_path / 'en.vec', ['customer'], [[1, 0]])
    class Translator:
        def translate(self, texts, languages):
            assert languages == ['de']
            return ['customer pay']
    monkeypatch.setattr('research.word_matching._language_model', lambda lang:
        lambda text: [SimpleNamespace(text='customer', pos_='NOUN'), SimpleNamespace(text='pay', pos_='VERB')])
    backend = WordMatching({'files': {'en': path}, 'format': 'word2vec_text',
                            'translate_to_en': True, 'nouns_only': True}, Translator())
    words, vectors = backend.prepare({'label': 'Kunde bezahlt', 'language': 'de'})
    assert words == ['customer']
    assert len(vectors) == 1


def test_real_gensim_file_formats_and_fasttext_subwords(tmp_path):
    pytest.importorskip('gensim')
    from gensim.models import KeyedVectors, FastText
    from gensim.models.fasttext import save_facebook_model

    vectors = KeyedVectors(vector_size=2)
    vectors.add_vectors(['customer', 'supplier'], np.array([[1., 0.], [0., 1.]], dtype=np.float32))
    elements = [{'label': word, 'language': 'en'} for word in ('customer', 'supplier')]
    for fmt, binary in [('word2vec_text', False), ('word2vec_binary', True)]:
        path = tmp_path / fmt
        vectors.save_word2vec_format(str(path), binary=binary)
        backend = WordMatching({'files': {'en': str(path)}, 'format': fmt})
        np.testing.assert_allclose(backend.matrix(elements, elements), np.eye(2))
    glove = tmp_path / 'glove.txt'
    glove.write_text('customer 1 0\nsupplier 0 1\n')
    backend = WordMatching({'files': {'en': str(glove)}, 'format': 'glove'})
    np.testing.assert_allclose(backend.matrix(elements, elements), np.eye(2))

    # Paragram enthält vereinzelt ungültige Bytes in Wortschlüsseln.
    glove.write_bytes(b'\xff 0 1\ncustomer 1 0\n')
    backend = WordMatching({'files': {'en': str(glove)}, 'format': 'glove'})
    assert backend.matrix(elements[:1], elements[:1])[0, 0] == pytest.approx(1)

    # Nur initialisierte Testgewichte für Datei-I/O, kein Qualitätsmodell/Training.
    model = FastText(vector_size=4, min_count=1, bucket=100, min_n=2, max_n=3, seed=42)
    model.build_vocab([['customer', 'supplier']])
    path = tmp_path / 'fasttext.bin'
    save_facebook_model(model, str(path))
    backend = WordMatching({'files': {'en': str(path)}, 'format': 'fasttext_bin'})
    _, result = backend.prepare({'label': 'customers', 'language': 'en'})
    assert result[0] is not None
    assert np.linalg.norm(result[0]) == pytest.approx(1)


def test_global_rank_fusion_ignores_ineligible_candidates():
    scores = np.array([[.9, 1], [.8, .7]])
    eligible = np.array([[True, False], [True, True]])
    result = global_ranking(scores, eligible)
    assert result[0, 0] == .9
    assert result[0, 1] == 0
    assert result[1, 0] < scores[1, 0]
    assert global_ranking(np.zeros((0, 2)), np.zeros((0, 2), dtype=bool)).shape == (0, 2)


def test_new_comparison_reuses_fasttext_for_hungarian_and_marks_missing_resources(tmp_path):
    path = archive(tmp_path / 'de.vec', ['kunde', 'lieferant'], [[1, 0], [0, 1]])
    data = {'cases': [{'id': 'test', 'case_number': 23, 'title': 'Kandidaten',
        'reference': [{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
        'student': [{'id': 's1', 'label': 'Kunde', 'language': 'de'},
                    {'id': 's2', 'label': 'Lieferant', 'language': 'de'}],
        'annotations': [['correct', 'incorrect']]}]}
    output = tmp_path / 'run.json'
    assert run_experiments(data, output, pipelines={'raw': []}, new_methods=True,
                           word_vectors={'fasttext': {'files': {'de': path}, 'format': 'word2vec_text'}}) == []
    result = json.loads(output.read_text())
    fasttext = next(r for r in result['records'] if r['experiment'] == 'fixed/fasttext_matching')
    assert fasttext['decisions']['hungarian']['selected'] == [[True, False]]
    assert sum(f['method'] == 'fasttext_matching' for f in result['features']) == 1
    assert next(r for r in result['records'] if r['experiment'] == 'fixed/word2vec_matching')['status'] == 'unavailable'
    assert 'deferred' not in result
    assert result['additional_resources']['word_vectors']['fasttext']['sha256']['de']
