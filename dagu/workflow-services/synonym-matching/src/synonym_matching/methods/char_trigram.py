"""Jaccard similarity of character trigrams, including short-label behavior."""

from .pairwise import pairwise


def compute(left, right):
    grams = {}
    for text in left + right:
        if not text.strip() or text in grams:
            continue
        count = max(1, len(text) - 3 + 1)
        grams[text] = {text[index:index + 3] for index in range(count)}

    def similarity(first, second):
        return len(grams[first] & grams[second]) / len(grams[first] | grams[second])

    return pairwise(left, right, similarity)
