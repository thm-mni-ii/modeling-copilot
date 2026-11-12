"""Jaro-Winkler similarity, including the reference's default prefix weighting."""

from rapidfuzz.distance import JaroWinkler

from .pairwise import pairwise


def compute(left, right):
    return pairwise(left, right, JaroWinkler.normalized_similarity)
