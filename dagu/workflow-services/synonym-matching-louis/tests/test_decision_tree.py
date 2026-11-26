"""Eindeutige Lexikonevidenz, Enthaltung und wiederverwendete produktive Textstufen."""

import pytest

from research.decision_tree import decide, production_modules, _summary


def features(**changes):
    return {'pair_known': 1, 'reference_synset_count': 1, 'student_synset_count': 1,
            'shared_synset': 0, 'antonym': 0, 'reference_hypernym': 0,
            'reference_hyponym': 0, 'path_similarity': .99, **changes}


def text(tier=None, veto=None):
    return {'status': 'supported' if tier else 'below_threshold', 'tier': tier, 'veto': veto}


@pytest.mark.parametrize('relation', ['antonym', 'reference_hypernym', 'reference_hyponym'])
def test_explicit_single_sense_counterrelation_precedes_similarity(relation):
    assert decide(features(**{relation: 1}), text('meaning')) == ('rejected', 'single_sense_counterrelation')
    assert decide(features(**{relation: 1, 'reference_synset_count': 2}), text('canonical'))[0] == 'open'


def test_missing_coverage_does_not_reject_and_ontology_never_confirms():
    assert decide(features(pair_known=0, reference_synset_count=0), text('spelling'))[0] == 'confirmed'
    assert decide(features(), text())[0] == 'open'
    assert decide(features(shared_synset=1), text())[1] == 'shared_synset'
    assert decide(features(shared_synset=1, reference_synset_count=3), text())[0] == 'confirmed'
    assert decide(features(shared_synset=1, antonym=1), text())[0] == 'open'


def test_multiple_senses_can_share_a_synset_and_strict_ablation_is_retained():
    f=features(shared_synset=1,reference_synset_count=12,student_synset_count=1)
    assert decide(f,text()) == ('confirmed','shared_synset')
    assert decide(f,text(),require_single_synset=True)[0] == 'open'
    assert decide(features(shared_synset=0),text())[0] == 'open'
    with pytest.raises(ValueError):
        decide(f,text(),require_single_synset=1)


def test_embedding_policy_empty_labels_and_digit_guard():
    assert decide(features(), text('meaning'), embedding_action='confirm')[0] == 'confirmed'
    assert decide(features(), text('meaning'), embedding_action='open')[0] == 'open'
    assert decide(features(), text('canonical'), valid=False)[0] == 'not_evaluable'
    assert decide(features(), text(veto='digit_mismatch'))[0] == 'rejected'
    with pytest.raises(ValueError):
        decide(features(), text(), embedding_action='other')


def test_production_preprocessing_and_guards_are_reused():
    registry, adapter = production_modules()
    texts = ['GebäudeNr.', 'Gebaeudenummer']
    method = registry.resolve_methods(['damerau_canonical'])[0]
    for step in method.preprocessing:
        texts = [registry.PREPROCESSORS[step](t) for t in texts]
    assert method.compute(None, texts[:1], texts[1:])[0,0] == 1
    assert adapter.text_veto('Version 1', 'Version 2') == 'digit_mismatch'
    assert adapter.text_veto('Nachname', 'Vorname') == 'start_mismatch'


def test_open_is_not_confirmation_and_top1_is_not_invented():
    case = {'id': 'c', 'reference': [{'id': 'r', 'label': 'Kunde'}],
            'student': [{'id': 'a', 'label': 'Abnehmer'}, {'id': 'b', 'label': 'Lieferant'}],
            'annotations': [['correct', 'incorrect']], 'changed_student_ids': ['a']}
    record = {'variant': 'tree', 'case': 'c', 'eligible': [[True, True]],
              'verdicts': [['open', 'rejected']]}
    metrics = _summary([case], [record], ['tree'])['tree']
    assert metrics['tp'] == metrics['fp'] == 0
    assert metrics['fn'] == 1
    assert metrics['automatic_decision_coverage'] == .5
    assert 'top1' not in metrics
    changed = _summary([case], [record], ['tree'], changed=True)['tree']
    assert changed['verdict_counts'] == {'open': 1}


def test_taxonomy_is_a_guard_not_an_independent_synonym_decision():
    f = features(taxonomy_available=1, path_similarity=.2, wup_similarity=.9)
    policy = {'path_similarity':.25, 'wup_similarity':.8}
    assert decide(f,text('meaning'))[0] == 'confirmed'
    assert decide(f,text('meaning'),taxonomy_policy=policy) == ('open','taxonomy_disagrees_with_embedding')
    assert decide(f,text('meaning'),taxonomy_policy={'wup_similarity':.8})[0] == 'confirmed'
    assert decide(f,text('canonical'),taxonomy_policy=policy)[0] == 'confirmed'
    assert decide(features(taxonomy_available=1,path_similarity=1,wup_similarity=1),
                  text(),taxonomy_policy=policy)[0] == 'open'


@pytest.mark.parametrize('changes', [{'taxonomy_available':0}, {'reference_synset_count':2},
                                    {'pair_known':0, 'student_synset_count':0}])
def test_missing_or_ambiguous_taxonomy_does_not_become_negative_evidence(changes):
    f=features(**{'taxonomy_available':1,'path_similarity':0,'wup_similarity':0,**changes})
    assert decide(f,text('meaning'),taxonomy_policy={'path_similarity':.25,'wup_similarity':.8})[0] == 'confirmed'


def test_explicit_counterrelation_precedes_high_taxonomy():
    f=features(taxonomy_available=1,path_similarity=1,wup_similarity=1,reference_hypernym=1)
    assert decide(f,text('meaning'),taxonomy_policy={'path_similarity':.25,'wup_similarity':.8})[0] == 'rejected'
