"""Normalized edit similarity that counts an adjacent transposition as one edit."""

from rapidfuzz.distance import DamerauLevenshtein

from .pairwise import pairwise


def compute(left, right):
    return pairwise(left, right, DamerauLevenshtein.normalized_similarity)
