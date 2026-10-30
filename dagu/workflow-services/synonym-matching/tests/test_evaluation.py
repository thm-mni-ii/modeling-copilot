import numpy as np
import pytest
from synonym_matching.evaluation import evaluate_case, summarize


def test_pair_metrics_and_competing_candidates():
    case = {'reference': [{'label': 'Kunde'}, {'label': 'Rechnung'}],
            'student': [{'label': 'Lieferant'}, {'label': 'Customer'}],
            'annotations': [['incorrect', 'correct'], ['incorrect', 'incorrect']]}
    result = evaluate_case(case, [[.8, .9], [.1, .2]])
    assert result == dict(tp=1, fp=1, fn=0, tn=2, top1=1, queries=1, pairs=4, all_correct=False)
    assert summarize([result])['precision'] == .5
    assert summarize([result])['f1'] == pytest.approx(2 / 3)


def test_empty_labels_are_not_predictions_even_at_zero():
    case = {'reference': [{'label': ''}], 'student': [{'label': 'x'}], 'annotations': [['incorrect']]}
    assert evaluate_case(case, [[0]], threshold=0)['fp'] == 0
    assert evaluate_case({'reference': [], 'student': [], 'annotations': []}, np.zeros((0, 0)))['pairs'] == 0


def test_missing_annotations_rejected():
    with pytest.raises(ValueError, match='annotations'):
        evaluate_case({'reference': [{'label': 'a'}], 'student': [{'label': 'b'}], 'annotations': []}, [[1]])
