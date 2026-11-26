"""Quellenwahl, Akzenttreue und fehlende/verknüpfte Bedeutungen."""

import os
from types import SimpleNamespace

import pytest

from synonym_matching.lexicons import LexiconMatcher, OdeNet


def profile(ids=()):
    return {'synsets': frozenset(ids), 'nodes': [], 'ancestors': set(),
            'antonym_synsets': set(), 'senses': set(), 'antonym_senses': set()}


def test_odenet_before_detection_and_english_fallback(monkeypatch):
    matcher = LexiconMatcher()
    monkeypatch.setattr(matcher.backends['de'], 'lookup', lambda t: {'de-synset'} if t == 'Experiment' else set())
    monkeypatch.setattr(matcher, 'detect', lambda t: 'en' if t == 'Building' else None)
    assert matcher.route('Experiment', 'Experiment', 'odenet_linked') == 'de'
    assert matcher.route('Building', 'Building', 'odenet_linked') == 'en'
    assert matcher.route('xyz', 'xyz', 'odenet_linked') is None
    assert matcher.route('Building', 'Building', 'odenet') == 'de'


def test_odenet_does_not_merge_zahlung_with_zaehlung():
    backend = OdeNet()
    backend.reader = SimpleNamespace(words=lambda t: [SimpleNamespace(forms=lambda: ['Zahlung', 'Zählung'])])
    assert backend._forms('zahlung') == {None: {'Zahlung'}}
    assert backend._forms('Zählung') == {None: {'Zählung'}}


def test_unknown_cross_language_and_linked_profiles(monkeypatch):
    matcher = LexiconMatcher()
    monkeypatch.setattr(matcher, 'profile', lambda text, language, linked=False:
        profile(['english-room']) if linked else profile([language+'-room']) if language else profile())
    direct = matcher.pair_features('Raum', 'Room', 'de', 'en', mode='odenet_first')
    assert direct['reference_known'] == direct['student_known'] == 1
    assert direct['pair_known'] == direct['shared_synset'] == 0
    linked = matcher.pair_features('Raum', 'Room', 'de', 'en')
    assert linked['shared_synset'] == 1
    unknown = matcher.pair_features('Raum', 'xyz', 'de', None)
    assert unknown['reference_known'] == 1 and unknown['student_known'] == 0
    assert unknown['taxonomy_available'] == 0


def test_missing_lexicon_reports_current_preparation_command(tmp_path):
    with pytest.raises(FileNotFoundError, match='PYTHONPATH=src python scripts/download_lexicons.py'):
        OdeNet(tmp_path).lookup('Kunde')


@pytest.mark.integration
@pytest.mark.skipif(os.getenv('RUN_MODEL_TESTS') != '1', reason='opt-in local lexicons')
def test_real_lexicons_translate_and_distinguish_accents():
    matcher = LexiconMatcher()
    assert not (matcher.backends['de'].lookup('Zahlung') & matcher.backends['de'].lookup('Zählung'))
    values = matcher.pair_features('Gebäude', 'Building', 'de', 'en')
    assert values['shared_synset'] == values['pair_known'] == 1
    assert values['taxonomy_available'] == 1
