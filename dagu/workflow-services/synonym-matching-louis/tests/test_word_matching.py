import json

import numpy as np
import pytest
from types import SimpleNamespace

from research.word_matching import WordMatching, greedy_matching
from research.evaluation import global_ranking
from research.compare import load_config, run_experiments
from tests.test_comparison import only


def archive(path, words, vectors):
    pytest.importorskip('gensim')
    values = np.asarray(vectors, dtype=float)
    lines = [f'{len(words)} {values.shape[1]}']
    lines += [word + ' ' + ' '.join(str(value) for value in row)
              for word, row in zip(words, values, strict=True)]
    path.write_text('\n'.join(lines) + '\n')
    return str(path)


def test_optimal_matching_beats_greedy_and_bidirectional_is_symmetric():
    from research.word_matching import optimal_matching, bidirectional_matching

    scores = np.array([[.9, .8], [.85, .1]])
    assert greedy_matching(scores) == pytest.approx(.5)
    assert optimal_matching(scores) == pytest.approx((.8 + .85) / 2)
    assert optimal_matching(scores) >= greedy_matching(scores)
    # Rechteckig: nicht zugeordnete Wörter zählen mit delta.
    assert optimal_matching(np.array([[.9, .4, .1]])) == pytest.approx((.9 + 2 * .2) / 3)
    # Jedes Wort wählt sein bestes Gegenstück; (0.9 + 0.85)/2 und (0.9 + 0.8)/2 gemittelt.
    expected = ((.9 + .85) / 2 + (.9 + .8) / 2) / 2
    assert bidirectional_matching(scores) == pytest.approx(expected)
    assert bidirectional_matching(scores.T) == pytest.approx(expected)
    for function in (optimal_matching, bidirectional_matching):
        assert function(np.zeros((0, 3))) == .2
        assert function(np.zeros((0, 0))) == 0
        with pytest.raises(ValueError):
            function([[float('nan')]])


def test_matching_option_is_validated_and_variant_inherits_from_base(tmp_path):
    from research.compare import load_config

    config = load_config()['methods']
    optimal = config['fasttext_de_optimal_matching']
    assert optimal['files'] == config['fasttext_de_matching']['files']
    assert optimal['matching'] == 'optimal' and 'based_on' not in optimal
    path = archive(tmp_path / 'de.vec', ['kunde'], [[1, 0]])
    with pytest.raises(ValueError, match='unknown matching'):
        WordMatching({'files': {'de': path}, 'matching': 'nope'})
    elements = [{'label': 'kunde lieferant', 'language': 'de'}]
    assert WordMatching({'files': {'de': path}, 'matching': 'bidirectional'}).matrix(
        elements, elements)[0, 0] == pytest.approx((.5 + .5) / 2 * 1)


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


def test_optional_noun_filter(tmp_path, monkeypatch):
    path = archive(tmp_path / 'en.vec', ['customer'], [[1, 0]])
    monkeypatch.setattr('research.word_matching._language_model', lambda lang:
        lambda text: [SimpleNamespace(text='customer', pos_='NOUN'), SimpleNamespace(text='pay', pos_='VERB')])
    backend = WordMatching({'files': {'en': path}, 'format': 'word2vec_text', 'nouns_only': True})
    words, vectors = backend.prepare({'label': 'customer pay', 'language': 'en'})
    assert words == ['customer']
    assert len(vectors) == 1


def test_german_profile_preserves_case_and_excludes_mixed_language_cases(tmp_path):
    from research.compare import load_config, unsupported

    word2vec = load_config()['methods']['word2vec_de_matching']
    word2vec['files'] = {
        'de': archive(tmp_path / 'de.vec', ['Kunde', 'Abnehmer'], [[1, 0], [1, 0]])}
    word2vec['format'] = 'word2vec_text'
    backend = WordMatching(word2vec)
    left = [{'label': 'Kunde', 'language': 'de'}]
    right = [{'label': 'Abnehmer', 'language': 'de'}]
    assert backend.prepare(left[0])[0] == ['Kunde']
    assert backend.matrix(left, right)[0, 0] == pytest.approx(1)

    lowercase = WordMatching({**word2vec, 'lowercase': True})
    assert lowercase.matrix(left, right)[0, 0] == 0
    chain = ['normalize', 'word2vec_de_matching']
    case = {'reference': left, 'student': [{'label': 'Customer', 'language': 'en'}]}
    assert unsupported(word2vec, chain, case) is not None
    word2vec['files'] = {'de': str(tmp_path / 'fehlt.vec')}
    assert 'Ressource fehlt' in unsupported(word2vec, chain, {'reference': left, 'student': right})


