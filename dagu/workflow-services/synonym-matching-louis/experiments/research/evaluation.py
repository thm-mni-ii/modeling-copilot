"""Kleine Auswertung vollständig annotierter Kandidatenmengen, ohne Training."""

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.stats import rankdata

from synonym_matching.service import nonempty_pairs


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

    valid = nonempty_pairs([element['label'] for element in reference],
                           [element['label'] for element in student])
    expected = np.asarray(annotations, dtype=str).reshape(shape) == 'correct'
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


def select_matches(scores, eligible, threshold=0.5, strategy='threshold'):
    """Liefere eine boolesche Auswahlmatrix aus ungerundeten Scores.

    Mutual Best behält alle Gleichstände (also nicht zwingend 1:1).
    Hungarian maximiert die Summe gültiger Scores mit Dummy-Spalten für
    Nichtzuordnung. Unzulässige Kanten werden VOR der Optimierung gesperrt.
    """
    scores = np.asarray(scores, dtype=float)
    eligible = np.asarray(eligible, dtype=bool)
    if scores.ndim != 2 or eligible.shape != scores.shape:
        raise ValueError('scores and eligible must have the same matrix shape')
    if not np.isfinite(scores).all() or not 0 <= threshold <= 1:
        raise ValueError('finite scores and threshold in [0,1] required')
    allowed = eligible & (scores >= threshold)
    if strategy not in {'threshold', 'mutual_best', 'hungarian'}:
        raise ValueError('unknown assignment strategy')
    if strategy == 'threshold' or not scores.size:
        return allowed
    if strategy == 'mutual_best':
        usable_scores = np.where(eligible, scores, -np.inf)
        row_best = usable_scores.max(axis=1, keepdims=True)
        column_best = usable_scores.max(axis=0, keepdims=True)
        return allowed & (scores == row_best) & (scores == column_best)

    rows, columns = scores.shape
    # Bei Score 0 besteht keine positive Evidenz: Dummy statt Zufallstreffer.
    allowed &= scores > 0
    weights = np.zeros((rows, columns + rows))
    weights[:, :columns] = np.where(allowed, scores, -1.0)
    row_indices, column_indices = linear_sum_assignment(weights, maximize=True)
    chosen = np.zeros(scores.shape, dtype=bool)
    for row, column in zip(row_indices, column_indices):
        if column < columns and allowed[row, column]:
            chosen[row, column] = True
    return chosen


def global_ranking(scores, eligible):
    """Eigene Rangheuristik: senke Scores entsprechend Zeilen- und Spaltenrang ab.

    Gleichstände erhalten mittlere Ränge. Beide Ränge 1 erhalten den Originalscore;
    schwächere Kandidaten werden mit 2/(Zeilenrang+Spaltenrang) gewichtet.
    Das ist keine zusätzliche 1:1-Zuordnung und keine übernommene Paper-Formel.
    """
    if not scores.size:
        return scores.copy()
    usable = np.where(eligible, scores, -np.inf)
    row_rank = rankdata(-usable, axis=1, method='average')
    column_rank = rankdata(-usable, axis=0, method='average')
    return np.where(eligible, scores * 2 / (row_rank + column_rank), 0)
