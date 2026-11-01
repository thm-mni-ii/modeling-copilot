"""Experimentelle Zuordnungen; die Service-Matrix bleibt unverändert."""

import numpy as np
from scipy.optimize import linear_sum_assignment


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
