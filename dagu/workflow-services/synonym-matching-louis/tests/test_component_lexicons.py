"""Kontrollierter Lexikonvergleich ohne Änderungen an S/E oder Fusion."""

from copy import deepcopy
import json

import numpy as np
import pytest

from research.compare_component_lexicons import LexiconSources, combine_sources


def profile(identifier):
    return {'synsets': {identifier} if identifier else set(), 'nodes': [],
            'ancestors': set(), 'antonym_synsets': set(),
            'senses': set(), 'antonym_senses': set()}


def test_native_cross_language_is_unknown_not_negative():
    sources = LexiconSources()
    sources.profile = lambda element, linked=False: profile(element['label'])
    reference = [{'label': 'same', 'language': 'de'}]
    student = [{'label': 'same', 'language': 'en'}, {'label': 'same', 'language': 'de'}]
    shared, values, comparable = sources.matrices(reference, student)
    assert shared.tolist() == [[0, 1]]
    assert values['pair_known'].tolist() == [[0, 1]]
    assert comparable.tolist() == [[0, 1]]
    assert values['reference_synset_count'].tolist() == [[1, 1]]


def test_ili_link_loss_is_not_negative_evidence_and_keeps_source_ambiguity():
    sources = LexiconSources()

    def lookup(element, linked=False):
        if linked:
            return profile(None)
        original = profile('de-first')
        original['synsets'].add('de-second')
        return original

    sources.profile = lookup
    elements = [{'label': 'Fachbegriff', 'language': 'de'}]
    shared, values, _ = sources.matrices(elements, elements, linked=True)
    assert shared[0, 0] == values['pair_known'][0, 0] == 0
    assert values['reference_synset_count'][0, 0] == 2


def test_conflicting_sources_abstain_without_changing_similarity():
    first = {name: np.zeros((1, 1)) for name in (
        'string_similarity', 'embedding_similarity', 'lexicon_coverage',
        'shared_synset_fraction', 'shared_synset', 'full_synonym_evidence',
        'antonym_relation', 'hypernym_relation', 'hyponym_relation',
        'antonym_evidence', 'hierarchy_evidence')}
    first['string_similarity'][:] = .7
    first['embedding_similarity'][:] = .8
    first['lexicon_coverage'][:] = first['shared_synset_fraction'][:] = 1
    first['full_synonym_evidence'][:] = 1
    second = deepcopy(first)
    second['shared_synset_fraction'][:] = second['full_synonym_evidence'][:] = 0
    second['antonym_relation'][:] = second['antonym_evidence'][:] = 1
    merged, conflict = combine_sources(first, second)
    assert conflict[0, 0]
    assert merged['lexicon_coverage'][0, 0] == merged['antonym_evidence'][0, 0] == 0
    assert merged['full_synonym_evidence'][0, 0] == 0
    assert merged['string_similarity'][0, 0] == .7
    assert merged['embedding_similarity'][0, 0] == .8
    assert first['lexicon_coverage'][0, 0] == 1


def test_saved_feature_comparison_keeps_alignment_and_baseline(tmp_path, monkeypatch):
    from research import compare_component_lexicons as module
    from research.experiments import load_config
    from synonym_matching.component_evidence import ComponentEvidence
    from synonym_matching.combinations import SEMANTIC_FEATURES

    element = {'id': 'x', 'label': 'Kunde', 'language': 'de'}
    scores = {name: np.ones((1, 1)) for name in
              ('levenshtein', 'jaro_winkler', 'char_trigram', 'translated_embedding', 'wordnet')}
    relations = {name: np.ones((1, 1)) if name in
                 {'pair_known', 'reference_synset_count', 'student_synset_count'} else np.zeros((1, 1))
                 for name in SEMANTIC_FEATURES}
    aggregator = ComponentEvidence.__new__(ComponentEvidence)
    aggregator.aggregate({'scores': scores, 'semantic_features': {'wordnet': relations}},
                         [[element], [element]], [[[0]], [[0]]], [element], [element])
    config = load_config()
    source = tmp_path / 'saved.json'
    source.write_text(json.dumps({'seed': 42, 'threshold': .5,
        'dataset': {'cases': [{'id': 'case', 'case_number': 1, 'title': 'Test',
                              'reference': [element], 'student': [element],
                              'changed_student_ids': ['x'], 'annotations': [['correct']]}]},
        'features': [{'chain': ['normalize', 'component_evidence'], 'case': 'case',
                      'status': 'ok', 'eligible': [[True]],
                      'component_features': {k: v.tolist() for k, v in aggregator.features.items()},
                      'component_evidence': aggregator.evidence}]}))
    monkeypatch.setattr(LexiconSources, 'profile',
                        lambda self, element, linked=False: profile('same'))
    output = tmp_path / 'comparison.json'
    result = module.run_comparison(source, output, config)
    assert len(result['records']) == 4
    assert result['changed_labels']['native']['tp'] == 1
    assert all(record['features']['embedding_similarity'] == [[1.]] for record in result['records'])
    assert result['component_diagnostics'][0]['component_evidence']['alignments'] == [[[[0, 0]]]]
    with pytest.raises(FileExistsError):
        module.run_comparison(source, output, config)
