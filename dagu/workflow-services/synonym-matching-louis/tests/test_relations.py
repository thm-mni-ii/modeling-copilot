"""Relationsmerkmale sind Evidenz, keine zusätzlichen Synonymentscheidungen."""

import json
import os
from types import SimpleNamespace

import pytest

from research.compare import run_experiments
from research.experiments import load_config
from synonym_matching.methods import wn_translation
from synonym_matching.lexicons import OdeNet, RELATION_FEATURES, WordNet

BASIC_FEATURES = RELATION_FEATURES[:6]


@pytest.fixture
def lexicon():
    class Node:
        def __init__(self, identifier, parents=()):
            self.id, self.parents = identifier, parents

        def closure(self, *relations):
            ancestors = {'car': ['vehicle'], 'sedan': ['car', 'vehicle']}
            return iter(nodes[name] for name in ancestors.get(self.id, []))

        def relations(self, *names):
            return {}

    nodes = {name: Node(name, parents) for name, parents in {
        'vehicle': (), 'car': ('vehicle',), 'sedan': ('car',),
        'hot': (), 'cold': (), 'customer': ()}.items()}
    senses = {name: SimpleNamespace(id=name, relations=lambda *args: {})
              for name in ('hot', 'warm', 'cold')}
    senses['hot'].relations = lambda *args: {'antonym': [senses['cold']]}

    class Reader:
        calls = 0

        def synsets(self, text, pos=None):
            ids = {'client': ['customer'], 'warm': ['hot'],
                   'ambiguous': ['hot', 'cold']}.get(text, [text])
            return [nodes[name] for name in ids if name in nodes]

        def synset(self, identifier):
            self.calls += 1
            return nodes[identifier]

        def senses(self, text, pos=None):
            return [senses[text]] if text in senses else []

    result = WordNet()
    result.reader = Reader()
    return result


def test_relation_direction_and_native_closure_cache(lexicon):
    result = lexicon.relation_features(['vehicle'], ['sedan'], BASIC_FEATURES)
    assert result['reference_hypernym'].tolist() == [[1]]
    assert result['reference_hyponym'].tolist() == [[0]]
    reverse = lexicon.relation_features(['sedan'], ['vehicle'], BASIC_FEATURES)
    assert reverse['reference_hyponym'].tolist() == [[1]]
    assert lexicon.matrix(['vehicle'], ['sedan']).tolist() == [[0]]
    calls = lexicon.reader.calls
    lexicon.relation_features(['vehicle'], ['sedan'], BASIC_FEATURES)
    assert lexicon.reader.calls == calls


def test_antonyms_use_actual_word_senses_and_are_symmetric(lexicon):
    result = lexicon.relation_features(['hot', 'warm', 'cold'], ['cold', 'hot'], ['antonym'])
    assert result['antonym'].tolist() == [[1, 0], [0, 0], [0, 1]]
    assert lexicon.matrix(['hot'], ['warm']).tolist() == [[1]]


def test_unknowns_counts_and_empty_shapes(lexicon, tmp_path):
    result = lexicon.relation_features(['ambiguous', ''], ['unknown', 'car'], BASIC_FEATURES)
    assert result['pair_known'].tolist() == [[0, 1], [0, 0]]
    assert result['reference_synset_count'].tolist() == [[2, 2], [0, 0]]
    assert result['student_synset_count'].tolist() == [[0, 1], [0, 1]]
    assert not result['antonym'].any()
    empty = WordNet(tmp_path).relation_features([], ['unknown'], BASIC_FEATURES)
    assert all(matrix.shape == (0, 1) for matrix in empty.values())
    with pytest.raises(ValueError):
        lexicon.relation_features(['car'], ['vehicle'], ['unknown_feature'])
    with pytest.raises(ValueError):
        lexicon.relation_features(['car'], ['vehicle'], ['antonym', 'antonym'])


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='requires local wn data')
def test_real_relations_stay_separate_from_similarity_scores(tmp_path):
    lexicon = WordNet()
    result = lexicon.relation_features(['vehicle', 'active'], ['car', 'inactive'], RELATION_FEATURES)
    assert result['reference_hypernym'][0, 0] == 1
    assert result['reference_hyponym'][0, 0] == 0
    assert result['antonym'][1, 1] == 1
    assert result['taxonomy_available'][0, 0] == 1
    assert result['wup_similarity'][0, 0] > .5
    assert 0 < result['path_similarity'][0, 0] <= 1
    assert lexicon.matrix(['vehicle'], ['car']).tolist() == [[0]]
    # OdeNet führt diese Antonymie auf Synset-Ebene statt zwischen Wortlesarten.
    german = OdeNet().relation_features(['Beginn'], ['Ende'], ['antonym'])
    assert german['antonym'].tolist() == [[1]]
    config = load_config()
    config['chains'] = {'wordnet': ['normalize', 'wordnet']}
    config['mixes'] = []
    case = {'id': 'relations', 'case_number': 1, 'title': 'Verwandt, nicht gleichwertig',
            'reference': [{'id': 'r', 'label': 'active', 'language': 'en'}],
            'student': [{'id': 's', 'label': 'inactive', 'language': 'en'}],
            'annotations': [['incorrect']]}
    output = tmp_path / 'relations.json'
    assert run_experiments({'cases': [case]}, output, config) == []
    payload = json.loads(output.read_text())
    assert payload['features'][0]['relation_features']['antonym'] == [[1]]
    assert payload['records'][0]['combinedScores'] == [[0]]
    assert payload['records'][0]['decisions']['threshold']['metrics']['fp'] == 0


