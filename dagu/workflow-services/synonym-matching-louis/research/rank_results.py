"""Top-3-Übersichten aus gespeicherten Experimenten, ohne Modelle neu auszuführen."""

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .evaluation import evaluate_case, summarize
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
    'wn_translation': 'DE/EN-Synsets → wn.translate (ohne Textübersetzungsmodell)',
    'openthesaurus': 'OpenThesaurus',
    'odenet': 'OdeNet (DE, gemeinsame Synsets)',
    'word2vec_de_matching': 'Word2Vec (DE) → Greedy-1:1-Wort-Matching',
    'fasttext_de_matching': 'FastText (DE) → Greedy-1:1-Wort-Matching',
    'fasttext_en_matching': 'FastText (EN) → Greedy-1:1-Wort-Matching',
    'word2vec_de_optimal_matching': 'Word2Vec (DE) → optimales 1:1-Wort-Matching',
    'fasttext_de_optimal_matching': 'FastText (DE) → optimales 1:1-Wort-Matching',
    'fasttext_en_optimal_matching': 'FastText (EN) → optimales 1:1-Wort-Matching',
    'word2vec_de_bidirectional_matching': 'Word2Vec (DE) → bidirektionales Wort-Matching',
    'fasttext_de_bidirectional_matching': 'FastText (DE) → bidirektionales Wort-Matching',
    'fasttext_en_bidirectional_matching': 'FastText (EN) → bidirektionales Wort-Matching',
}


def mean(names):
    return 'Mittel(' + ' + '.join(names) + ')'


def chain_text(chain):
    """Zeige eine Kette mit Preprocessing, Übersetzung und Verfahren in Reihenfolge."""
    steps = ['DE→EN' if step == 'translate' else step for step in chain[:-1]]
    return ('+'.join(steps) or 'ohne_Preprocessing') + ' → ' + METHOD_NAMES.get(chain[-1], chain[-1])


def word_paths(spec):
    """Beschreibe die modellabhängigen Zusatzschritte der Wortvektorpfade."""
    paths = []
    for method, options in spec.get('word_matching', {}).items():
        steps = []
        if options.get('nouns_only'):
            steps.append('nouns_only')
        if options.get('lowercase', True):
            steps.append('lowercase')
        paths.append(f"{method}: {'_'.join(steps) or 'keine Zusatzschritte'}, δ={options.get('delta', .2)}")
    return ' [Wortpfade: ' + '; '.join(paths) + ']' if paths else ''


def describe_chains(spec):
    """Beschreibe Ketten und ihre Gewichte; jede Kette trägt ihr Preprocessing selbst."""
    combiner = spec['combiner']
    weights = combiner.get('weights') or {key: 1 for key in spec['chains']}
    total = sum(weights.values())
    parts = [(weights[key] / total, chain_text(chain)) for key, chain in spec['chains'].items()]
    text = parts[0][1] if len(parts) == 1 else ' + '.join(f'{100 * w:g}% {t}' for w, t in parts)
    return text + word_paths(spec)


def describe_pipeline(spec):
    """Zeige Schritte in Ausführungsreihenfolge und die tatsächliche Kombination."""
    if spec.get('combiner', {}).get('kind') == 'evidence':
        baseline = spec['chains'][spec['combiner']['baseline']]
        lexical = spec['chains'][spec['combiner']['lexicon']]
        return (f'Basis: {chain_text(baseline)}; Lexikonevidenz: {chain_text(lexical)} '
                '(beidseits eine Lesart: Synset→1, Gegenrelation→0, sonst Basis)')
    if spec.get('chain_based'):
        return describe_chains(spec)
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
        'consensus_fusion': f'Konsens({translated}; {multi}; Mittel bei Abweichung ≤ 0.2, sonst Minimum)',
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
    description += word_paths(spec) if any(method.endswith('_matching') for method in requires) else ''
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


def language_group(case):
    """Trenne rein deutsche, gemischte DE/EN- und spanische Fälle, z. B. 'de' oder 'de-en'."""
    languages = {e.get('language') for side in ('reference', 'student') for e in case[side]
                 if e['label'].strip() and e.get('language')}
    return '-'.join(sorted(languages)) or 'ohne Sprache'


