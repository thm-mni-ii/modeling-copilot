import copy
import csv
import json
from pathlib import Path
import numpy as np
import pytest
from synonym_matching.evaluation import validate_dataset, metrics, run

ROOT = Path(__file__).resolve().parents[1]


def dataset():
    return json.loads((ROOT / 'experiments/data/synthetic.json').read_text())


def test_dataset_and_leakage_guards():
    data = dataset()
    validate_dataset(data)
    for field in ['group', 'families']:
        broken = copy.deepcopy(data)
        broken['tasks'][-1][field] = broken['tasks'][0][field]
        with pytest.raises(ValueError, match='leakage'):
            validate_dataset(broken)
    broken = copy.deepcopy(data)
    broken['tasks'][-1]['reference'][0]['label'] = broken['tasks'][0]['reference'][0]['label']
    broken['tasks'][-1]['student'][0]['label'] = broken['tasks'][0]['student'][0]['label']
    with pytest.raises(ValueError, match='pair crosses'):
        validate_dataset(broken)


def test_top1_uses_full_candidates_and_no_match_rejection():
    records = [dict(task='t', reference_index=i, student_index=j, annotation=a)
               for i, row in enumerate([['incorrect', 'correct'], ['incorrect', 'incorrect']])
               for j, a in enumerate(row)]
    m = metrics(records, np.array([.9, .8, .2, .1]), .5)
    assert m['top1_accuracy'] == 0
    assert m['no_match_rejection'] == 1
    assert m['query_coverage'] == .5


def test_runner_persists_results_and_never_overwrites(tmp_path):
    suite = {'version': 1, 'variants': [{'name': 'one', 'config': {'methods': ['levenshtein']}}],
             'learned': ['logistic_regression', 'random_forest'], 'thresholds': [.3, .5, .8]}
    output = tmp_path / 'run'
    assert run(dataset(), suite, output) == []
    assert (output / 'summary.csv').exists()
    with (output / 'one/predictions.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert {'logistic_regression', 'random_forest'} <= {r['method'] for r in rows}
    assert not (output / 'one/logistic_regression.json').exists()
    assert not (output / 'one/random_forest.json').exists()
    with pytest.raises(FileExistsError):
        run(dataset(), suite, output)


@pytest.mark.parametrize('learner', ['logistic_regression', 'random_forest'])
def test_test_labels_cannot_change_predictions_or_threshold(tmp_path, learner):
    suite = {'version': 1, 'variants': [{'name': 'one', 'config': {'methods': ['levenshtein']}}],
             'learned': [learner], 'thresholds': [.2, .5, .8]}
    data = dataset()
    modified = copy.deepcopy(data)
    for task in modified['tasks']:
        if task['split'] == 'test':
            task['annotations'] = [['incorrect' if a == 'correct' else 'correct' if a == 'incorrect' else a for a in row] for row in task['annotations']]
    assert run(data, suite, tmp_path / 'a') == []
    assert run(modified, suite, tmp_path / 'b') == []
    a, b = tmp_path / 'a/one', tmp_path / 'b/one'
    assert (a / 'selected_thresholds.json').read_text() == (b / 'selected_thresholds.json').read_text()
    def predictions(directory):
        with (directory / 'predictions.csv').open() as stream:
            return [(r['task'], r['reference_index'], r['student_index'], r['score'])
                    for r in csv.DictReader(stream) if r['method'] == learner]
    assert predictions(a) == predictions(b)
