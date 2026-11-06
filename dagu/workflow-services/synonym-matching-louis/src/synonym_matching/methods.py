"""Verfahren liefern paarweise Rohscores; größere Werte bedeuten höhere Ähnlichkeit."""

from importlib.metadata import version

import numpy as np
from rapidfuzz.distance import DamerauLevenshtein, JaroWinkler, Levenshtein, LCSseq
from rapidfuzz.fuzz import token_sort_ratio as _token_sort_ratio

from .preprocessing import Preprocessor
from .translation import Translator
from .combinations import string_ensemble


def _pairwise(left, right, score):
    """Wende eine Paarfunktion auf alle Referenz-/Schülerlabels an."""
    matrix = np.zeros((len(left), len(right)))
    for row, reference_text in enumerate(left):
        for column, student_text in enumerate(right):
            if reference_text.strip() and student_text.strip():
                matrix[row, column] = score(reference_text, student_text)
    return matrix


def levenshtein(left, right):
    """Vergleiche Einfügen, Löschen und Ersetzen von Zeichen."""
    return _pairwise(left, right, Levenshtein.normalized_similarity)


def damerau_levenshtein(left, right):
    """Berücksichtige zusätzlich das Vertauschen benachbarter Zeichen."""
    return _pairwise(left, right, DamerauLevenshtein.normalized_similarity)


def jaro_winkler(left, right):
    """Berechne Jaro-Winkler mit höherem Gewicht für gleiche Präfixe."""
    return _pairwise(left, right, JaroWinkler.normalized_similarity)


def char_ngram(left, right, n=3):
    """Vergleiche Mengen aus Zeichenfolgen der Länge n mit Jaccard."""
    if type(n) is not int or n < 1:
        raise ValueError("n must be a positive integer")
    grams = {}
    for text in left + right:
        if not text.strip() or text in grams:
            continue
        # Auch Labels mit weniger als n Zeichen bilden ein einziges n-Gramm.
        count = max(1, len(text) - n + 1)
        grams[text] = {text[index:index + n] for index in range(count)}

    def compare_grams(first, second):
        common = grams[first] & grams[second]
        all_grams = grams[first] | grams[second]
        return len(common) / len(all_grams)

    return _pairwise(left, right, compare_grams)


def char_bigram(left, right):
    """Vergleiche Zeichenfolgen der Länge zwei."""
    return char_ngram(left, right, n=2)


def char_trigram(left, right):
    """Vergleiche Zeichenfolgen der Länge drei."""
    return char_ngram(left, right, n=3)


def multilingual_embedding(left, right, *, backend):
    """Nutze das Backend für Modellladen und wiederverwendete Embeddings."""
    return backend.matrix(left, right)


def translated_embedding(left, right, *, backend):
    """Die Texte wurden bei der Vorbereitung bereits ins Englische übersetzt."""
    return backend.matrix(left, right)


def token_jaccard(left, right):
    """Vergleiche Wortmengen ohne Berücksichtigung der Reihenfolge."""
    def compare_tokens(first, second):
        first_tokens = set(first.split())
        second_tokens = set(second.split())
        common = first_tokens & second_tokens
        all_tokens = first_tokens | second_tokens
        return len(common) / len(all_tokens)

    return _pairwise(left, right, compare_tokens)


def token_sort_ratio(left, right):
    """Sortiere Wörter vor dem Stringvergleich; skaliere auf [0, 1]."""
    return _pairwise(left, right, lambda a, b: _token_sort_ratio(a, b, processor=None) / 100)


def word_order(left, right):
    """Vergleiche die längste gemeinsame Teilfolge von Wörtern."""
    return _pairwise(left, right, lambda a, b: LCSseq.normalized_similarity(a.split(), b.split()))


def exact_match(left, right):
    """Liefere 1 nur für identische, nichtleere Texte."""
    return _pairwise(left, right, lambda a, b: float(a == b))


def translated_string(left, right):
    """Mittle String-Scores für die bereits ins Englische übersetzten Texte."""
    return string_ensemble({
        'levenshtein': levenshtein(left, right),
        'jaro_winkler': jaro_winkler(left, right),
        'char_trigram': char_trigram(left, right),
    })


def wordnet(left, right, *, backend):
    """Prüfe gemeinsame englische WordNet-Synsets nach der Übersetzung."""
    return backend.matrix(left, right)


def openthesaurus(left, right, *, backend):
    """Prüfe gemeinsame deutsche Synonymgruppen ohne Übersetzung."""
    return backend.matrix(left, right)


