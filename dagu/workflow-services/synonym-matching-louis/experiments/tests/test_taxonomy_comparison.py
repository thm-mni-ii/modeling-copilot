"""Taxonomie nur als explizite Ablation, ohne unbekannte Paare abzuwerten."""

import pytest

from research.decision_tree import decide
from research.compare_taxonomy import distributions


@pytest.mark.parametrize(('policy', 'expected'), [
    ({'path_similarity': .25}, 'open'),
    ({'wup_similarity': .8}, 'confirmed'),
    ({'path_similarity': .25, 'wup_similarity': .8}, 'open'),
])
def test_ambiguous_coverage_ablation_is_opt_in(policy, expected):
    values = {'pair_known': 1, 'reference_synset_count': 3, 'student_synset_count': 2,
              'shared_synset': 0, 'antonym': 0, 'reference_hypernym': 0,
              'reference_hyponym': 0, 'taxonomy_available': 1,
              'path_similarity': .2, 'wup_similarity': .9}
    text = {'status': 'supported', 'tier': 'meaning'}
    assert decide(values, text, taxonomy_policy=policy)[0] == 'confirmed'
    assert decide(values, text, taxonomy_policy=policy, taxonomy_single_sense=False)[0] == expected
    for changes in ({'pair_known': 0}, {'taxonomy_available': 0}):
        assert decide({**values, **changes}, text, taxonomy_policy=policy,
                      taxonomy_single_sense=False)[0] == 'confirmed'
    assert decide({**values, 'shared_synset': 1}, text, taxonomy_policy=policy,
                  taxonomy_single_sense=False)[1] == 'shared_synset'
    assert decide(values, {'status': 'below_threshold', 'tier': None},
                  taxonomy_policy=policy, taxonomy_single_sense=False)[0] == 'open'


def test_missing_values_are_not_averaged_as_zero():
    base = {'correct': False, 'confirmed': True, 'reason': 'meaning', 'pair_known': True,
            'single_sense': False}
    rows = [{**base, 'taxonomy_available': True, 'path_similarity': .2, 'wup_similarity': .9},
            {**base, 'taxonomy_available': False, 'path_similarity': None, 'wup_similarity': None}]
    group = distributions(rows)['meaning_incorrect']
    assert group['coverage'] == .5
    assert group['path_similarity']['median'] == .2
    assert group['single_sense_available'] == 0
    assert distributions([])['false_positives']['wup_similarity'] is None
