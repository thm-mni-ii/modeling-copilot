import os
import numpy as np
import pytest
from synonym_matching import MatchingEngine
from synonym_matching.lexicons import OdeNet, WordNet, OpenThesaurus


def test_openthesaurus_groups_not_transitive_and_unknowns_zero(tmp_path):
    path = tmp_path / 'thesaurus.txt'
    path.write_text('# source\nKunde;Abnehmer (fachspr.)\nAbnehmer;Käufer\n(von etwas) fortfahren;abfahren\n')
    lexicon = OpenThesaurus(path)
    assert lexicon.matrix(['Kunde', 'Unbekannt', '', 'Kunde'], ['Abnehmer', 'Käufer', 'Unbekannt']).tolist() == [
        [1, 0, 0], [0, 0, 0], [0, 0, 0], [1, 0, 0]]
    assert not lexicon.lookup('fortfahren')  # Meaningful parenthesis not stripped.
    assert lexicon.matrix([], ['Kunde']).shape == (0, 1)


def test_wordnet_lookup_cached_and_phrase_normalized():
    class Reader:
        calls = []
        def synsets(self, word, pos=None):
            self.calls.append(word)
            class Synset:
                id = 'omw-en-09984659-n'
            return [Synset()] if word in {'customer', 'client'} else []
    lexicon = WordNet()
    lexicon.reader = Reader()
    assert lexicon.matrix(['customer', 'customer'], ['client', 'unknown']).tolist() == [[1, 0], [1, 0]]
    lexicon.lookup('Customer')
    lexicon.lookup('ice cream')
    assert lexicon.reader.calls == ['customer', 'client', 'unknown', 'ice cream']
    lexicon.lookup('ice_cream')
    assert lexicon.reader.calls[-1] == 'ice cream'


def test_engine_translates_only_wordnet_and_preserves_labels(monkeypatch):
    engine = MatchingEngine({'methods': ['wordnet', 'levenshtein']})
    calls = []
    def translate(texts, languages):
        calls.append((texts, languages))
        return ['customer', 'client']
    monkeypatch.setattr(engine.translator, 'translate', translate)
    monkeypatch.setattr(engine.backends['wordnet'], 'matrix', lambda a, b: np.array([[float(a == ['customer'] and b == ['client'])]]))
    ref = [{'id': 'r', 'label': 'Kunde', 'language': 'de'}]
    student = [{'id': 's', 'label': 'client', 'language': 'en'}]
    result = engine.match(ref, student)
    assert result['scores']['wordnet'] == [[1]]
    assert result['referenceElements'] == ref
    assert result['processedLabels']['levenshtein']['reference'] == ['Kunde']
    assert len(calls) == 1


def test_openthesaurus_rejects_non_german():
    engine = MatchingEngine({'methods': ['openthesaurus']})
    with pytest.raises(ValueError, match='explicit de'):
        engine.match([{'id': 'r', 'label': 'Customer', 'language': 'en'}], ['Kunde'])


def test_missing_resources_raise_not_zero(tmp_path):
    with pytest.raises(FileNotFoundError):
        OpenThesaurus(tmp_path / 'missing').matrix(['Kunde'], ['Abnehmer'])
    with pytest.raises(FileNotFoundError, match='WordNet missing'):
        WordNet(tmp_path).matrix(['customer'], ['client'])
    with pytest.raises(FileNotFoundError, match='OdeNet missing'):
        OdeNet(tmp_path).matrix(['Kunde'], ['Abnehmer'])


def test_odenet_caches_synsets_and_does_not_invent_unknown_matches():
    class Reader:
        calls = []

        def synsets(self, text, pos=None):
            self.calls.append(text)
            from types import SimpleNamespace
            return [SimpleNamespace(id='customer')] if text in {'kunde', 'abnehmer'} else []

    lexicon = OdeNet()
    lexicon.reader = Reader()
    assert lexicon.matrix(['Kunde', 'Kunde', '', 'unbekannt'],
                          ['Abnehmer', 'unbekannt']).tolist() == [[1, 0], [1, 0], [0, 0], [0, 0]]
    assert lexicon.reader.calls == ['kunde', 'unbekannt', 'abnehmer']
    assert lexicon.matrix([], ['Kunde']).shape == (0, 1)


