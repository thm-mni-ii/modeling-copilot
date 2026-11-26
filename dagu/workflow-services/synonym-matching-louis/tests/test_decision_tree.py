"""Entscheidungsreihenfolge und fachliche Enthaltung statt erfundener Evidenz."""

import pytest

from synonym_matching.decision import decide


def features(**changes):
    return {'pair_known': 1, 'shared_synset': 0, 'reference_synset_count': 1,
        'student_synset_count': 1, 'antonym': 0, 'reference_hypernym': 0,
        'reference_hyponym': 0, 'damerau_canonical': .2, 'embedding_similarity': .2, **changes}


@pytest.mark.parametrize('relation', ['antonym','reference_hypernym','reference_hyponym'])
def test_counterrelation_and_ambiguity(relation):
    assert decide(features(**{relation:1}), 'Kunde', 'Lieferant')[0] == 'rejected'
    assert decide(features(**{relation:1, 'student_synset_count':2}), 'Kunde', 'Lieferant')[0] == 'open'
    assert decide(features(**{relation:1, 'shared_synset':1}), 'Kunde', 'Abnehmer')[0] == 'confirmed'


def test_missing_coverage_and_taxonomy_are_not_synonym_proof():
    assert decide(features(pair_known=0, embedding_similarity=.9), 'Raum', 'Room') == ('confirmed','meaning')
    assert decide(features(path_similarity=1., wup_similarity=1.), 'Kunde', 'Lieferant')[0] == 'open'
    assert decide(features(shared_synset=1, student_synset_count=10), 'Kunde', 'Abnehmer')[0] == 'confirmed'
    assert decide(features(shared_synset=1), '', 'Kunde')[0] == 'not_evaluable'


def test_string_guards_thresholds_and_optional_exact_priority():
    assert decide(features(damerau_canonical=.9), 'Bestellung', 'Bestelung')[1] == 'spelling'
    assert decide(features(damerau_canonical=.99), 'Vorname', 'Nachname')[0] == 'open'
    assert decide(features(embedding_similarity=.99), 'Raum 1', 'Raum 2')[1] == 'digit_mismatch'
    f = features(embedding_similarity=.84)
    assert decide(f, 'Raum', 'Room', meaning_threshold=.8)[0] == 'confirmed'
    assert decide(f, 'Raum', 'Room', meaning_threshold=.85)[0] == 'open'
    assert decide(features(antonym=1), ' Kunde ', 'kunde', exact_first=True)[1] == 'normalized_exact'
    assert decide(features(antonym=1), 'Gebäude', 'Gebaeude', exact_first=True)[0] == 'rejected'
