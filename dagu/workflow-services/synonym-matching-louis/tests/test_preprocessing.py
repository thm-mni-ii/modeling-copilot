"""Nur die im aktuellen Lauf benutzten Textformen."""

import pytest

from synonym_matching.preprocessing import normalize, expanded, canonical, expand_modeling_abbreviations, text_veto


@pytest.mark.parametrize(('label', 'expected'), [
    ('GebäudeNr.', 'Gebäude Nummer'), ('Personalnr.', 'Personal Nummer'),
    ('customerNumber', 'customer Number'), ('Nachname\n Kunde', 'Nachname Kunde'),
    ('E-Mail', 'E-Mail'), ('Anz.', 'Anzahl'), ('BestellBez.', 'Bestell Bezeichnung'),
    ('Finanz', 'Finanz'), ('Bezirk', 'Bezirk'), ('PLZahl', 'PLZahl'),
])
def test_expansion(label, expected):
    assert expanded(label) == expected


def test_distinct_forms_do_not_destroy_semantic_spelling():
    assert normalize('Geba\u0308ude') == 'Gebäude'
    assert canonical('GebäudeNr.') == canonical('Gebaeudenummer')
    assert expanded('Gebäude') == 'Gebäude'
    assert expand_modeling_abbreviations('Experiment') == 'Experiment'
    assert text_veto('Raum 1', 'Raum 2') == 'digit_mismatch'
    assert text_veto('Vorname', 'Nachname') == 'start_mismatch'
