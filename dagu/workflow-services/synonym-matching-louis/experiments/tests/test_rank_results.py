"""Vergleichbare Fallmengen, negative Beispiele und Gleichstände im Ranking."""

import json

from research.rank_results import rank, build_rankings, print_rankings, main


def example():
    cases = [dict(id='positive', case_number=1, title='Identisch',
                  reference=[{'label': 'Kunde'}], student=[{'label': 'Kunde'}],
                  annotations=[['correct']]),
             dict(id='negative', case_number=15, title='Verwandt',
                  reference=[{'label': 'Kunde'}], student=[{'label': 'Lieferant'}],
                  annotations=[['incorrect']])]
    payload = {'threshold': .5, 'dataset': {'cases': cases},
               'definitions': {n: {} for n in ['good', 'bad', 'missing']},
               'records': [], 'errors': []}
    for name in payload['definitions']:
        for cid in ['positive', 'negative']:
            if name == 'missing' and cid == 'negative':
                continue
            fp = int(name == 'bad' and cid == 'negative')
            metrics = dict(tp=int(cid == 'positive'), fp=fp, fn=0,
                           tn=int(cid == 'negative') - fp,
                           top1=int(cid == 'positive'), queries=int(cid == 'positive'),
                           pairs=1, all_correct=not fp)
            payload['records'].append(dict(
                experiment=name, case=cid, status='ok', feature_seconds=1,
                combine_seconds=.1, decisions={'threshold': {'metrics': metrics, 'seconds': .01}}))
    return payload


def test_negative_cases_reward_correct_rejection_and_require_coverage():
    payload = example()
    rows = rank(payload, {'negative'}, payload['definitions'])
    assert [r['pipeline'] for r in rows] == ['good', 'bad']
    assert rows[0]['rejection'] == 1
    assert rows[1]['rejection'] == 0
    assert not rows[0]['has_positives']
    assert rank(payload, set(), payload['definitions']) == []


def test_global_ranking_excludes_incomplete_pipeline_and_marks_ties():
    payload = example()
    rows = rank(payload, {'positive', 'negative'}, payload['definitions'])
    assert [r['pipeline'] for r in rows] == ['good', 'bad']
    assert rows[0]['metrics']['f1'] == 1
    tied = rank(payload, {'positive'}, payload['definitions'])
    assert [r['rank'] for r in tied] == [1, 1, 1]


def test_report_marks_technical_cases_ties_and_different_cohorts(capsys):
    payload = example()
    payload['dataset']['cases'].append(dict(id='empty', case_number=28,
        title='Leer', reference=[], student=[], annotations=[]))
    for i in range(4):
        name = f'tied-{i}'
        payload['definitions'][name] = {}
        payload['records'].extend([{**r, 'experiment': name}
                                   for r in list(payload['records']) if r['experiment'] == 'good'])
    rankings = build_rankings(payload)
    assert rankings['categories'][-1]['technical_cases'] == ['empty']
    assert rankings['overall_complete']['additional_tied_pipelines'] > 0
    assert rankings['overall_common']['excluded_cases'] == ['negative']
    print_rankings(rankings)
    text = capsys.readouterr().out
    assert 'Nur technisch geprüft: empty' in text
    assert 'weitere gleichwertige Pipelines' in text
    assert 'Gesamt: vollständige Abdeckung' in text


def test_language_groups_keep_german_mixed_and_spanish_cases_apart(capsys):
    payload = example()
    for case, languages in zip(payload['dataset']['cases'], ['de', 'es']):
        for side in ('reference', 'student'):
            case[side][0]['language'] = languages
    payload['dataset']['cases'][1]['student'][0]['language'] = 'en'
    rankings = build_rankings(payload)
    assert set(rankings['language_groups']) == {'de', 'en-es'}
    assert rankings['language_groups']['de']['cases'] == ['positive']
    print_rankings(rankings)
    assert 'Sprachgruppe en-es' in capsys.readouterr().out


def test_cli_saves_rankings_in_existing_json_only(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'run.json'
    original = example()
    path.write_text(json.dumps(original))
    monkeypatch.setattr('sys.argv', ['rank_results', '--input', str(path)])
    main()
    saved = json.loads(path.read_text())
    assert saved['records'] == original['records']
    assert 'threshold' in saved['rankings']
    assert list(tmp_path.iterdir()) == [path]
    assert 'Top 3' in capsys.readouterr().out
