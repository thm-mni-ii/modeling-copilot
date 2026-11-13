"""Prüfe die optionale Konfliktheuristik, ohne Embeddingmodelle zu laden."""

import json
from pathlib import Path

import numpy as np
import pytest
import jsonschema

from synonym_matching import MatchingEngine
from synonym_matching.combinations import label_part_fusion
from synonym_matching.methods import label_part_compatibility


@pytest.mark.parametrize(('left', 'right', 'expected'), [
    ('Gebäude', 'GebäudeNr.', 0),
    ('GebäudeNr.', 'Gebäudenummer', 1),
    ('GebaeudeNr.', 'Building number', 1),
    ('Geräte Nummer', 'Raum Nummer', 0),
    ('GeräteNr.', 'Gerätenummer', 1),
    ('Geräte', 'Geräteraum', 0),
    ('equipment', 'equipment room', 0),
    ('Bestellnummer', 'Best.-Nr.', 1),
    ('XYZ Nummer', 'ABC Nummer', 1),  # Unbekannte Objekte begründen keinen Konflikt.
    ('Kunde', 'Lieferant', 1),  # Neutral heißt nicht synonym.
    ('', 'GebäudeNr.', 0),
])
def test_label_conflicts_are_symmetric(left, right, expected):
    assert label_part_compatibility([left], [right])[0, 0] == expected
    assert label_part_compatibility([right], [left])[0, 0] == expected


def test_conflict_fusion_only_reduces_detected_conflicts():
    scores = {'translated_embedding': np.array([[.8, .8, -.1]]),
              'label_part_compatibility': np.array([[0., 1., 1.]])}
    np.testing.assert_allclose(label_part_fusion(scores), [[.4, .8, 0.]])
    np.testing.assert_allclose(label_part_fusion(scores, penalty=0), [[.8, .8, 0.]])
    with pytest.raises(ValueError):
        label_part_fusion(scores, penalty=float('nan'))


def test_service_uses_original_labels_for_conflicts_and_keeps_schema(monkeypatch):
    from synonym_matching.methods import METHODS

    monkeypatch.setitem(METHODS, 'translated_embedding',
                        lambda left, right, backend: np.full((len(left), len(right)), .8))
    config = {'methods': ['translated_embedding', 'label_part_compatibility'],
              'preprocessing': ['stem'], 'embedding_preprocessing': ['normalize'],
              'combiner': {'kind': 'variant', 'name': 'label_part_fusion',
                           'options': {'penalty': .5}}}
    reference = [{'id': 'r', 'label': 'GebäudeNr.', 'language': 'de'}]
    student = [{'id': 's1', 'label': 'Gebäude', 'language': 'de'},
               {'id': 's2', 'label': 'Gebäudenummer', 'language': 'de'}]
    # Der Übersetzer wird im Test ersetzt; die Regel muss trotzdem die Originale sehen.
    engine = MatchingEngine(config)
    monkeypatch.setattr(engine.translator, 'translate', lambda texts, languages: ['same'] * len(texts))
    raw = engine.match(reference, student)
    assert raw['scores']['label_part_compatibility'] == [[0, 1]]
    assert raw['combinedScores'] == [[.4, .8]]
    public = {'synonymMatrix': raw['synonymMatrix']}
    root = Path(__file__).resolve().parents[1]
    jsonschema.validate(public, json.loads((root / 'schemas/output.schema.json').read_text()))
    assert public['synonymMatrix'][0]['matches'][0]['submissionElement']['id'] == 's2'
    assert label_part_compatibility([], ['x']).shape == (0, 1)

