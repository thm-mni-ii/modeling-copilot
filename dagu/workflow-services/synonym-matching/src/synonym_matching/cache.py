"""Reuse features for unique labels within one engine; no files or database."""
import json


class Cache:
    def __init__(self):
        self.memory = {}
        self.hits = 0
        self.misses = 0

    def get_many(self, namespace, texts, compute):
        namespace = json.dumps(namespace, sort_keys=True)
        unique = list(dict.fromkeys(texts))
        missing = [text for text in unique if (namespace, text) not in self.memory]
        self.hits += len(unique) - len(missing)
        self.misses += len(missing)
        if missing:
            values = compute(missing)
            if len(values) != len(missing):
                raise ValueError("backend returned the wrong number of values")
            self.memory.update({(namespace, text): value
                                for text, value in zip(missing, values, strict=True)})
        return [self.memory[(namespace, text)] for text in texts]