@pytest.mark.parametrize('field,value', [('relation_features', ['not_a_feature']),
                                        ('relation_depth', 0), ('relation_depth', True)])
def test_invalid_relation_configuration_is_rejected(tmp_path, field, value):
    config = load_config()
    config['methods']['wordnet'][field] = value
    path = tmp_path / 'experiments.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        load_config(path)


def test_wn_translation_keeps_languages_and_missing_links_distinct():

    class Reader:
        def synset(self, identifier):
            targets = {'de-customer': ['en-customer'], 'de-poison': ['en-poison']}
            return SimpleNamespace(translate=lambda **kwargs: [
                SimpleNamespace(id=name) for name in targets.get(identifier, [])])

    german = {'Kunde': {'de-customer'}, 'Gift': {'de-poison'}, 'unmapped': {'de-unmapped'}}
    english = {'customer': {'en-customer'}, 'Gift': {'en-present'}}
    source = OdeNet()
    source.reader = Reader()
    source.lookup = lambda text: german.get(text, set())
    backend = {
        'de': source,
        'en': SimpleNamespace(reader=Reader(), lookup=lambda text: english.get(text, set())),
    }
    scores = wn_translation(['Kunde', 'Gift', 'unmapped', 'unknown'], ['customer', 'Gift'],
                            backend=backend, left_languages=['de'] * 4, right_languages=['en'] * 2)
    assert scores.tolist() == [[1, 0], [0, 0], [0, 0], [0, 0]]
    assert backend['coverage']['reference'][2]['status'] == 'unlinked'
    assert backend['coverage']['reference'][3]['status'] == 'unknown'
    assert wn_translation([], ['customer'], backend=backend, left_languages=[], right_languages=['en']).shape == (0, 1)
    with pytest.raises(ValueError, match='explicit de/en'):
        wn_translation(['Kunde'], ['customer'], backend=backend, left_languages=['fr'], right_languages=['en'])


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('RUN_LEXICON_TESTS') != '1', reason='requires local wn data')
def test_real_wn_translation_runs_without_machine_translation(tmp_path, monkeypatch):
    from synonym_matching import MatchingEngine

    engine = MatchingEngine({'methods': ['wn_translation']})

    def no_translation(*args):
        raise AssertionError('wn_translation must not call the text translator')

    monkeypatch.setattr(engine.translator, 'translate', no_translation)
    ref = [{'id': 'r', 'label': 'Kunde', 'language': 'de'}]
    student = [{'id': 's', 'label': 'customer', 'language': 'en'}]
    result = engine.match(ref, student)
    assert result['scores']['wn_translation'] == [[1]]
    assert result['referenceElements'] == ref and result['studentElements'] == student
    assert engine.backends['wn_translation']['coverage']['reference'][0]['status'] == 'linked'

    config = load_config()
    config['chains'] = {'wn_translate': ['normalize', 'wn_translation']}
    config['mixes'] = []
    case = {'id': 'crosslingual', 'case_number': 1, 'title': 'DE/EN',
            'reference': ref, 'student': student, 'annotations': [['correct']]}
    output = tmp_path / 'wn-translation.json'
    assert run_experiments({'cases': [case]}, output, config) == []
    feature = json.loads(output.read_text())['features'][0]
    assert feature['crosslingual_coverage']['reference'][0]['status'] == 'linked'