def test_odenet_engine_uses_original_german_and_rejects_english(monkeypatch):
    engine = MatchingEngine({'methods': ['odenet']})

    def no_translation(*args):
        raise AssertionError('OdeNet must not translate')

    monkeypatch.setattr(engine.translator, 'translate', no_translation)
    monkeypatch.setattr(engine.backends['odenet'], 'matrix', lambda a, b: np.ones((len(a), len(b))))
    ref = [{'id': 'r', 'label': 'Kunde', 'language': 'de'}]
    student = [{'id': 's', 'label': 'Abnehmer', 'language': 'de'}]
    result = engine.match(ref, student)
    assert result['processedLabels']['odenet'] == {'reference': ['Kunde'], 'student': ['Abnehmer']}
    assert result['scores']['odenet'] == [[1]]
    with pytest.raises(ValueError, match='explicit de'):
        engine.match(ref, [{'id': 's', 'label': 'Customer', 'language': 'en'}])


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='set RUN_LEXICON_TESTS=1 for downloaded lexicons')
def test_real_lexicons():
    assert WordNet().matrix(['customer', 'vehicle'], ['client', 'car']).tolist() == [[1, 0], [0, 0]]
    assert OpenThesaurus().matrix(['Kunde'], ['Abnehmer'])[0, 0] == 1


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='set RUN_LEXICON_TESTS=1 for downloaded lexicons')
def test_real_odenet_finds_umlauts_with_index_normalization():
    import unicodedata

    lexicon = OdeNet()
    for label in ['Gebäude', 'Größe', 'Fläche', 'Gerät']:
        expected = lexicon.lookup(label)
        assert expected, f'OdeNet should find {label}'
        assert lexicon.lookup(label.lower()) == expected
        assert lexicon.lookup(unicodedata.normalize('NFD', label)) == expected
    assert lexicon.matrix(['Gebäude'], ['Gebäude']).tolist() == [[1]]
    assert not lexicon.lookup('FachbegriffXYZUnbekannt')


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='set RUN_LEXICON_TESTS=1 for downloaded lexicons')
def test_real_wn_english_morphology_phrases_and_satellites():
    lexicon = WordNet()
    for singular, plural in [('customer', 'customers'), ('mouse', 'mice'),
                             ('ice cream', 'ice creams')]:
        assert lexicon.lookup(singular) & lexicon.lookup(plural)
    assert lexicon.lookup('ice cream') == lexicon.lookup('ice_cream')
    assert any(synset.endswith('-s') for synset in lexicon.lookup('active'))
    assert lexicon.lookup('better') & lexicon.lookup('good')
    assert lexicon.matrix(['customer', 'vehicle'], ['client', 'car']).tolist() == [[1, 0], [0, 0]]
    assert not lexicon.lookup('unknownxyznonword')


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='set RUN_LEXICON_TESTS=1 for downloaded lexicons')
def test_english_wordnet_needs_no_translation_model(monkeypatch):
    engine = MatchingEngine({'methods': ['wordnet']})

    def no_model():
        raise AssertionError('English labels must not load the translation model')

    monkeypatch.setattr(engine.translator, '_load', no_model)
    result = engine.match([{'id': 'r', 'label': 'customer', 'language': 'en'}],
                          [{'id': 's', 'label': 'client', 'language': 'en'}])
    assert result['scores']['wordnet'] == [[1]]


@pytest.mark.parametrize('flag,version', [('--wordnet', 'omw-en:1.4'), ('--odenet', 'odenet:1.4')])
def test_explicit_wn_download_uses_shared_cache_only(tmp_path, monkeypatch, flag, version):
    import sys
    from types import SimpleNamespace
    from scripts import download_lexicons

    calls = []
    fake_wn = SimpleNamespace(config=SimpleNamespace(), download=calls.append)
    monkeypatch.setattr(download_lexicons, 'wn', fake_wn)
    monkeypatch.setattr(download_lexicons, 'DATA', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['download_lexicons.py', flag])

    def no_thesaurus(*args):
        raise AssertionError('Selecting one WordNet must not download OpenThesaurus')

    monkeypatch.setattr(download_lexicons.urllib.request, 'urlretrieve', no_thesaurus)
    download_lexicons.main()
    assert calls == [version]
    assert fake_wn.config.data_directory == tmp_path / 'wn'
    assert (tmp_path / 'wn').is_dir()
