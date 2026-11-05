"""Fixture contracts and diagnostic reporting, not assertions of semantic perfection."""
import os
import subprocess
import sys

import numpy as np

from research.build_model_cases import build
from research import compare as experiments
from research.compare import load_config
from tests.test_comparison import only
from synonym_matching import MatchingEngine
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'research'


def test_examples_match_graph_and_cover_all_requested_cases():
    original, generated, payload = build()
    assert generated == json.loads((EXAMPLES / 'model-cases.json').read_text())
    assert payload == json.loads((ROOT / 'examples/order-management-input.json').read_text())
    assert {c['case_number'] for c in generated['cases']} == set(range(1, 35))
    before = ET.fromstring(original['model']['version']['data']['xml'])
    assert [c.get('id') for c in before.iter('Cell') if c.get('value')] == [
        e['id'] for e in payload['input']['referenceModel']['elements']]
    for case in generated['cases']:
        assert len(case['annotations']) == len(case['reference'])
        assert all(len(row) == len(case['student']) for row in case['annotations'])
        for side in ('reference', 'student'):
            assert len({x['id'] for x in case[side]}) == len(case[side])


def test_single_research_command_writes_json_and_rankings(tmp_path):
    data = json.loads((EXAMPLES / 'model-cases.json').read_text())
    data['cases'] = [case for case in data['cases'] if case['case_number'] in (20, 28)]
    source = tmp_path / 'cases.json'
    source.write_text(json.dumps(data))
    config = only(load_config(), 'levenshtein', 'jaro_winkler', 'char_trigram', 'exact_match')
    config['preprocessing'] = {'normalize': ['normalize']}
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(config))
    output = tmp_path / 'results.json'
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    result = subprocess.run([sys.executable, '-m', 'research.compare', '--config', str(config_path),
        '--data', str(source), '--output', str(output)],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text())
    assert {p.name for p in tmp_path.iterdir()} == {'cases.json', 'config.json', 'results.json'}
    assert 'Top 3' in result.stdout
    assert 'threshold' in payload['rankings']
    assert {r['case'] for r in payload['records']} == {c['id'] for c in data['cases']}
    bank = next(r for r in payload['records']
                if r['case'] == 'case-20' and r['experiment'] == 'fixed/exact_match')
    assert bank['combinedScores'] == [[1.0]]
    assert bank['decisions']['threshold']['metrics']['fp'] == 1


def test_cases_with_other_languages_are_excluded_and_reported(tmp_path):
    data = json.loads((EXAMPLES / 'model-cases.json').read_text())
    data['cases'] = [c for c in data['cases'] if c['case_number'] in (1, 10, 11, 22)]
    config = only(load_config(), 'levenshtein')
    config['preprocessing'] = {'raw': []}
    out = tmp_path / 'run.json'
    experiments.run_experiments(data, out, config)
    run = json.loads(out.read_text())
    assert [c['id'] for c in run['dataset']['cases']] == ['case-01', 'case-10']
    assert run['excluded_cases'] == [{'case': 'case-11', 'languages': ['es']},
                                     {'case': 'case-22', 'languages': ['es']}]
    assert set(run['rankings']['threshold']['language_groups']) == {'de', 'de-en'}


def test_spanish_translation_explicit_and_other_variants_continue(tmp_path, monkeypatch):
    class FakeEmbeddingEngine(MatchingEngine):
        def compute_scores(self, refs, students):
            assert not set(self.methods) & {'translated_embedding', 'translated_string'}
            if 'multilingual' in self.methods:
                return {'scores': {'multilingual': np.array([[.7]])}, 'shape': [1, 1],
                        'validPairs': np.ones((1, 1), dtype=bool),
                        'usablePairs': {'multilingual': np.ones((1, 1), dtype=bool)},
                        'processedLabels': {'multilingual': {'reference': ['Rechnung'],
                                                            'student': ['Factura']}}}
            return super().compute_scores(refs, students)

    monkeypatch.setattr(experiments, 'MatchingEngine', FakeEmbeddingEngine)
    data = json.loads((EXAMPLES / 'model-cases.json').read_text())
    data['cases'] = [c for c in data['cases'] if c['case_number'] == 11]
    out = tmp_path / 'run.json'
    config = only(load_config(), 'levenshtein', 'multilingual', 'translated_embedding', 'translated_string')
    config['preprocessing'] = {'raw': []}
    config['languages'] = ['de', 'en', 'es']
    assert experiments.run_experiments(data, out, config) == []
    results = json.loads(out.read_text())['records']
    translated = next(r for r in results if r['experiment'] == 'fixed/translated_embedding')
    assert translated['status'] == 'unavailable'
    assert 'de/en' in translated['missing']['translated_embedding']['reason']
    assert next(r for r in results if r['experiment'] == 'fixed/multilingual')['status'] == 'ok'
