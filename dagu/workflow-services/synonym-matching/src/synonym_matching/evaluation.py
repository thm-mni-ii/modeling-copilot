"""Kleine Auswertung vollständig annotierter Kandidatenmengen, ohne Training."""

import numpy as np


def evaluate_case(case, scores, threshold=0.5, *, eligible=None, selected=None):
    """Zähle richtige/falsche Entscheidungen anhand ungerundeter Scores.

    TP: richtiger Treffer, FP: falscher Treffer, FN: übersehener Treffer,
    TN: richtig abgelehntes Paar. Für Top-1 zählen nur Referenzlabels mit
    mindestens einer korrekten Entsprechung. Leere Labels sind nie Kandidaten.
    """
    reference = case['reference']
    student = case['student']
    shape = (len(reference), len(student))
    values = np.asarray(scores, dtype=float).reshape(shape)
    annotations = case['annotations']
    if len(annotations) != shape[0]:
        raise ValueError('annotations must cover every reference/student pair')
    for row in annotations:
        if len(row) != shape[1]:
            raise ValueError('annotations must cover every reference/student pair')
        if any(label not in {'correct', 'incorrect'} for label in row):
            raise ValueError('diagnostic annotations must be correct or incorrect')

    valid = np.zeros(shape, dtype=bool)
    expected = np.zeros(shape, dtype=bool)
    for row, reference_element in enumerate(reference):
        for column, student_element in enumerate(student):
            valid[row, column] = bool(
                reference_element['label'].strip()
                and student_element['label'].strip()
            )
            expected[row, column] = annotations[row][column] == 'correct'
    if eligible is not None:
        valid &= np.asarray(eligible, dtype=bool).reshape(shape)

    predicted = (values >= threshold) & valid
    if selected is not None:
        # Zuordnungsverfahren filtern Entscheidungen, nicht die Top-1-Rangliste.
        predicted &= np.asarray(selected, dtype=bool).reshape(shape)
    true_positives = int((expected & predicted).sum())
    false_positives = int((~expected & predicted).sum())
    false_negatives = int((expected & ~predicted).sum())
    true_negatives = int((~expected & ~predicted).sum())

    queries = 0
    top1_correct = 0
    for row in range(shape[0]):
        if not expected[row].any():
            continue
        queries += 1
        candidates = np.flatnonzero(valid[row])
        if len(candidates):
            # np.argmax nimmt bei Gleichstand den ersten Kandidaten.
            winner = candidates[np.argmax(values[row, candidates])]
            top1_correct += int(expected[row, winner])
    return {
        'tp': true_positives,
        'fp': false_positives,
        'fn': false_negatives,
        'tn': true_negatives,
        'top1': top1_correct,
        'queries': queries,
        'pairs': int(values.size),
        'all_correct': false_positives == false_negatives == 0,
    }


def summarize(results):
    """Summiere Fallzahlen und berechne Precision, Recall und F1."""
    totals = {}
    for name in ('tp', 'fp', 'fn', 'tn', 'top1', 'queries', 'pairs'):
        totals[name] = sum(result[name] for result in results)

    true_positives = totals['tp']
    predicted_positives = true_positives + totals['fp']
    actual_positives = true_positives + totals['fn']
    f1_denominator = 2 * true_positives + totals['fp'] + totals['fn']

    # Bei fehlendem Nenner verwenden wir für die Übersicht den Wert 0.
    totals['precision'] = (
        true_positives / predicted_positives if predicted_positives else 0
    )
    totals['recall'] = (
        true_positives / actual_positives if actual_positives else 0
    )
    totals['f1'] = (
        2 * true_positives / f1_denominator if f1_denominator else 0
    )
    return totals
