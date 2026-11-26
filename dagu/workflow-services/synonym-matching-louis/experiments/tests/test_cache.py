from synonym_matching.cache import Cache
from synonym_matching.translation import Translator
import pytest


def test_memory_cache_and_namespace_isolation():
    calls = []
    def compute(texts):
        calls.append(texts)
        return [t.upper() for t in texts]
    first = Cache()
    assert first.get_many({'model': 'a'}, ['x', 'x', 'y'], compute) == ['X', 'X', 'Y']
    assert first.get_many({'model': 'a'}, ['y'], compute) == ['Y']
    first.get_many({'model': 'b'}, ['y'], compute)
    assert calls == [['x', 'y'], ['y']]
    assert first.hits == 1


def test_translation_once_per_unique_german_label(monkeypatch):
    import synonym_matching.translation as module
    monkeypatch.setattr(module, 'version', lambda _: 'test')
    translator = Translator({}, Cache())
    translator.model, translator.revision = object(), 'pinned'
    calls = []
    def compute(texts):
        calls.append(texts)
        return ['customer' for t in texts]
    monkeypatch.setattr(translator, '_compute', compute)
    assert translator.translate(['Kunde', 'Kunde', 'customer', ''], ['de', 'de', 'en', None]) == ['customer', 'customer', 'customer', '']
    translator.translate(['Kunde'], ['de'])
    assert calls == [['Kunde']]
    with pytest.raises(ValueError, match='explicit de/en'):
        translator.translate(['client'], ['fr'])
