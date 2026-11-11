"""Pinned multilingual SentenceTransformer cosine scores using local resources."""

from copy import deepcopy
from pathlib import Path

import numpy as np


class MultilingualMethod:
    def __init__(self, config):
        self.config = config
        self.model = None
        self.revision = None

    def _load(self):
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.util import load_file_path

        name, revision = self.config["model"], self.config["revision"]
        modules = load_file_path(name, "modules.json", token=None, revision=revision, local_files_only=True)
        if modules is None:
            # SentenceTransformer would otherwise fall back to a different pooling pipeline.
            raise ValueError("required cached SentenceTransformer modules.json is unavailable")
        cached_revision = Path(modules).parent.name
        if cached_revision != revision:
            raise ValueError("cached multilingual resource does not match the pinned revision")
        self.model = SentenceTransformer(name, revision=revision, device="cpu", local_files_only=True)
        model_config = self.model[0].auto_model.config
        self.revision = getattr(model_config, "_commit_hash", None) or cached_revision
        if self.revision != revision:
            raise ValueError("loaded multilingual model does not match the pinned revision")

    def compute(self, left, right):
        if not left or not right:
            return np.zeros((len(left), len(right)))
        if self.model is None:
            self._load()
        # Reuse text features while keeping every element instance in the matrices.
        texts = list(dict.fromkeys(left + right))
        for text in texts:
            if len(self.model.tokenizer.encode(text)) > self.model.max_seq_length:
                raise ValueError("label exceeds embedding model token limit")
        vectors = self.model.encode(texts, batch_size=self.config["batch_size"],
                                    normalize_embeddings=True, show_progress_bar=False).tolist()
        mapping = dict(zip(texts, vectors, strict=True))
        reference_vectors = np.array([mapping[text] for text in left])
        student_vectors = np.array([mapping[text] for text in right])
        return np.clip(reference_vectors @ student_vectors.T, -1, 1)

    def resource_metadata(self):
        return {**deepcopy(self.config), "resolvedRevision": self.revision,
                "status": "used" if self.model is not None else "not_needed_no_usable_pairs",
                "maxSequenceLength": self.model.max_seq_length if self.model is not None else None}
