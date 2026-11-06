import os
import numpy as np
import pytest
from synonym_matching import MatchingEngine
from synonym_matching.lexicons import WordNet, OpenThesaurus


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
        def synsets(self, word):
            self.calls.append(word)
            class Synset:
                def name(self):
                    return 'customer.n.01'
            return [Synset()] if word in {'customer', 'client'} else []
    lexicon = WordNet()
    lexicon.reader = Reader()
    assert lexicon.matrix(['customer', 'customer'], ['client', 'unknown']).tolist() == [[1, 0], [1, 0]]
    lexicon.lookup('Customer')
    lexicon.lookup('ice cream')
    assert lexicon.reader.calls == ['customer', 'client', 'unknown', 'ice_cream']


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


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='set RUN_LEXICON_TESTS=1 for downloaded lexicons')
def test_real_lexicons():
    assert WordNet().matrix(['customer', 'vehicle'], ['client', 'car']).tolist() == [[1, 0], [0, 0]]
    assert OpenThesaurus().matrix(['Kunde'], ['Abnehmer'])[0, 0] == 1
