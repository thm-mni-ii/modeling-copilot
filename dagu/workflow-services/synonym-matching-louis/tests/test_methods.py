"""Scorebereich, E5-Konvention und Wiederverwendung eindeutiger Labels."""

from types import SimpleNamespace

import numpy as np
import pytest

from synonym_matching.methods import SentenceEmbedding, damerau_matrix


def test_damerau_includes_transpositions_and_empty_axes():
    assert damerau_matrix(['Kunde'], ['Knude'])[0,0] == pytest.approx(.8)
    assert damerau_matrix([''], ['']).tolist() == [[0.]]
    assert damerau_matrix([], ['Kunde']).shape == (0,1)


@pytest.mark.parametrize(('name', 'prefix'), [('jina_de',''), ('multilingual',''), ('e5_base','query: ')])
def test_embedding_cache_and_prefix(name, prefix, monkeypatch):
    backend, calls = SentenceEmbedding(name), []
    def encode(texts, **kwargs):
        calls.append(texts)
        return np.array([[1., 0.] for _ in texts])
    backend.model = SimpleNamespace(tokenizer=SimpleNamespace(encode=lambda t: list(t)),
                                     max_seq_length=128, encode=encode)
    monkeypatch.setattr(backend, 'load', lambda **kwargs: None)
    assert backend.matrix(['Kunde',''], ['Customer','Kunde']).tolist() == [[1.,1.],[0.,0.]]
    backend.matrix(['Kunde'], ['Customer'])
    assert calls == [[prefix+'Kunde', prefix+'Customer']]
    backend.model.max_seq_length = 2
    with pytest.raises(ValueError, match='token limit'):
        backend.matrix(['Zu lang'], ['Customer'])


def test_empty_labels_do_not_load_resources(monkeypatch):
    backend = SentenceEmbedding()
    monkeypatch.setattr(backend, 'load', lambda **kwargs: pytest.fail('must not load'))
    assert backend.matrix([''], ['Kunde']).tolist() == [[0.]]


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError):
        SentenceEmbedding('missing')
