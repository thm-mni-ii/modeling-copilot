"""Direkter Aufruf, IDs, vollständige Matrix, Schema und optionale echte Ressourcen."""

import json
import os
from pathlib import Path

import jsonschema
import pytest

from synonym_matching import MatchingPipeline

ROOT = Path(__file__).resolve().parents[1]


def test_metadata_duplicate_labels_and_language_independence(fake_pipeline):
    reference = [{'id':'r','label':'Kunde','type':'entity','language':'en'}]
    student = [{'id':'s1','label':'Kunde'}, {'id':'s2','label':'Kunde'}, {'id':'s3','label':''}]
    output = fake_pipeline.match(reference, student)
    jsonschema.validate(output, json.loads((ROOT/'schemas/output.schema.json').read_text()))
    row = output['synonymMatrix'][0]
    assert row['referenceElement'] == reference[0]
    assert [m['submissionElement']['id'] for m in row['matches']] == ['s1','s2','s3']
    assert row['matches'][0]['verdict'] == 'confirmed'
    assert row['matches'][2]['verdict'] == 'not_evaluable'
    assert 'combinedScore' not in row['matches'][0]


def test_empty_sets_and_duplicate_ids(fake_pipeline):
    assert fake_pipeline.match([], ['Kunde']) == {'synonymMatrix': []}
    assert fake_pipeline.match(['Kunde'], [])['synonymMatrix'][0]['matches'] == []
    with pytest.raises(ValueError, match='duplicate'):
        fake_pipeline.match([{'id':'r','label':'A'}, {'id':'r','label':'B'}], [])
    assert fake_pipeline.match([{'id':1,'label':'A'}, {'id':'1','label':'A'}], [])


@pytest.mark.parametrize('threshold', [True, float('nan'), -1, 2])
def test_invalid_thresholds(threshold):
    with pytest.raises(ValueError):
        MatchingPipeline(meaning_threshold=threshold)


def test_rounding_happens_after_decision(fake_pipeline):
    data = fake_pipeline.features(['Kunde'], ['Lieferant'])
    data['scores'][0][0].update(damerau_canonical=0., embedding_similarity=.84999999)
    item = fake_pipeline.from_features(data)['synonymMatrix'][0]['matches'][0]
    assert item['scores']['embedding_similarity'] == .85
    assert item['verdict'] == 'open'


def test_cli_empty_request_and_errors_without_resources():
    import subprocess
    import sys
    env = {k:v for k,v in os.environ.items() if k != 'TEMPLATE_INPUT'}
    payload = {'input': {'referenceModel': {'elements': []}, 'studentModel': {'elements': []}}}
    process = subprocess.run([sys.executable, 'src/main.py'], input=json.dumps(payload),
                             cwd=ROOT, env=env, text=True, capture_output=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {'synonymMatrix': []}
    invalid = subprocess.run([sys.executable, 'src/main.py'], input='{}', cwd=ROOT,
                             env=env, text=True, capture_output=True)
    assert invalid.returncode == 1 and invalid.stdout == ''
    assert 'ValidationError' in invalid.stderr


@pytest.mark.integration
@pytest.mark.skipif(os.getenv('RUN_MODEL_TESTS') != '1', reason='opt-in local model/lexicon test')
def test_real_pipeline_cli_and_warm_cache():
    import subprocess
    import sys
    pipeline = MatchingPipeline()
    first = pipeline.match(['Gebäude'], ['Building','Lieferant'])
    count = len(pipeline.embedding.vectors)
    assert first == pipeline.match(['Gebäude'], ['Building','Lieferant'])
    assert len(pipeline.embedding.vectors) == count
    assert first['synonymMatrix'][0]['matches'][0]['verdict'] == 'confirmed'
    process = subprocess.run([sys.executable, 'src/main.py', '--input', 'examples/input.json'],
                              cwd=ROOT, text=True, capture_output=True)
    assert process.returncode == 0, process.stderr
    jsonschema.validate(json.loads(process.stdout), json.loads((ROOT/'schemas/output.schema.json').read_text()))


@pytest.mark.integration
@pytest.mark.skipif(os.getenv('RUN_MODEL_TESTS') != '1', reason='opt-in real benchmark regression')
def test_real_frozen_cases_without_language_metadata():
    from research.compare import case_metrics
    from research.evaluation import summarize
    pipeline = MatchingPipeline()
    expected = json.loads((ROOT/'research/baseline-results.json').read_text())
    for name in ('laboratory', 'control', 'targeted'):
        dataset = json.loads((ROOT/'research/data'/f'{name}.json').read_text())
        changed = any(c.get('changed_student_ids') for c in dataset['cases'])
        totals = {str(t): [] for t in (.8, .85, .9)}
        for case in dataset['cases']:
            sides = [[{k:v for k,v in e.items() if k != 'language'} for e in case[side]]
                     for side in ('reference', 'student')]
            data = pipeline.features(*sides)
            for threshold in (.8, .85, .9):
                output = pipeline.from_features(data, meaning_threshold=threshold)
                m = case_metrics(case, data, output, changed=changed)
                if m is not None:
                    totals[str(threshold)].append(m)
        for threshold, values in totals.items():
            actual = summarize(values)
            before = expected['runs']['odenet_linked']['datasets'][name][threshold]
            assert {k: actual[k] for k in ('tp','fp','fn')} == {k:before[k] for k in ('tp','fp','fn')}
