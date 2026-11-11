"""The reference's weighted string/embedding fusion; raw scores remain untouched."""

from copy import deepcopy

import numpy as np

STRING_METHODS = ("levenshtein", "jaro_winkler", "char_trigram")


def combine(scores, config):
    strings = np.stack([np.clip(scores[name], 0, 1) for name in STRING_METHODS]).mean(axis=0)
    embedding = np.clip(scores["multilingual"], 0, 1)
    weight = config["options"]["embedding_weight"]
    # Match the reference's np.average operation and its floating-point precision.
    return np.average(np.stack([strings, embedding]), axis=0, weights=[1 - weight, weight])


def describe(config):
    return {**deepcopy(config), "contributingMethods": list(STRING_METHODS) + ["multilingual"],
            "contributionTransform": "clip_each_score_to_[0,1]",
            "formula": "0.5 * mean(clip(levenshtein), clip(jaro_winkler), clip(char_trigram)) + 0.5 * clip(multilingual)",
            "scoreRange": [0, 1], "scoreMeaning": "similarity_not_probability"}
