"""Prüfe den Datenimport und fachlich festgelegte Beispiele, keine Modellqualität."""

import gzip
import json
import sys

from research.build_laboratory_cases import HERE, SOURCE, VARIANTS, build, read_labels
from research.compare import run_experiments
from research.experiments import load_config


def annotation(case, reference_id, student_id):
    row = next(i for i, e in enumerate(case['reference']) if e['id'] == reference_id)
    column = next(i for i, e in enumerate(case['student']) if e['id'] == student_id)
    return case['annotations'][row][column]


def test_five_complete_models_are_preserved_and_reproducible():
    data = build()
    assert data == json.loads((HERE / 'laboratory-cases.json').read_text())
    assert len(data['cases']) == 5
    for case, variant in zip(data['cases'], VARIANTS, strict=True):
        assert case['reference'] == read_labels(SOURCE / 'sample_solution.json')
        source = read_labels(SOURCE / f'synonym_{variant}.json')
        assert [(e['id'], e['label']) for e in case['student']] == [
            (e['id'], e['label']) for e in source]
        assert len(case['reference']) == len(case['student']) == 48
        assert len(case['annotations']) == 48
        assert all(len(row) == 48 for row in case['annotations'])
        assert len({e['id'] for e in case['student']}) == 48
    # Gleiche Schreibweise kann je nach Datei Deutsch oder Englisch sein.
    terms, languages = data['cases'][2:4]
    assert next(e for e in terms['student'] if e['id'] == '19')['language'] == 'de'
    assert next(e for e in languages['student'] if e['id'] == '19')['language'] == 'en'


def test_annotations_follow_meaning_not_equal_ids():
    cases = {case['id']: case for case in build()['cases']}
    terms = cases['laboratory-terms']
    assert annotation(terms, '19', '19') == 'correct'  # Versuch / Experiment
    assert annotation(terms, '19', '15') == 'incorrect'  # Versuch / Forschende
    assert annotation(terms, '47', '47') == 'correct'  # Nachname / Familienname
    assert annotation(terms, '47', '46') == 'incorrect'  # Nachname / Vorname
    assert annotation(terms, '9', '9') == 'correct'  # Gerätearten laut Fallstudie
    # Gebäudenummern bleiben gültige Labelkandidaten, auch mit anderen IDs.
    assert annotation(terms, '28', '29') == 'correct'
    ambiguity = cases['laboratory-ambiguity']
    for ref, student in [('9', '9'), ('7', '7'), ('44', '44'), ('33', '33'), ('76', '76')]:
        assert annotation(ambiguity, ref, student) == 'incorrect'
    assert annotation(ambiguity, '52', '76') == 'correct'  # Ende / Ende
    assert annotation(ambiguity, '52', '77') == 'correct'  # Ende / Schluss


def test_existing_runner_accepts_all_five_complete_models(tmp_path, monkeypatch):
    config = load_config()
    config['chains'] = {'lev': ['normalize', 'levenshtein']}
    config['mixes'] = []
    output = tmp_path / 'laboratory.json.gz'
    assert run_experiments(build(), output, config) == []
    with gzip.open(output, 'rt', encoding='utf-8') as stream:
        run = json.load(stream)
    assert len(run['records']) == 5
    assert all(row['shape'] == [48, 48] for row in run['records'])
    assert not run['excluded_cases']
    focused = run['rankings']['threshold']['changed_labels']
    assert len(focused['categories']) == 5
    assert focused['policy']['top1_direction'] == 'student_to_reference'
    # Auch die erneute Ranglistenberechnung muss komprimierte Ergebnisse lesen.
    from research import rank_results
    monkeypatch.setattr(sys, 'argv', ['rank_results', '--input', str(output),
                                     '--strategy', 'mutual_best'])
    rank_results.main()
    with gzip.open(output, 'rt', encoding='utf-8') as stream:
        assert 'mutual_best' in json.load(stream)['rankings']


def test_changed_labels_keep_all_reference_candidates_and_original_assignment(tmp_path):
    from research.rank_results import build_rankings

    case = {
        'id': 'changed', 'case_number': 1, 'title': 'Änderung',
        'reference': [{'id': 'r1', 'label': 'Kunde', 'language': 'de'},
                      {'id': 'r2', 'label': 'Abnehmer', 'language': 'de'}],
        'student': [{'id': 's1', 'label': 'Kunde', 'language': 'de'},
                    {'id': 's2', 'label': 'Kund', 'language': 'de'}],
        'annotations': [['correct', 'correct'], ['incorrect', 'incorrect']],
        'changed_student_ids': ['s2'], 'changed_reference_ids': ['r2'],
    }
    config = load_config()
    config['chains'] = {'lev': ['normalize', 'levenshtein']}
    config['mixes'] = []
    output = tmp_path / 'focus.json'
    assert run_experiments({'cases': [case]}, output, config) == []
    run = json.loads(output.read_text())
    full = run['rankings']['threshold']['overall_complete']['top3'][0]['metrics']
    focused = run['rankings']['threshold']['changed_labels']['overall_complete']['top3'][0]
    # Der unveränderte Treffer zählt nicht; der richtige Referenzkandidat r1 bleibt.
    assert full['tp'] == 2 and full['pairs'] == 4
    assert focused['metrics']['tp'] == 1 and focused['metrics']['pairs'] == 2
    assert focused['top1'] == 1
    # Hungarian hat r1 bereits an s1 vergeben. Auf der Teilmenge neu zu optimieren
    # würde s2 fälschlich als ausgewählten Treffer ausweisen.
    hungarian = build_rankings(run, 'hungarian')['changed_labels']['overall_complete']['top3'][0]
    assert hungarian['metrics']['tp'] == 0 and hungarian['metrics']['fn'] == 1


def test_changed_negative_counts_false_matches_not_unchanged_success(tmp_path):
    case = {
        'id': 'negative', 'case_number': 1, 'title': 'Falscher verwandter Begriff',
        'reference': [{'id': 'r', 'label': 'Geräte', 'language': 'de'}],
        'student': [{'id': 's1', 'label': 'Geräte', 'language': 'de'},
                    {'id': 's2', 'label': 'Geräteraum', 'language': 'de'}],
        'annotations': [['correct', 'incorrect']], 'changed_student_ids': ['s2'],
    }
    config = load_config()
    config['chains'] = {'jw': ['normalize', 'jaro_winkler']}
    config['mixes'] = []
    output = tmp_path / 'negative.json'
    assert run_experiments({'cases': [case]}, output, config) == []
    run = json.loads(output.read_text())
    focused = run['rankings']['threshold']['changed_labels']['overall_complete']['top3'][0]
    assert focused['metrics']['tp'] == 0 and focused['metrics']['fp'] == 1
    assert focused['rejection'] == 0 and focused['top1'] is None
