import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.methods import METHODS, levenshtein, jaro_winkler, char_ngram
from synonym_matching.preprocessing import apply_pipeline, normalize, lowercase, Preprocessor
from synonym_matching.combinations import mean, maximum, weighted_mean


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
    named = MatchingEngine({'methods': ['levenshtein'], 'preprocessing': ['normalize', 'lowercase']}).match([' Kunde '], ['KUND'])
    legacy = MatchingEngine({'methods': ['levenshtein'], 'preprocessing': {'normalize': True, 'lowercase': True}}).match([' Kunde '], ['KUND'])
    assert named['scores'] == legacy['scores']
    assert named['combinedScores'] == legacy['combinedScores']
    assert named['processedLabels']['levenshtein'] == {'reference': ['kunde'], 'student': ['kund']}


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


class FakeTranslator:
    """Übersetzt nur deutsche Labels; merkt sich die Sprachen jedes Aufrufs."""
    revision = None

    def __init__(self):
        self.calls = []

    def translate(self, texts, languages):
        self.calls.append(list(languages))
        table = {'kunde': 'customer', 'Kunde': 'Customer'}
        return [table.get(text, text) if language == 'de' else text
                for text, language in zip(texts, languages, strict=True)]


def test_translate_step_splits_pipeline_and_switches_language():
    translator = FakeTranslator()
    processor = Preprocessor(['normalize', 'lowercase', 'translate', 'stem'], translator)
    texts, languages = processor.process_many([' Kunde ', 'Customer', ''], ['de', 'en', 'de'])
    assert texts[0].startswith('custom') and languages == ['en', 'en', 'en']
    # Nach 'translate' gilt der Text als englisch und wird kein zweites Mal übersetzt.
    assert translator.calls == [['de', 'en', 'de']]
    with pytest.raises(ValueError, match='translator'):
        Preprocessor(['translate']).process_many(['Kunde'], ['de'])
    with pytest.raises(ValueError, match='only once'):
        Preprocessor(['translate', 'translate'])


def test_engine_translate_step_works_for_any_method_and_never_translates_twice():
    translator = FakeTranslator()
    config = {'methods': ['levenshtein', 'translated_string'],
              'preprocessing': ['normalize', 'translate']}
    engine = MatchingEngine(config, translator)
    result = engine.compute_scores([{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
                                   [{'id': 's', 'label': 'Customer', 'language': 'en'}])
    assert result['scores']['levenshtein'][0, 0] == pytest.approx(1)
    # Das implizit übersetzende Verfahren erhält bereits englische Labels.
    assert result['processedLabels']['translated_string']['reference'] == ['Customer']
    assert result['scores']['translated_string'][0, 0] == pytest.approx(1)
    assert all(set(languages) == {'en'} for languages in translator.calls[1:])


def test_method_traits_replace_name_checks_in_engine(monkeypatch):
    from synonym_matching.methods import METHOD_TRAITS
    seen = {}

    def xy(left, right):
        seen['texts'] = (left, right)
        return np.zeros((len(left), len(right)))

    monkeypatch.setitem(METHODS, 'xy', xy)
    monkeypatch.setitem(METHOD_TRAITS, 'xy', {'translate'})
    MatchingEngine({'methods': ['xy']}, FakeTranslator()).compute_scores(
        [{'id': 'r', 'label': 'kunde', 'language': 'de'}],
        [{'id': 's', 'label': 'customer', 'language': 'en'}])
    assert seen['texts'] == (['customer'], ['customer'])
