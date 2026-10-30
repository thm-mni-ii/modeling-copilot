"""Reuse features for unique labels within one engine; no files or database."""

import json


class Cache:
    """Speichert Ergebnisse nach Modellkonfiguration und Text im RAM."""
    def __init__(self):
        """Lege Speicher sowie Treffer- und Fehlzugriffszähler an."""
        self.memory = {}
        self.hits = 0
        self.misses = 0

    def get_many(self, namespace, texts, compute):
        """Berechne nur fehlende Texte und liefere Ergebnisse in Eingabereihenfolge."""
        namespace = json.dumps(namespace, sort_keys=True)
        unique = list(dict.fromkeys(texts))
        missing = [text for text in unique if (namespace, text) not in self.memory]
        self.hits += len(unique) - len(missing)
        self.misses += len(missing)
        if missing:
            values = compute(missing)
            if len(values) != len(missing):
                raise ValueError("backend returned the wrong number of values")
            for text, value in zip(missing, values, strict=True):
                self.memory[(namespace, text)] = value
        return [self.memory[(namespace, text)] for text in texts]
