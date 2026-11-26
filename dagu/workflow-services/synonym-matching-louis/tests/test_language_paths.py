"""Parallelkorpus: Sprachfassungen verändern keine Identitäten oder Goldzuordnungen."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from research.compare_language_paths import validate_cases


def corpus():
    return json.loads((Path(__file__).resolve().parents[1]/'research/language-path-cases.json').read_text())


def test_corpus_is_paired_and_contains_no_label_language_attribute():
    data=corpus()
    validate_cases(data)
    assert len(data['cases'])==27
    gold=[v for c in data['cases'] for row in c['annotations'] for v in row]
    assert gold.count('correct')==22
    assert gold.count('incorrect')==40
    for c in data['cases']:
        for language in ('de','en'):
            for side in ('reference','student'):
                assert all(set(e)=={'id','label'} for e in c[language][side])


@pytest.mark.parametrize('change',['identity','empty','annotation','duplicate'])
def test_unmatched_or_invalid_variants_are_rejected(change):
    data=deepcopy(corpus())
    if change=='identity':data['cases'][0]['en']['reference'][0]['id']='other'
    elif change=='empty':data['cases'][0]['en']['student'][0]['label']=''
    elif change=='annotation':data['cases'][0]['annotations']=[[]]
    else:data['cases'].append(deepcopy(data['cases'][0]))
    with pytest.raises(ValueError):validate_cases(data)
