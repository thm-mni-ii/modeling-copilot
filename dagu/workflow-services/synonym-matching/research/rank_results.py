"""Top-3-Übersichten aus gespeicherten Experimenten, ohne Modelle neu auszuführen."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .evaluation import summarize
from .pipeline_names import describe_pipeline


def evaluable(case):
    """Leere Mengen und ausschließlich leere Labels sind technische Sonderfälle."""
    return any(r['label'].strip() and s['label'].strip()
               for r in case['reference'] for s in case['student'])


def rank(payload, case_ids, names, strategy='threshold'):
    """Vergleiche nur vollständig verfügbare Pipelines auf denselben Fällen."""
    cases = {c['id']: c for c in payload['dataset']['cases']}
    rows = {(r['experiment'], r['case']): r for r in payload['records']
            if r['status'] == 'ok' and strategy in r['decisions']}
    negatives = sum(
        case['annotations'][i][j] == 'incorrect'
        for cid in case_ids for case in [cases[cid]]
        for i, ref in enumerate(case['reference'])
        for j, student in enumerate(case['student'])
        if ref['label'].strip() and student['label'].strip())
    results = []
    if not case_ids:
        return results
    for name in names:
        if not all((name, cid) in rows for cid in case_ids):
            continue
        records = [rows[name, cid] for cid in sorted(case_ids)]
        stats = summarize([r['decisions'][strategy]['metrics'] for r in records])
        has_positives = stats['tp'] + stats['fn'] > 0
        rejection = 1 - stats['fp'] / negatives if negatives else None
        # Bei reinen Negativfällen wäre F1 stets 0, auch bei korrekter Ablehnung.
        quality = ((stats['f1'], stats['precision'], stats['recall'])
                   if has_positives else (rejection, 0, 0))
        multi = [r for r in records if len(cases[r['case']]['student']) > 1]
        top = summarize([r['decisions'][strategy]['metrics'] for r in multi])
        results.append({
            'pipeline': name, 'metrics': stats, 'quality': quality,
            'description': describe_pipeline(payload['definitions'][name]),
            'has_positives': has_positives, 'rejection': rejection,
            'top1': top['top1'] / top['queries'] if top['queries'] else None,
            'feature_seconds': sum(r['feature_seconds'] for r in records),
            'decision_seconds': sum(r['combine_seconds']
                                    + r['decisions'][strategy]['seconds'] for r in records),
        })
    # Namen dienen nur der stabilen Darstellung; Laufzeit entscheidet keine Gleichstände.
    results.sort(key=lambda r: (tuple(-v for v in r['quality']), r['pipeline']))
    previous = None
    for index, row in enumerate(results):
        if row['quality'] != previous:
            position = index + 1
        row['rank'] = position
        previous = row['quality']
    return results


def top_three(results, case_ids, total_pipelines, technical=()):
    """Speichere drei Vertreter samt Gleichständen und Vergleichsgrundlage."""
    shown = results[:3]
    tied = sum(row['quality'] == shown[-1]['quality'] for row in results[3:]) if shown else 0
    return {'cases': sorted(case_ids), 'technical_cases': list(technical),
            'eligible_pipelines': len(results), 'total_pipelines': total_pipelines,
            'top3': shown, 'additional_tied_pipelines': tied}


def build_rankings(payload, strategy='threshold'):
    """Erzeuge JSON-Daten für Kategorien und Gesamtrankings."""
    if strategy not in {'threshold', 'mutual_best', 'hungarian'}:
        raise ValueError('unknown assignment strategy')
    cases = payload['dataset']['cases']
    names = list(payload['definitions'])
    groups = defaultdict(list)
    for case in cases:
        groups[case['case_number']].append(case)
    categories = []
    for number, group in sorted(groups.items()):
        selected = {case['id'] for case in group if evaluable(case)}
        technical = [case['id'] for case in group if not evaluable(case)]
        categories.append({'number': number, 'title': group[0]['title'],
            **top_three(rank(payload, selected, names, strategy), selected, len(names), technical)})
    all_cases = {case['id'] for case in cases if evaluable(case)}
    complete = top_three(rank(payload, all_cases, names, strategy), all_cases, len(names))
    available = {name: set() for name in names}
    for row in payload['records']:
        if row['status'] == 'ok' and strategy in row['decisions']:
            available[row['experiment']].add(row['case'])
    active = [name for name in names if available[name] & all_cases]
    common = all_cases.intersection(*(available[name] for name in active)) if active else set()
    shared = top_three(rank(payload, common, active, strategy), common, len(names))
    shared['excluded_cases'] = sorted(all_cases - common)
    return {'strategy': strategy, 'threshold': payload['threshold'],
            'policy': {'positive_cases': 'micro F1, precision, recall descending',
                       'negative_only': 'correct rejection rate',
                       'ties': 'same rank; alphabetical representatives; no runtime tiebreak',
                       'timings': 'shared features; not isolated end-to-end times',
                       'scope': 'exploratory synthetic data; no automatic service changes'},
            'categories': categories, 'overall_complete': complete, 'overall_common': shared}


def print_rankings(rankings):
    """Zeige eine kompakte Übersicht im Terminal, ohne eine Berichtsdatei."""
    print(f"Top 3 | Auswahl: {rankings['strategy']} | Threshold: {rankings['threshold']}")
    print('Positive Fälle: F1 / Precision / Recall. Negativfälle: korrekte Ablehnung.')
    print('Gleichstände alphabetisch; Laufzeit ist kein Entscheidungskriterium.')
    sections = [(f"{c['number']}. {c['title']}", c) for c in rankings['categories']]
    sections += [('Gesamt: vollständige Abdeckung', rankings['overall_complete']),
                 ('Gesamt: gemeinsame Fallmenge', rankings['overall_common'])]
    for title, section in sections:
        print(f"\n{title} ({len(section['cases'])} Szenarien; "
              f"{section['eligible_pipelines']}/{section['total_pipelines']} Pipelines)")
        for row in section['top3']:
            m = row['metrics']
            quality = (f"F1={m['f1']:.3f} P={m['precision']:.3f} R={m['recall']:.3f}"
                       if row['has_positives'] else f"Ablehnung={row['rejection']:.3f}")
            top1 = f"{row['top1']:.3f}" if row['top1'] is not None else 'n/a'
            print(f"  {row['rank']}. {row['description']}")
            print(f"     {quality}; "
                  f"Top1={top1}; FP/FN={m['fp']}/{m['fn']}; "
                  f"Features={row['feature_seconds']:.4f}s, Auswahl={row['decision_seconds']:.4f}s")
        if not section['top3']:
            print('  Kein Qualitätsranking verfügbar.')
        if section['additional_tied_pipelines']:
            print(f"  +{section['additional_tied_pipelines']} weitere gleichwertige Pipelines")
        if section['technical_cases']:
            print('  Nur technisch geprüft: ' + ', '.join(section['technical_cases']))
    print('Gemeinsame Fallmenge: ' + ', '.join(rankings['overall_common']['cases']))
    print('Dort ausgeschlossen: ' + ', '.join(rankings['overall_common']['excluded_cases']))
    print('Vorläufige Ergebnisse auf synthetischen Daten; der Service bleibt unverändert.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='Optional eine neue JSON-Kopie statt der Eingabedatei')
    parser.add_argument('--strategy', choices=['threshold', 'mutual_best', 'hungarian'],
                        default='threshold')
    args = parser.parse_args()
    output = args.output or args.input
    if output.resolve() != args.input.resolve() and output.exists():
        parser.error('choose a new output filename')
    payload = json.loads(args.input.read_text())
    if not any(r['status'] == 'ok' and args.strategy in r['decisions']
               for r in payload['records']):
        parser.error('no successful records for this strategy')
    rankings = build_rankings(payload, args.strategy)
    payload.setdefault('rankings', {})[args.strategy] = rankings
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print_rankings(rankings)
    print(f"\nGespeichert: {output}")


if __name__ == '__main__':
    main()