def test_translate_step_comes_before_vector_lookup(tmp_path, monkeypatch):
    from research import compare
    from synonym_matching.translation import Translator

    class FakeTranslator(Translator):
        def translate(self, texts, languages):
            return ['customer' if lang == 'de' else text.lower()
                    for text, lang in zip(texts, languages, strict=True)]

    monkeypatch.setattr(compare, 'Translator', FakeTranslator)
    data = {'cases': [{'id': 'test', 'case_number': 1, 'title': 'Übersetzung',
            'reference': [{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
            'student': [{'id': 's', 'label': 'Customer', 'language': 'en'}],
            'annotations': [['correct']]},
            {'id': 'es', 'case_number': 11, 'title': 'Spanisch',
             'reference': [{'id': 'r', 'label': 'Cliente', 'language': 'es'}],
             'student': [{'id': 's', 'label': 'Customer', 'language': 'en'}],
             'annotations': [['correct']]}]}
    config = only(load_config(), 'ft_en_lowercase')
    config['languages'] = ['de', 'en', 'es']
    config['preprocessing'] = {'lower': ['normalize', 'lowercase']}
    config['methods']['fasttext_en_matching'].update({
        'files': {'en': archive(tmp_path / 'en.vec', ['customer'], [[1, 0]])}, 'format': 'word2vec_text'})
    output = tmp_path / 'run.json'
    assert compare.run_experiments(data, output, config) == []
    run = json.loads(output.read_text())
    records = {(r['experiment'], r['case']): r for r in run['records']}
    name = 'normalize+translate+lowercase → fasttext_en_matching'
    assert records[name, 'test']['combinedScores'] == [[1.0]]
    assert records[name, 'es']['status'] == 'unavailable'
    assert 'Übersetzung' in records[name, 'es']['missing']['fasttext_en_matching']['reason']

    for model in [m for m in load_config()['methods'].values() if 'files' in m]:
        assert model['source'].startswith('https://huggingface.co/')
        assert len(model['revision']) == 40
        assert len(model['files']) == 1


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
    pytest.importorskip('fasttext')
    backend = WordMatching({'files': {'en': str(path)}, 'format': 'fasttext_bin'})
    _, result = backend.prepare({'label': 'customers', 'language': 'en'})
    assert result[0] is not None
    assert np.linalg.norm(result[0]) == pytest.approx(1)
    # Der native Loader muss dieselben Vektoren liefern, einschließlich OOV.
    for word in ('customer', 'customers'):
        np.testing.assert_allclose(backend.models['en'][word], model.wv[word], atol=1e-6)


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
    config = only(load_config(), 'ft_de', 'w2v_de')
    config['preprocessing'] = {'raw': [], 'lowercase': ['lowercase']}
    config['methods']['fasttext_de_matching'].update({'files': {'de': path}, 'format': 'word2vec_text'})
    config['methods']['word2vec_de_matching']['files'] = {'de': str(tmp_path / 'fehlt.bin')}
    assert run_experiments(data, output, config) == []
    result = json.loads(output.read_text())
    fasttext = next(r for r in result['records'] if r['experiment'] == 'lowercase → fasttext_de_matching')
    assert fasttext['decisions']['hungarian']['selected'] == [[True, False]]
    # Ohne den expliziten Schritt darf die Suche nicht unbemerkt lowercase verwenden.
    raw = next(r for r in result['records'] if r['experiment'] == 'raw → fasttext_de_matching')
    assert raw['decisions']['hungarian']['selected'] == [[False, False]]
    assert sum(f['method'] == 'fasttext_de_matching' for f in result['features']) == 2
    missing = next(r for r in result['records'] if r['experiment'] == 'raw → word2vec_de_matching')
    assert missing['status'] == 'unavailable'
    assert 'Ressource fehlt' in missing['missing']['word2vec_de_matching']['reason']
    assert 'deferred' not in result
    assert result['additional_resources']['word_vectors']['fasttext_de_matching']['sha256']['de']


def test_word_vectors_use_pipeline_preprocessing_and_load_model_once(tmp_path, monkeypatch):
    import research.word_matching as module

    loads = []
    real_load = module.load_vectors
    monkeypatch.setattr(module, 'load_vectors', lambda *args: loads.append(args) or real_load(*args))
    path = archive(tmp_path / 'de.vec', ['Kunde'], [[1, 0]])
    data = {'cases': [{'id': 'test', 'case_number': 1, 'title': 'Groß-/Kleinschreibung',
        'reference': [{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
        'student': [{'id': 's', 'label': 'Kunde', 'language': 'de'}],
        'annotations': [['correct']]}]}
    config = only(load_config(), 'w2v_de')
    config['preprocessing'] = {'raw': [], 'lower': ['lowercase']}
    config['methods']['word2vec_de_matching'].update({'files': {'de': path}, 'format': 'word2vec_text'})
    output = tmp_path / 'run.json'
    assert run_experiments(data, output, config) == []
    records = {r['experiment']: r for r in json.loads(output.read_text())['records']}
    # Das Modell kennt nur die Großschreibung; Lowercasing in der Pipeline ist echte Ablation.
    assert records['raw → word2vec_de_matching']['combinedScores'] == [[1.0]]
    assert records['lowercase → word2vec_de_matching']['combinedScores'] == [[0.0]]
    assert len(loads) == 1
    run = json.loads(output.read_text())
    loaded = [f['load_seconds'] for f in run['features'] if f['status'] == 'ok']
    assert sum(value > 0 for value in loaded) == 1
    assert run['model_load_seconds']['word2vec_de_matching'] == pytest.approx(sum(loaded))
    assert run['additional_resources']['word_vectors']['word2vec_de_matching']['sha256_source'] == {'de': 'berechnet'}
