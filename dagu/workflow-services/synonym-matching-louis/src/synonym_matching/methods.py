"""Damerau-Levenshtein und austauschbare Sentence-Embeddings mit Labelcache."""

import numpy as np
from rapidfuzz.distance import DamerauLevenshtein

MODELS = {
    'jina_de': ('jinaai/jina-embeddings-v2-base-de', '3f9eede875721714945b6a99a3198299243cf2be'),
    'multilingual': ('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'),
    'e5_base': ('intfloat/multilingual-e5-base', 'd128750597153bb5987e10b1c3493a34e5a4502a'),
}
JINA_CODE_REVISION = 'f3ec4cf7de7e561007f27c9efc7148b0bd713f81'


def damerau_matrix(left, right):
    """Normierte Schreibähnlichkeit für jedes nichtleere Labelpaar."""
    values = np.zeros((len(left), len(right)))
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            if a and b:
                values[i, j] = DamerauLevenshtein.normalized_similarity(a, b)
    return values


class SentenceEmbedding:
    """Ein CPU-Modell pro Instanz; jedes eindeutige Label nur einmal kodieren."""

    def __init__(self, name='jina_de', batch_size=32):
        if name not in MODELS:
            raise ValueError(f'unknown embedding model: {name}')
        self.name, self.batch_size = name, batch_size
        self.model = None
        self.vectors = {}

    def load(self, *, allow_download=False):
        """Matching ist offline. Nur das Vorbereitungsskript darf herunterladen."""
        if self.model is not None:
            return
        from sentence_transformers import SentenceTransformer
        model, revision = MODELS[self.name]
        options = {}
        if self.name == 'jina_de':
            options = {'trust_remote_code': True,
                       'model_kwargs': {'code_revision': JINA_CODE_REVISION},
                       'config_kwargs': {'code_revision': JINA_CODE_REVISION}}
        self.model = SentenceTransformer(model, revision=revision, device='cpu',
                                         local_files_only=not allow_download, **options)
        resolved = getattr(self.model[0].auto_model.config, '_commit_hash', None)
        if resolved is not None and resolved != revision:
            raise ValueError('loaded model does not match pinned revision')

    def matrix(self, left, right):
        """Normierte Vektoren liefern rohe Cosinuswerte in [-1,1]."""
        shape = (len(left), len(right))
        if not all(shape) or not any(t.strip() for t in left) or not any(t.strip() for t in right):
            return np.zeros(shape)
        missing = list(dict.fromkeys(t for t in left + right if t.strip() and t not in self.vectors))
        if missing:
            self.load()
            texts = ['query: ' + t for t in missing] if self.name == 'e5_base' else missing
            if any(len(self.model.tokenizer.encode(t)) > self.model.max_seq_length for t in texts):
                raise ValueError('label exceeds embedding model token limit')
            values = self.model.encode(texts, batch_size=self.batch_size,
                                       normalize_embeddings=True, show_progress_bar=False)
            self.vectors.update(zip(missing, values, strict=True))
        zero = np.zeros(len(next(iter(self.vectors.values()))))
        a = np.asarray([self.vectors.get(t, zero) for t in left])
        b = np.asarray([self.vectors.get(t, zero) for t in right])
        return np.clip(a @ b.T, -1, 1)

    def metadata(self):
        model, revision = MODELS[self.name]
        return {'model': model, 'revision': revision, 'device': 'cpu',
                'code_revision': JINA_CODE_REVISION if self.name == 'jina_de' else None}
