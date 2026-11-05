"""Top-3-Übersichten aus gespeicherten Experimenten, ohne Modelle neu auszuführen."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .evaluation import summarize
from synonym_matching.combinations import STRINGS, TOKENS

METHOD_NAMES = {
    'levenshtein': 'Levenshtein',
    'damerau_levenshtein': 'Damerau-Levenshtein',
    'jaro_winkler': 'Jaro-Winkler',
    'char_bigram': 'Zeichen-Bigramme',
    'char_trigram': 'Zeichen-Trigramme',
    'token_jaccard': 'Token-Jaccard',
    'token_sort_ratio': 'Token-Sort-Ratio',
    'word_order': 'Wortreihenfolge (Token-LCS)',
    'exact_match': 'Exakter Textvergleich',
    'multilingual': 'Multilinguales Embedding',
    'translated_embedding': 'DE→EN-Übersetzung → monolinguales Embedding',
    'wordnet': 'DE→EN-Übersetzung → WordNet',
    'openthesaurus': 'OpenThesaurus',
    'word2vec_matching': 'Word2Vec → Greedy-1:1-Wort-Matching',
    'fasttext_matching': 'FastText → Greedy-1:1-Wort-Matching',
    'glove_matching': 'GloVe → Greedy-1:1-Wort-Matching',
    'paragram_matching': 'Paragram → Greedy-1:1-Wort-Matching',
}


def mean(names):
    return 'Mittel(' + ' + '.join(names) + ')'


def describe_pipeline(spec):
    """Zeige Schritte in Ausführungsreihenfolge und die tatsächliche Kombination."""
    strings = mean([METHOD_NAMES[name] for name in STRINGS])
    tokens = mean([METHOD_NAMES[name] for name in TOKENS])
    multi = METHOD_NAMES['multilingual']
    translated = METHOD_NAMES['translated_embedding']
    hybrid = f'50% {strings} + 50% {multi}'
    expressions = {
        **METHOD_NAMES,
        'translated_string': f'DE→EN-Übersetzung → {strings}',
        'string_ensemble': strings,
        'token_ensemble': tokens,
        'character_token_ensemble': f'50% {strings} + 50% {tokens}',
        'embedding_ensemble': mean([translated, multi]),
        'string_multilingual': hybrid,
        'string_translation_embedding': f'50% {strings} + 50% {translated}',
        'string_both_embeddings': mean([strings, translated, multi]),
        'maximum_fusion': f'Maximum({strings}; {multi})',
        'geometric_fusion': f'Geometrisches Mittel({strings}; {multi})',
        'exact_match_fusion': f'Exakt-Regel (bei Textgleichheit 1, sonst {hybrid})',
        'context_aware': f'Kandidatenkonkurrenz-Korrektur({hybrid}; penalty=0.5)',
    }
    combiner = spec.get('combiner', {})
    name = combiner.get('name', spec.get('function', spec.get('name', '')))
    requires = spec.get('methods', spec.get('requires', []))
    if name == 'weighted_fusion':
        weight = combiner.get('options', spec.get('options', {})).get('embedding_weight', .5)
        expression = f'{(1 - weight) * 100:g}% {strings} + {weight * 100:g}% {multi}'
    elif combiner.get('kind') == 'weighted_mean':
        weights = combiner['weights']
        total = sum(weights.values())
        expression = ' + '.join(f'{100 * weights[method] / total:g}% {expressions.get(method, method)}'
                                for method in requires)
    elif combiner.get('kind') in {'mean', 'max'}:
        parts = [expressions.get(method, method) for method in requires]
        expression = parts[0] if len(parts) == 1 else (mean(parts) if combiner['kind'] == 'mean'
                                                      else 'Maximum(' + '; '.join(parts) + ')')
    elif spec.get('kind') == 'lexicon_string':
        expression = f'50% {METHOD_NAMES[requires[0]]} + 50% {strings}'
    elif spec.get('kind') == 'mean':
        expression = mean([METHOD_NAMES.get(method, method) for method in requires])
    else:
        expression = expressions.get(name, name or 'Unbekanntes Verfahren')
    steps = spec.get('preprocessing', [])
    preprocessing = '_'.join(steps) if steps else 'ohne_Preprocessing'
    description = f'{preprocessing} - {expression}'
    # Die Ablation verändert Stringverfahren, nicht die separaten Sprachpfade.
    semantic = {'multilingual', 'translated_embedding', 'translated_string', 'wordnet', 'openthesaurus'}
    if set(requires) & semantic and set(requires) & (set(STRINGS) | set(TOKENS)):
        description += ' [Preprocessing vorne: Stringpfad; Sprach-/Lexikonpfade: normalize]'
    if name == 'exact_match_fusion':
        description += ' [Exakt-Prüfung: normalize auf Originaltext]'
    if any(method.endswith('_matching') for method in requires):
        paths = []
        for method, options in spec.get('word_matching', {}).items():
            steps = list(options['preprocessing'])
            if options['translate_to_en']:
                steps.append('DE→EN')
            if options['nouns_only']:
                steps.append('nouns_only')
            if options['lowercase']:
                steps.append('lowercase')
            paths.append(f"{method}: {'_'.join(steps)}, δ={options['delta']}")
        description += ' [Wortpfade: ' + '; '.join(paths) + ']'
    if spec.get('global_ranking'):
        description += ' → Zeilen-/Spaltenrang-Fusion'
    return description


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
