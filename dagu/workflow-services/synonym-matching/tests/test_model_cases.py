"""Fixture contracts and diagnostic reporting, not assertions of semantic perfection."""
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def load(name):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_examples_match_graph_and_cover_all_requested_cases():
    original, generated, payload = load('build_model_cases').build()
    assert generated == json.loads((EXAMPLES / 'model-cases.json').read_text())
    assert payload == json.loads((EXAMPLES / 'order-management-input.json').read_text())
    assert {c['case_number'] for c in generated['cases']} == set(range(1, 35))
    before = ET.fromstring(original['model']['version']['data']['xml'])
    assert [c.get('id') for c in before.iter('Cell') if c.get('value')] == [
        e['id'] for e in payload['input']['referenceModel']['elements']]
    for case in generated['cases']:
        assert len(case['annotations']) == len(case['reference'])
        assert all(len(row) == len(case['student']) for row in case['annotations'])
        for side in ('reference', 'student'):
            assert len({x['id'] for x in case[side]}) == len(case[side])


def test_matrices_and_small_overview(tmp_path):
    data = json.loads((EXAMPLES / 'model-cases.json').read_text())
    out = tmp_path / 'matrices.json'
    assert load('check_model_cases').run(data, out) == []
    results = json.loads(out.read_text())
    assert {p.name for p in tmp_path.iterdir()} == {'matrices.json', 'matrices.md'}
    assert all(set(r) == {'variant', 'case', 'title', 'synonymMatrix'} for r in results)
    assert {r['case'] for r in results} == {c['id'] for c in data['cases']}
    bank = next(r for r in results if r['case'] == 'case-20')
    assert bank['synonymMatrix'][0]['matches'][0]['combinedScore'] == 1
    assert next(r for r in results if r['case'] == 'case-28-both-empty')['synonymMatrix'] == []
    assert 'case-20: Mehrdeutigkeit | 0/' in out.with_suffix('.md').read_text()


def test_spanish_translation_explicit_and_other_variants_continue(tmp_path, monkeypatch):
    runner = load('check_model_cases')
    class FakeEngine:
        def __init__(self, config):
            self.methods = config['methods']
        def match(self, refs, students):
            assert 'translated_embedding' not in self.methods
            return {'scores': {name: [[0.7]] for name in self.methods},
                    'processedLabels': {name: {'reference': ['Rechnung'], 'student': ['Factura']} for name in self.methods}}
    monkeypatch.setattr(runner, 'MatchingEngine', FakeEngine)
    data = json.loads((EXAMPLES / 'model-cases.json').read_text())
    data['cases'] = [c for c in data['cases'] if c['case_number'] == 11]
    out = tmp_path / 'matrices.json'
    assert runner.run(data, out, models=True) == []
    results = json.loads(out.read_text())
    translated = next(r for r in results if r['variant'] == 'translated_embedding')
    assert translated['synonymMatrix'] is None
    assert 'de/en' in translated['error']
    assert next(r for r in results if r['variant'] == 'multilingual')['synonymMatrix']
