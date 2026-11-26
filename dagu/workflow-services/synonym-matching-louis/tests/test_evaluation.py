"""Kandidatenmengen, falsche Treffer und Rohscore-Top-1 korrekt auswerten."""

import json
from pathlib import Path

import numpy as np

from research.compare import case_metrics
from research.evaluation import evaluate_case, summarize


def test_changed_students_keep_all_competing_references():
    case = {'reference': [{'id':'r1','label':'A'},{'id':'r2','label':'B'}],
            'student': [{'id':'s1','label':'A'},{'id':'s2','label':'Changed'}],
            'changed_student_ids':['s2'], 'annotations':[['correct','correct'],['incorrect','incorrect']]}
    data = {'scores': [[{'embedding_similarity':1.},{'embedding_similarity':.8}],
                       [{'embedding_similarity':.1},{'embedding_similarity':.9}]]}
    output = {'synonymMatrix':[{'matches':[{'verdict':'confirmed'},{'verdict':'open'}]},
                              {'matches':[{'verdict':'open'},{'verdict':'confirmed'}]}]}
    metrics = case_metrics(case, data, output, changed=True)
    assert (metrics['tp'],metrics['fp'],metrics['fn']) == (0,1,1)
    assert (metrics['top1'],metrics['queries']) == (0,1)


def test_empty_axes_and_invalid_labels_do_not_generate_matches():
    case = {'reference':[{'label':''}], 'student':[{'label':'Kunde'}], 'annotations':[['incorrect']]}
    assert evaluate_case(case, np.array([[1.]]))['fp'] == 0
    assert summarize([])['f1'] == 0


def test_frozen_datasets_have_full_annotations_and_provenance():
    root = Path(__file__).resolve().parents[1]/'research/data'
    for path in root.glob('*.json'):
        data = json.loads(path.read_text())
        for case in data['cases']:
            assert len(case['annotations']) == len(case['reference'])
            assert all(len(row) == len(case['student']) for row in case['annotations'])
    laboratory = json.loads((root/'laboratory.json').read_text())
    assert len(laboratory['cases']) == 5
    assert laboratory['provenance']['source_sha256']


def test_research_launcher_isolates_old_packages_and_returns_errors():
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    launcher = root/'scripts/run_experiments.py'
    process = subprocess.run([sys.executable, str(launcher), 'compare', '--help'],
                             cwd=root, text=True, capture_output=True)
    assert process.returncode == 0, process.stderr
    # Der bisherige Baukasten hat --data, der neue Direktvergleich nicht.
    assert '--data' in process.stdout
    invalid = subprocess.run([sys.executable, str(launcher), 'compare', '--unknown-option'],
                             cwd=root, text=True, capture_output=True)
    assert invalid.returncode != 0