# Diese Namen werden auch in der JSON-Konfiguration verwendet.
METHODS = {
    'levenshtein': levenshtein,
    'damerau_levenshtein': damerau_levenshtein,
    'jaro_winkler': jaro_winkler,
    'char_bigram': char_bigram,
    'char_trigram': char_trigram,
    'token_jaccard': token_jaccard,
    'token_sort_ratio': token_sort_ratio,
    'word_order': word_order,
    'exact_match': exact_match,
    'translated_string': translated_string,
    'wordnet': wordnet,
    'openthesaurus': openthesaurus,
    'multilingual': multilingual_embedding,
    'translated_embedding': translated_embedding,
}
# Was die Engine für ein Verfahren vorbereitet, statt Namensabfragen in der Engine:
# translate = Texte vorher DE→EN übersetzen, german_only = Sprache de verlangen,
# original_text = nur normalisierten Originaltext verwenden (Preprocessing ignorieren).
METHOD_TRAITS = {
    'translated_string': {'translate'},
    'wordnet': {'translate'},
    'openthesaurus': {'german_only'},
    'exact_match': {'original_text'},
}
# Die bisherige String-Baseline bleibt ausdrücklich auswählbar.
STRING_BASELINES = [
    'levenshtein', 'damerau_levenshtein', 'jaro_winkler',
    'char_bigram', 'char_trigram',
]
EMBEDDING_MODELS = {
    "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "translated_embedding": "sentence-transformers/all-MiniLM-L6-v2",
}
# Feste Commits der Standardmodelle; bei eigenem "model" gilt weiter "main".
EMBEDDING_REVISIONS = {
    "multilingual": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    "translated_embedding": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
}


class EmbeddingMethod:
    """Verwaltet ein Sentence-Embedding-Modell und dessen Featurecache."""
    def __init__(self, name, config, cache):
        """Merke Modellkonfiguration und Cache; lade noch keine Gewichte."""
        self.name = name
        self.config = config
        self.cache = cache
        self.model = None
        self.revision = None
        self.translator = Translator(config, cache) if name == "translated_embedding" else None
        self.target_preprocessor = Preprocessor(config.get("target_preprocessing", {}))

    def prepare(self, texts, languages):
        """Übersetze bei Bedarf und wende das Ziel-Preprocessing an."""
        if self.translator:
            texts = self.translator.translate(texts, languages)
            texts = [self.target_preprocessor.process(t, "en") for t in texts]
        return texts

    def _load(self):
        """Lade das Modell einmalig auf der CPU."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            name = self.config.get("model", EMBEDDING_MODELS[self.name])
            default = "main" if "model" in self.config else EMBEDDING_REVISIONS[self.name]
            revision = self.config.get("revision", default)
            self.model = SentenceTransformer(name, revision=revision, device="cpu")
            model_config = self.model[0].auto_model.config
            self.revision = getattr(model_config, "_commit_hash", None) or revision

    def _encode(self, texts):
        """Berechne normierte Vektoren für einen Stapel unbekannter Labels."""
        for text in texts:
            if len(self.model.tokenizer.encode(text)) > self.model.max_seq_length:
                raise ValueError("label exceeds embedding model token limit")
        values = self.model.encode(texts, batch_size=self.config.get("batch_size", 32),
                                   normalize_embeddings=True, show_progress_bar=False).tolist()
        return values

    def matrix(self, left, right):
        """Berechne paarweise Cosinus-Scores aus wiederverwendeten Vektoren."""
        texts = list(dict.fromkeys(t for t in left + right if t.strip()))
        if not left or not right or not texts:
            return np.zeros((len(left), len(right)))
        self._load()
        namespace = {
            "kind": "embedding-v1",
            "model": self.config.get("model", EMBEDDING_MODELS[self.name]),
            "revision": self.revision,
            "normalize": True,
            "device": "cpu",
            "sentence_transformers": version("sentence-transformers"),
            "torch": version("torch"),
        }
        values = self.cache.get_many(namespace, texts, self._encode)
        mapping = dict(zip(texts, values, strict=True))
        zero = np.zeros(len(values[0]))
        reference_vectors = np.array([mapping.get(text, zero) for text in left])
        student_vectors = np.array([mapping.get(text, zero) for text in right])
        # Bei normierten Vektoren entspricht das Skalarprodukt dem Cosinus.
        similarities = reference_vectors @ student_vectors.T
        return np.clip(similarities, -1, 1)