def changed_label_rankings(payload, strategy):
    """Bewerte geänderte Schülerlabels gegen sämtliche Referenzkandidaten.

    Nur die Auswertung wird eingeschränkt. Scores, Kandidaten und die gespeicherte
    Auswahl (auch Hungarian/Mutual Best) stammen weiter vom vollständigen Modell.
    Top-1 betrachtet hier die Richtung Schülerlabel → Referenzlabel.
    """
    cases, columns = [], {}
    for case in payload['dataset']['cases']:
        # Ältere Labor-Ergebnisse enthalten nur changed_reference_ids. Die fünf
        # Varianten haben dieselben IDs; dies dient nur der Teilmengenauswahl.
        changed = set(case.get('changed_student_ids', case.get('changed_reference_ids', [])))
        indices = [i for i, element in enumerate(case['student']) if element['id'] in changed]
        if not indices:
            continue
        columns[case['id']] = indices
        cases.append({
            'id': case['id'], 'case_number': case['case_number'], 'title': case['title'],
            'reference': [case['student'][i] for i in indices], 'student': case['reference'],
            'annotations': [[row[i] for row in case['annotations']] for i in indices],
        })
    if not cases:
        return None
    cases_by_id = {case['id']: case for case in cases}
    features = {(tuple(f['chain']), f['case']): f for f in payload['features']}
    records = []
    for record in payload['records']:
        if (record['status'] != 'ok' or record['case'] not in columns
                or strategy not in record['decisions']):
            continue
        indices = columns[record['case']]
        spec = payload['definitions'][record['experiment']]
        shape = tuple(record['shape'])
        eligible = np.logical_or.reduce([
            np.asarray(features[tuple(chain), record['case']]['eligible'], dtype=bool).reshape(shape)
            for chain in spec['chains'].values()])
        decision = record['decisions'][strategy]
        metrics = evaluate_case(
            cases_by_id[record['case']], np.asarray(record['combinedScores']).T[indices],
            payload['threshold'], eligible=eligible.T[indices],
            selected=np.asarray(decision['selected'], dtype=bool).T[indices])
        records.append({**record, 'decisions': {strategy: {**decision, 'metrics': metrics}}})
    # Die Teilfälle tragen keine Änderungsmarkierungen: kein weiteres Teilranking.
    result = build_rankings({**payload, 'dataset': {'cases': cases}, 'records': records}, strategy)
    result['policy']['scope'] = 'Nur geänderte Schülerlabels; alle Referenzkandidaten bleiben erhalten.'
    result['policy']['top1_direction'] = 'student_to_reference'
    result['policy']['timings'] = 'Rechenzeiten des vollständigen Modells, kein separat gemessener Lauf.'
    return result


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
    languages = defaultdict(set)
    for case in cases:
        if evaluable(case):
            languages[language_group(case)].add(case['id'])
    language_groups = {name: top_three(rank(payload, ids, names, strategy), ids, len(names))
                       for name, ids in sorted(languages.items())}
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
    result = {'strategy': strategy, 'threshold': payload['threshold'],
            'policy': {'positive_cases': 'micro F1, precision, recall descending',
                       'negative_only': 'correct rejection rate',
                       'ties': 'same rank; alphabetical representatives; no runtime tiebreak',
                       'timings': 'compute seconds only; model loading is stored separately',
                       'scope': 'exploratory synthetic data; no automatic service changes'},
            'categories': categories, 'language_groups': language_groups,
            'overall_complete': complete, 'overall_common': shared}
    if any('changed_student_ids' in c or 'changed_reference_ids' in c for c in cases):
        result['changed_labels'] = changed_label_rankings(payload, strategy)
    return result


def print_rankings(rankings):
    """Zeige eine kompakte Übersicht im Terminal, ohne eine Berichtsdatei."""
    print(f"Top 3 | Auswahl: {rankings['strategy']} | Threshold: {rankings['threshold']}")
    print('Positive Fälle: F1 / Precision / Recall. Negativfälle: korrekte Ablehnung.')
    print('Gleichstände alphabetisch; Laufzeit ist kein Entscheidungskriterium.')
    sections = [(f"{c['number']}. {c['title']}", c) for c in rankings['categories']]
    sections += [(f'Sprachgruppe {name}', group)
                 for name, group in rankings.get('language_groups', {}).items()]
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
                  f"Rechnen={row['feature_seconds']:.4f}s, Auswahl={row['decision_seconds']:.4f}s")
        if not section['top3']:
            print('  Kein Qualitätsranking verfügbar.')
        if section['additional_tied_pipelines']:
            print(f"  +{section['additional_tied_pipelines']} weitere gleichwertige Pipelines")
        if section['technical_cases']:
            print('  Nur technisch geprüft: ' + ', '.join(section['technical_cases']))
    print('Gemeinsame Fallmenge: ' + ', '.join(rankings['overall_common']['cases']))
    print('Dort ausgeschlossen: ' + ', '.join(rankings['overall_common']['excluded_cases']))
    print('Vorläufige Ergebnisse auf synthetischen Daten; der Service bleibt unverändert.')
    if rankings.get('changed_labels'):
        print('\nZUSATZAUSWERTUNG: nur veränderte Schülerlabels, alle Referenzkandidaten.')
        print('Top1-Richtung: Schüler → Referenz. Zeiten stammen vom vollständigen Lauf.')
        print_rankings(rankings['changed_labels'])


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
    opener = gzip.open if args.input.suffix == '.gz' else open
    with opener(args.input, 'rt', encoding='utf-8') as stream:
        payload = json.load(stream)
    if not any(r['status'] == 'ok' and args.strategy in r['decisions']
               for r in payload['records']):
        parser.error('no successful records for this strategy')
    rankings = build_rankings(payload, args.strategy)
    payload.setdefault('rankings', {})[args.strategy] = rankings
    output.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if output.suffix == '.gz' else open
    with opener(output, 'wt', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        stream.write('\n')
    print_rankings(rankings)
    print(f"\nGespeichert: {output}")


if __name__ == '__main__':
    main()
