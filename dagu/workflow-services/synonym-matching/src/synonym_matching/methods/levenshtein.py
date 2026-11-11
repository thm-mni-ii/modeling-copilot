"""Normalized edit similarity, as used by the reference implementation."""

from rapidfuzz.distance import Levenshtein

from .pairwise import pairwise


def compute(left, right):
    return pairwise(left, right, Levenshtein.normalized_similarity)
