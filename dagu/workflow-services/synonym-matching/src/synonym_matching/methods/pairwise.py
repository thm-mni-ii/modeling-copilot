"""Apply a scalar string score to every reference/submission text pair."""

import numpy as np


def pairwise(left, right, score):
    matrix = np.zeros((len(left), len(right)))
    for row, reference_text in enumerate(left):
        for column, student_text in enumerate(right):
            if reference_text.strip() and student_text.strip():
                matrix[row, column] = score(reference_text, student_text)
    return matrix
