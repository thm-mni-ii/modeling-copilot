"""Keine Sprachannotation als Eingabe, konservatives Routing bei Unsicherheit."""

import numpy as np

from research.compare_lingua import LanguageDetection, route_features, odenet_first_routes


def matrices(shared=0, counter=0, known=1):
    return {k: np.array([[v]], dtype=float) for k, v in {
        'pair_known': known, 'shared_synset': shared, 'antonym': counter,
        'reference_hypernym': 0, 'reference_hyponym': 0,
        'reference_synset_count': known, 'student_synset_count': known}.items()}


def test_confident_routing_and_cross_language_unknown():
    sources = {'de': matrices(shared=1), 'en': matrices(counter=1)}
    values, conflict = route_features(sources, [{'language': 'de'}], [{'language': 'de'}])
    assert values['shared_synset'][0, 0] == 1
    assert not conflict.any()
    values, conflict = route_features(sources, [{'language': 'de'}], [{'language': 'en'}])
    assert all(not v.any() for v in values.values())
    assert not conflict.any()


def test_uncertain_uses_both_and_preserves_conflict():
    sources = {'de': matrices(shared=1), 'en': matrices(counter=1)}
    _, conflict = route_features(sources, [{'language': None}], [{'language': None}])
    assert conflict[0, 0]
    sources['en'] = matrices(known=0)
    values, conflict = route_features(sources, [{'language': None}], [{'language': None}])
    assert values['shared_synset'][0, 0] == 1
    assert not conflict.any()


def test_lingua_smoke_cache_and_empty_input():
    detector = LanguageDetection(.2)
    assert detector.detect('Das Gebäude besitzt mehrere Räume.')['language'] == 'de'
    assert detector.detect('The building contains several rooms.')['language'] == 'en'
    assert detector.detect('')['language'] is None
    first = detector.detect('Bank')
    assert detector.detect('Bank') is first
    assert set(first['confidence']) == {'de', 'en'}
    assert len(detector.cache) == 4


def test_odenet_first_keeps_german_evidence_despite_english_detection():
    sources = {'de': matrices(shared=1), 'en': matrices(counter=1)}
    routes = odenet_first_routes([{'language': 'en'}], [True])
    assert routes[0]['language'] == 'en'  # Erkennung und Quellenwahl getrennt.
    assert routes[0]['allowed_lexicons'] == ['de']
    values, conflict = route_features(sources, routes, routes)
    assert values['shared_synset'][0, 0] == 1
    assert not conflict.any()


def test_odenet_first_falls_back_only_to_confident_english():
    detections = [{'language': 'en'}, {'language': 'de'}, {'language': None}]
    assert [r['allowed_lexicons'] for r in odenet_first_routes(detections, [False] * 3)] == [['en'], [], []]
    sources = {'de': matrices(shared=1), 'en': matrices(shared=1)}
    unknown = odenet_first_routes([{'language': None}], [False])
    values, conflict = route_features(sources, unknown, unknown)
    assert all(not v.any() for v in values.values())
    assert not conflict.any()
