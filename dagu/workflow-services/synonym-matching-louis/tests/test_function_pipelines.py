import numpy as np
import pytest

from synonym_matching import MatchingEngine
from synonym_matching.methods import METHODS, levenshtein, jaro_winkler, char_ngram
from synonym_matching.preprocessing import apply_pipeline, normalize, lowercase, Preprocessor
from synonym_matching.combinations import mean, maximum, weighted_mean


@pytest.mark.parametrize(('text', 'expected'), [
    ('Nr.', 'Nummer'), ('Nr', 'Nummer'), ('GebäudeNr.', 'Gebäude Nummer'),
    ('GebäudeNR', 'Gebäude Nummer'), ('Gebäude Nr.', 'Gebäude Nummer'),
    ('Nr. unbekannt', 'Nummer unbekannt'), ('Nummer', 'Nummer'),
    ('Genre', 'Genre'), ('', ''),
])
def test_expand_number_abbreviation(text, expected):
    processor = Preprocessor(['expand_abbreviations'])
    assert processor.process(text, 'de') == expected
    assert processor.process(text, 'en') == text
    assert processor.process(text, None) == text


def test_label_parts_are_optional_and_keep_number_and_room_distinct(monkeypatch):
    monkeypatch.setattr('synonym_matching.preprocessing._compound_words',
                        lambda: {'gebäude', 'nummer', 'gerät', 'raum'})
    original = Preprocessor(['normalize'])
    parts = Preprocessor(['normalize', 'split_label_parts', 'lowercase'])
    assert original.process('GebäudeNr.', 'de') == 'GebäudeNr.'
    assert parts.process('GebäudeNr.', 'de') == parts.process('Gebäudenummer', 'de') == 'gebäude nummer'
    assert parts.process('Geräteraum', 'de') == 'geräte raum'
    assert parts.process('Gerätenummer', 'de') == 'geräte nummer'
    assert parts.process('Geräte', 'de') == 'geräte'
    assert parts.process('UnbekanntXYZ', 'de') == 'unbekannt xyz'
    assert Preprocessor(['split_label_parts']).process('buildingNumber', 'en') == 'buildingNumber'
    # Die bisherige Kompositazerlegung erhält ihre bisherige Behandlung von Pluralformen.
    assert Preprocessor(['split_compounds']).process('Geräteraum', 'de') == 'Geräteraum'


def test_label_parts_work_in_json_builder_and_public_schema(monkeypatch):
    import json
    from pathlib import Path

    import jsonschema

    from research.experiments import configurations, load_config
    from synonym_matching import match

    definitions, _ = configurations(load_config())
    assert 'normalize+expand_abbreviations → translated_embedding' in definitions
    assert 'normalize+split_label_parts → translated_embedding' in definitions
    monkeypatch.setattr('synonym_matching.preprocessing._compound_words',
                        lambda: {'gebäude', 'nummer', 'gerät', 'raum'})
    root = Path(__file__).resolve().parents[1]
    case = json.loads((root / 'research/label-parts-cases.json').read_text())['cases'][0]
    output = match(case['reference'], case['student'],
                   {'methods': ['token_jaccard'],
                    'preprocessing': ['normalize', 'split_label_parts', 'lowercase']})
    jsonschema.validate(output, json.loads((root / 'schemas/output.schema.json').read_text()))
    scores = {m['submissionElement']['id']: m['combinedScore']
              for m in output['synonymMatrix'][1]['matches']}
    assert scores['s2'] == scores['s3'] == 1
    assert scores['s1'] < scores['s2']
    assert len(output['synonymMatrix']) == 4
    assert all(len(row['matches']) == 6 for row in output['synonymMatrix'])


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
