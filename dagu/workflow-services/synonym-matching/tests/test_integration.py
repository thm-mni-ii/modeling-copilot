"""Opt-in only: downloads model weights; never part of the offline test run."""
import os
import json
import subprocess
import sys
from pathlib import Path
import pytest
from synonym_matching import MatchingEngine

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get('RUN_MODEL_TESTS') != '1', reason='set RUN_MODEL_TESTS=1 to load real models')]


@pytest.mark.parametrize('method', ['multilingual', 'translated_embedding'])
def test_real_model_path(method):
    engine = MatchingEngine({'methods': [method]})
    refs = [{'id': 'r', 'label': 'Kunde', 'language': 'de'}]
    students = [{'id': 's', 'label': 'Customer', 'language': 'en'}]
    cold = engine.match(refs, students)
    misses = engine.cache.misses
    warm = engine.match(refs, students)
    assert cold['shape'] == [1, 1]
    assert engine.backends[method].revision
    assert -1 <= cold['scores'][method][0][0] <= 1
    assert warm['scores'] == cold['scores']
    assert engine.cache.misses == misses


def test_translate_step_with_real_translation_model():
    engine = MatchingEngine({'methods': ['levenshtein'],
                             'preprocessing': ['normalize', 'lowercase', 'translate']})
    result = engine.match([{'id': 'r', 'label': 'Kunde', 'language': 'de'}],
                          [{'id': 's', 'label': 'Customer', 'language': 'en'}])
    assert result['processedLabels']['levenshtein']['reference'][0] == 'customer'
    assert result['scores']['levenshtein'][0][0] == pytest.approx(1)
    assert engine.translator.revision


def test_default_pipeline_combines_strings_and_multilingual_embedding():
    result = MatchingEngine().match(['Kunde'], ['Customer', 'Kund', 'Lieferant'], threshold=.5)
    scores = result['scores']
    assert set(scores) == {'levenshtein', 'jaro_winkler', 'char_trigram', 'multilingual'}
    for column in range(3):
        string_score = sum(scores[name][0][column]
                           for name in ('levenshtein', 'jaro_winkler', 'char_trigram')) / 3
        embedding_score = max(0, scores['multilingual'][0][column])
        assert result['combinedScores'][0][column] == pytest.approx((string_score + embedding_score) / 2)
    labels = {match['submissionElement']['label'] for match in result['synonymMatrix'][0]['matches']}
    assert {'Customer', 'Kund'} <= labels


def test_default_cli_works_without_explicit_config():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / 'examples/input.json').read_text())
    assert 'config' not in payload['input']
    process = subprocess.run([sys.executable, str(root / 'src/main.py')],
                             input=json.dumps(payload), capture_output=True, text=True,
                             env={k: v for k, v in os.environ.items() if k != 'TEMPLATE_INPUT'})
    assert process.returncode == 0, process.stderr
    output = json.loads(process.stdout)
    assert set(output) == {'synonymMatrix'}
    customer = next(row for row in output['synonymMatrix'] if row['referenceElement']['id'] == 'r1')
    assert any(candidate['submissionElement']['id'] == 's1' for candidate in customer['matches'])
