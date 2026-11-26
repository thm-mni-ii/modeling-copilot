"""Modellkonventionen und Vergleichsauswertung ohne Gewichte testen."""

from types import SimpleNamespace

import numpy as np
import pytest

from research.compare_embeddings import evaluate
from research.experiments import configurations, load_config
from synonym_matching import MatchingEngine
from synonym_matching.cache import Cache
from synonym_matching.methods import EmbeddingMethod


@pytest.mark.parametrize(('name', 'prefix'), [('multilingual', ''), ('jina_de', ''), ('e5_base', 'query: ')])
def test_prefix_cache_empty_labels_and_method_registration(name, prefix, monkeypatch):
    calls = []

    def encode(texts, **kwargs):
        calls.append(texts)
        return np.array([[1., 0.] for _ in texts])

    def load(backend):
        backend.model = SimpleNamespace(tokenizer=SimpleNamespace(encode=lambda t: list(t)),
                                        max_seq_length=512, encode=encode)
        backend.revision = 'test-revision'

    monkeypatch.setattr(EmbeddingMethod, '_load', load)
    engine = MatchingEngine({'methods': [name]})
    first = engine.compute_scores(['Kunde', ''], ['Customer', 'Kunde'])
    second = engine.compute_scores(['Kunde'], ['Customer'])
    assert first['scores'][name].tolist() == [[1., 1.], [0., 0.]]
    assert second['scores'][name].tolist() == [[1.]]
    assert calls == [[prefix + 'Kunde', prefix + 'Customer']]
    assert first['shape'] == [2, 2]


def test_new_models_are_json_building_blocks():
    definitions, _ = configurations(load_config())
    for name in ('jina_de', 'e5_base'):
        assert f'normalize+split_identifiers → {name}' in definitions


def test_changed_labels_keep_all_competing_reference_candidates():
    case = {'reference': [{'id': 'r1', 'label': 'A'}, {'id': 'r2', 'label': 'B'}],
            'student': [{'id': 's1', 'label': 'A'}, {'id': 's2', 'label': 'Changed'}],
            'changed_student_ids': ['s2'],
            'annotations': [['correct', 'correct'], ['incorrect', 'incorrect']]}
    result = evaluate([case], [{'scores': [[1., .8], [.1, .9]]}], .85, changed=True)
    assert (result['tp'], result['fp'], result['fn']) == (0, 1, 1)
    assert result['queries'] == 1
    assert result['top1_accuracy'] == 0


def test_e5_prefix_counts_towards_token_limit():
    backend = EmbeddingMethod('e5_base', {}, Cache())
    backend.model = SimpleNamespace(tokenizer=SimpleNamespace(encode=lambda t: list(t)),
        max_seq_length=10, encode=lambda *a, **k: pytest.fail('must reject instead of truncate'))
    with pytest.raises(ValueError, match='token limit'):
        backend._encode(['123456'])  # query: zählt zum Tokenlimit.


def test_jina_pins_separate_architecture_repository(monkeypatch):
    import sys
    from synonym_matching.methods import EMBEDDING_REVISIONS, JINA_CODE_REVISION

    calls = []

    def load(name, **options):
        calls.append(options)
        return [SimpleNamespace(auto_model=SimpleNamespace(config=SimpleNamespace(_commit_hash='test')))]

    monkeypatch.setitem(sys.modules, 'sentence_transformers', SimpleNamespace(SentenceTransformer=load))
    EmbeddingMethod('jina_de', {}, Cache())._load()
    assert calls[0]['revision'] == EMBEDDING_REVISIONS['jina_de']
    assert calls[0]['model_kwargs']['code_revision'] == JINA_CODE_REVISION
    assert calls[0]['config_kwargs']['code_revision'] == JINA_CODE_REVISION
    assert calls[0]['trust_remote_code'] is True
