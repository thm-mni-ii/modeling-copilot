"""Deutsche Kürzel optional expandieren, ohne Wortteile oder Originaldaten zu verlieren."""

import pytest

from synonym_matching.preprocessing import expand_abbreviations, expand_modeling_abbreviations, Preprocessor
from research.decision_tree import label_forms, production_modules


@pytest.mark.parametrize('short,full', [
    ('Anz.', 'Anzahl'), ('Bez.', 'Bezeichnung'), ('Beschr.', 'Beschreibung'),
    ('PLZ', 'Postleitzahl'), ('bez.', 'Bezeichnung'),
    ('ArtikelAnz.', 'Artikel Anzahl'), ('Artikel-Anz.', 'Artikel-Anzahl'),
    ('Artikel_Anz.', 'Artikel_Anzahl'),
])
def test_known_abbreviations_at_visible_boundaries(short, full):
    assert expand_modeling_abbreviations(short, 'de') == full


@pytest.mark.parametrize('text', ['Finanz.', 'Bezirk', 'PLZahl', 'Anz.foo', 'Pers.', 'Str.', 'Nr.'])
def test_unknown_or_embedded_terms_are_not_expanded(text):
    assert expand_modeling_abbreviations(text, 'de') == text


@pytest.mark.parametrize('language', ['en', None])
def test_do_not_assume_german(language):
    assert expand_modeling_abbreviations('PLZ Bez.', language) == 'PLZ Bez.'


def test_originals_and_existing_number_rule_are_preserved():
    source = [{'id': 'x', 'label': 'Bez.', 'language': 'de'}]
    assert label_forms(source, {'Bez.': 'Bezeichnung'})[0]['label'] == 'Bezeichnung'
    assert source[0]['label'] == 'Bez.'
    assert label_forms(source, {}) == source
    assert expand_modeling_abbreviations('a\nb', 'de', abbreviations={}) == 'a\nb'
    assert expand_abbreviations(expand_modeling_abbreviations('Personalnr.', 'de'), 'de') == 'Personal Nummer'
    assert Preprocessor(['expand_modeling_abbreviations']).process('Anz.', 'de') == 'Anzahl'


def test_expanded_text_works_with_productive_canonical_comparator():
    registry, _ = production_modules()
    method = registry.resolve_methods(['damerau_canonical'])[0]
    texts = [expand_modeling_abbreviations(t, 'de') for t in ['ArtikelAnz.', 'Artikelanzahl']]
    for step in method.preprocessing:
        texts = [registry.PREPROCESSORS[step](t) for t in texts]
    assert method.compute(None, texts[:1], texts[1:])[0,0] == 1
    assert expand_modeling_abbreviations('Str.', 'de', abbreviations={'Str.': 'Straße'}) == 'Straße'
    assert expand_modeling_abbreviations('Str.', 'de') == 'Str.'
