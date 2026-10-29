"""Methods return raw pairwise matrices; larger values always mean more similar."""
import time
from importlib.metadata import version

import numpy as np
from rapidfuzz.distance import DamerauLevenshtein, JaroWinkler, Levenshtein

from .preprocessing import Preprocessor
from .translation import Translator

def _pairwise(left, right, score):
    return np.array([[score(a, b) if a.strip() and b.strip() else 0.0
                      for b in right] for a in left], dtype=float).reshape(len(left), len(right))


def levenshtein(left, right):
    return _pairwise(left, right, Levenshtein.normalized_similarity)


def damerau_levenshtein(left, right):
    return _pairwise(left, right, DamerauLevenshtein.normalized_similarity)


def jaro_winkler(left, right):
    return _pairwise(left, right, JaroWinkler.normalized_similarity)


def char_ngram(left, right, n=3):
    if type(n) is not int or n < 1:
        raise ValueError("n must be a positive integer")
    grams = {text: {text[i:i+n] for i in range(max(1, len(text)-n+1))}
             for text in dict.fromkeys(left + right) if text.strip()}
    return _pairwise(left, right, lambda a, b: len(grams[a] & grams[b]) / len(grams[a] | grams[b]))


def char_bigram(left, right):
    return char_ngram(left, right, n=2)


def char_trigram(left, right):
    return char_ngram(left, right, n=3)


def multilingual_embedding(left, right, *, backend):
    """The backend only owns model loading and feature caching."""
    return backend.matrix(left, right)


def translated_embedding(left, right, *, backend):
    """Inputs are translated by the backend's batch preparation step."""
    return backend.matrix(left, right)


METHODS = {function.__name__: function for function in
           (levenshtein, damerau_levenshtein, jaro_winkler, char_bigram, char_trigram)}
DEFAULT_METHODS = list(METHODS)
METHODS.update(multilingual=multilingual_embedding, translated_embedding=translated_embedding)
EMBEDDING_MODELS = {
    "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "translated_embedding": "sentence-transformers/all-MiniLM-L6-v2",
}


class EmbeddingMethod:
    def __init__(self, name, config, cache):
        self.name, self.config, self.cache = name, config, cache
        self.model = None
        self.revision = None
        self.load_seconds = 0.0
        self.encode_seconds = 0.0
        self.translator = Translator(config, cache) if name == "translated_embedding" else None
        self.target_preprocessor = Preprocessor(config.get("target_preprocessing", {}))

    def prepare(self, texts, languages):
        if self.translator:
            texts = self.translator.translate(texts, languages)
            texts = [self.target_preprocessor.process(t, "en") for t in texts]
        return texts

    def _load(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            started = time.perf_counter()
            name = self.config.get("model", EMBEDDING_MODELS[self.name])
            revision = self.config.get("revision", "main")
            self.model = SentenceTransformer(name, revision=revision, device="cpu")
            self.revision = getattr(self.model[0].auto_model.config, "_commit_hash", None) or revision
            self.load_seconds = time.perf_counter() - started

    def _encode(self, texts):
        started = time.perf_counter()
        for text in texts:
            if len(self.model.tokenizer.encode(text)) > self.model.max_seq_length:
                raise ValueError("label exceeds embedding model token limit")
        values = self.model.encode(texts, batch_size=self.config.get("batch_size", 32),
                                   normalize_embeddings=True, show_progress_bar=False).tolist()
        self.encode_seconds += time.perf_counter() - started
        return values

    def matrix(self, left, right):
        texts = list(dict.fromkeys(t for t in left + right if t.strip()))
        if not left or not right or not texts:
            return np.zeros((len(left), len(right)))
        self._load()
        namespace = {"kind": "embedding-v1", "model": self.config.get("model", EMBEDDING_MODELS[self.name]),
                     "revision": self.revision, "normalize": True, "device": "cpu",
                     "sentence_transformers": version("sentence-transformers"), "torch": version("torch")}
        values = self.cache.get_many(namespace, texts, self._encode)
        mapping = dict(zip(texts, values, strict=True))
        zero = np.zeros(len(values[0]))
        a = np.array([mapping.get(t, zero) for t in left])
        b = np.array([mapping.get(t, zero) for t in right])
        return np.clip(a @ b.T, -1, 1)
