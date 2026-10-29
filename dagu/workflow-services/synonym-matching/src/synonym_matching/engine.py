"""Reference rows × student columns, with no forced one-to-one assignment."""
import math
import random
import time
import numpy as np
from .cache import Cache
from .combiners import combine
from .config import validate_config
from .methods import EmbeddingMethod, METHODS, EMBEDDING_MODELS
from .preprocessing import Preprocessor


def elements(values, prefix):
    if not isinstance(values, list):
        raise ValueError(f"{prefix} elements must be a list")
    result, ids = [], set()
    for index, value in enumerate(values):
        item = {"id": f"{prefix}:{index}", "label": value} if isinstance(value, str) else value
        if not isinstance(item, dict) or not isinstance(item.get("label"), str):
            raise ValueError("every element must have a string label")
        if type(item.get("id")) not in (str, int) or item["id"] == "":
            raise ValueError("element IDs must be nonempty strings or integers")
        key = (type(item["id"]), item["id"])
        if key in ids:
            raise ValueError(f"duplicate {prefix} ID: {item['id']}")
        ids.add(key)
        if "language" in item and (not isinstance(item["language"], str) or not item["language"]):
            raise ValueError("language must be a nonempty string")
        result.append({k: item[k] for k in ("id", "label", "language") if k in item})
    return result


class MatchingEngine:
    def __init__(self, config=None):
        self.config = validate_config(config)
        self.cache = Cache()
        self.string_preprocessor = Preprocessor(self.config["preprocessing"])
        self.embedding_preprocessor = Preprocessor(self.config["embedding_preprocessing"])
        self.methods = {name: METHODS[name] for name in self.config["methods"]}
        self.backends = {name: EmbeddingMethod(name, self.config["embedding"].get(name, {}), self.cache)
                         for name in self.methods if name in EMBEDDING_MODELS}
        random.seed(self.config["seed"])
        np.random.seed(self.config["seed"])

    def match(self, reference, student, *, threshold=None):
        if threshold is not None and (type(threshold) not in (float, int) or not math.isfinite(threshold) or not 0 <= threshold <= 1):
            raise ValueError("threshold must be null or a finite number in [0, 1]")
        started = time.perf_counter()
        reference, student = elements(reference, "reference"), elements(student, "student")
        all_elements = reference + student
        split = len(reference)
        matrices, details, timings, metadata = {}, {}, {}, {}
        hits, misses = self.cache.hits, self.cache.misses
        preprocessing_started = time.perf_counter()
        string_texts = [self.string_preprocessor.process(x["label"], x.get("language")) for x in all_elements]
        embedding_texts = None
        if any(n in EMBEDDING_MODELS for n in self.methods):
            embedding_texts = [self.embedding_preprocessor.process(x["label"], x.get("language")) for x in all_elements]
        timings["preprocessing_seconds"] = time.perf_counter() - preprocessing_started
        valid = np.array([bool(x["label"].strip()) for x in reference], dtype=bool)[:, None] & np.array([bool(x["label"].strip()) for x in student], dtype=bool)[None, :]
        for name, function in self.methods.items():
            method = self.backends.get(name)
            method_start = time.perf_counter()
            texts = string_texts
            if isinstance(method, EmbeddingMethod) and reference and student:
                texts = method.prepare(embedding_texts, [x.get("language") for x in all_elements])
            matrix = (function(texts[:split], texts[split:], backend=method) if method is not None
                      else function(texts[:split], texts[split:]))
            if matrix.shape != (len(reference), len(student)) or not np.isfinite(matrix).all():
                raise ValueError(f"invalid score matrix from {name}")
            matrix[~valid] = 0
            matrices[name] = matrix
            details[name] = {"reference": texts[:split], "student": texts[split:]}
            timings[name] = time.perf_counter() - method_start
            if isinstance(method, EmbeddingMethod):
                metadata[name] = {"model": method.config.get("model", EMBEDDING_MODELS[name]),
                                  "revision": method.revision, "load_seconds_cumulative": method.load_seconds,
                                  "encode_seconds_cumulative": method.encode_seconds}
                if method.translator:
                    metadata[name].update(translation_model=method.config.get("translation_model", "Helsinki-NLP/opus-mt-de-en"),
                                          translation_revision=method.translator.revision,
                                          translation_load_seconds_cumulative=method.translator.load_seconds,
                                          translation_seconds_cumulative=method.translator.compute_seconds)
        combine_start = time.perf_counter()
        combined = combine(matrices, self.config["combiner"])
        if combined.shape != valid.shape or not np.isfinite(combined).all():
            raise ValueError("combiner returned an invalid score matrix")
        combined = np.clip(combined, 0, 1)
        combined[~valid] = 0
        timings["combination_seconds"] = time.perf_counter() - combine_start
        candidates = []
        for i, ref in enumerate(reference):
            order = sorted(range(len(student)), key=lambda j: (-combined[i, j], j))
            eligible_order = [j for j in order if valid[i, j]]
            margin = float(combined[i, eligible_order[0]] - combined[i, eligible_order[1]]) if len(eligible_order) >= 2 else None
            matches = []
            for rank, j in enumerate(eligible_order, 1):
                if threshold is not None and combined[i, j] < threshold:
                    continue
                matches.append({"submissionElement": student[j], "scores": {n: float(m[i, j]) for n, m in matrices.items()},
                                "combinedScore": float(combined[i, j]), "rank": rank,
                                "mutualBest": bool(combined[i, j] == combined[i, eligible_order[0]] and combined[i, j] == combined[:, j].max())})
            candidates.append({"referenceElement": ref, "matches": matches, "top1Top2Margin": margin})
        timings["total_seconds"] = time.perf_counter() - started
        return {"referenceElements": reference, "studentElements": student,
                "shape": [len(reference), len(student)], "scores": {n: m.tolist() for n, m in matrices.items()},
                "combinedScores": combined.tolist(), "synonymMatrix": candidates,
                "processedLabels": details, "config": self.config, "threshold": threshold,
                "metadata": {"models": metadata, "timings": timings,
                             "cacheHits": self.cache.hits - hits, "cacheMisses": self.cache.misses - misses,
                             "scorePolicy": "raw cosine [-1,1]; combiners clip to [0,1]; empty labels score 0 and are not candidates"}}
