"""Compare fixed methods on the 28 requested categories: matrices + one overview."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from synonym_matching import MatchingEngine
from synonym_matching.engine import (
    build_candidates,
    format_synonym_matrix,
    nonempty_pairs,
)
from synonym_matching.evaluation import evaluate_case, summarize
from synonym_matching.variants import REQUIRES, evaluate_variant

HERE = Path(__file__).resolve().parent
STRINGS = ['levenshtein', 'damerau_levenshtein', 'jaro_winkler', 'char_bigram',
           'char_trigram', 'token_jaccard', 'token_sort_ratio', 'word_order', 'exact_match']


def run(data, output, models=False, threshold=0.5, preprocessing=None, lexicons=False):
    """Vergleiche Methoden auf denselben Fällen; schreibe Matrizen und Übersicht."""
    if (type(threshold) not in (int, float)
            or not np.isfinite(threshold) or not 0 <= threshold <= 1):
        raise ValueError('threshold must be in [0,1]')
    output = Path(output)
    overview = output.with_suffix('.md')
    if output.exists() or overview.exists():
        raise FileExistsError('choose a new output filename')
    output.parent.mkdir(parents=True, exist_ok=True)
    preprocessing = preprocessing if preprocessing is not None else ['normalize', 'lowercase']
    methods = STRINGS + (['multilingual'] if models else [])
    primary = MatchingEngine({'methods': methods, 'preprocessing': preprocessing})
    translation = MatchingEngine({'methods': ['translated_string', 'translated_embedding'],
                                  'preprocessing': preprocessing}) if models else None
    dictionaries = [MatchingEngine({'methods': [name], 'preprocessing': preprocessing})
                    for name in ('wordnet', 'openthesaurus')] if lexicons else []
    if translation and dictionaries:
        dictionaries[0].translator = translation.translator
    available = set(methods + (['translated_string', 'translated_embedding'] if models else [])
                    + (['wordnet', 'openthesaurus'] if lexicons else []))
    aliases = {'translation_string', 'translation_monolingual',
               'multilingual_only', 'weighted_fusion'}
    variants = [name for name, requires in REQUIRES.items()
                if set(requires) <= available and name not in aliases]
    records = []
    errors = []
    evaluations = {}
    statuses = []
    # Zuerst Basisscores pro Fall berechnen, dann daraus Varianten ableiten.
    started = time.perf_counter()
    for case in data['cases']:
        raw = {}
        failed = {}
        usable = {}
        shape = (len(case['reference']), len(case['student']))
        for engine in [primary] + ([translation] if translation else []) + dictionaries:
            labels = case['reference'] + case['student']
            uses_translation = engine is translation or 'wordnet' in engine.methods
            unsupported_translation = any(
                element['label'].strip() and element.get('language') not in {'de', 'en'}
                for element in labels
            )
            if uses_translation and unsupported_translation:
                for name in engine.methods:
                    failed[name] = 'Translation supports de/en only.'
                continue
            unsupported_german = any(
                element['label'].strip() and element.get('language') != 'de'
                for element in labels
            )
            if 'openthesaurus' in engine.methods and unsupported_german:
                failed['openthesaurus'] = 'OpenThesaurus supports de only.'
                continue
            try:
                result = engine.match(case['reference'], case['student'])
                for name, matrix in result['scores'].items():
                    raw[name] = np.asarray(matrix).reshape(shape)
                for name, texts in result['processedLabels'].items():
                    usable[name] = nonempty_pairs(
                        texts['reference'], texts['student']
                    )

            except Exception as error:
                message = f'{type(error).__name__}: {error}'
                failed.update({name: message for name in engine.methods})
                errors.append({'case': case['id'], 'error': message})
        for name in sorted(available) + variants:
            item = dict(variant=name, case=case['id'], title=case['title'])
            requires = REQUIRES[name] if name in variants else (name,)
            missing = [n for n in requires if n not in raw]
            if missing:
                messages = sorted({failed[method] for method in missing})
                item.update(synonymMatrix=None, error='; '.join(messages))
                statuses.append((case['id'], name, 'nicht ausgeführt'))
            else:
                if name in variants:
                    scores = evaluate_variant(name, raw)
                else:
                    scores = np.clip(raw[name], 0, 1)
                eligible = np.logical_or.reduce([usable[n] for n in requires])
                selected_matrices = {method: raw[method] for method in requires}
                original_valid = nonempty_pairs(
                    [element['label'] for element in case['reference']],
                    [element['label'] for element in case['student']],
                )
                rows = build_candidates(
                    case['reference'], case['student'], selected_matrices,
                    scores, eligible & original_valid, threshold=None,
                )
                item['synonymMatrix'] = format_synonym_matrix(rows)
                result = evaluate_case(case, scores, threshold, eligible=eligible)
                evaluations.setdefault(name, []).append(result)
                status = 'leer, technisch geprüft' if not result['pairs'] else (
                    'OK' if result['all_correct'] else f"FP {result['fp']}, FN {result['fn']}")
                statuses.append((case['id'], name, status))
            records.append(item)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    write_overview(
        output, data, evaluations, statuses, threshold, preprocessing,
        time.perf_counter() - started, len(errors),
    )

    return errors


def write_overview(output, data, evaluations, statuses, threshold,
                   preprocessing, elapsed, error_count):
    """Schreibe die kompakte Übersicht neben die JSON-Datei."""
    overview = output.with_suffix('.md')
    # Die Auswertung verwendet ungerundete Scores; nur JSON wird gerundet.
    lines = ['# Vorläufiger Variantenvergleich', '',
             f'Threshold für die Auswertung: {threshold}; Matrizen bleiben ungefiltert.',
             f'Preprocessing: {preprocessing}. Seed: 42. Gesamtlaufzeit: {elapsed:.2f} s.',
             'Basisscores werden pro Fall einmal berechnet und zwischen Varianten geteilt.',
             'Synthetische Fälle, keine unabhängige Qualitätsbestätigung; '
             'kein Training oder Tuning.',
             'Bank mit verschiedenen Bedeutungen ist ohne Kontext nicht unterscheidbar.',
             'Top-1 ist bei Einzelpaaren trivial; deshalb zusätzlich Graphfall 21 separat.', '',
             '| Verfahren | Fälle mit Paaren | TP | FP | FN | Precision | Recall | F1 |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name, results in evaluations.items():
        m = summarize(results)
        nonempty_cases = sum(result['pairs'] > 0 for result in results)
        lines.append(
            f"| {name} | {nonempty_cases} | {m['tp']} | {m['fp']} | {m['fn']} "
            f"| {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} |"
        )
    lines += ['', '## Graphfall: Top-1', '']
    graph = None
    for case in data['cases']:
        if case['case_number'] == 21:
            graph = case
            break
    if graph:
        # Derive this from the already computed, unrounded evaluation records.
        for name in evaluations:
            case_ids = [
                case_id for case_id, variant, status in statuses
                if variant == name and status != 'nicht ausgeführt'
            ]
            if graph['id'] in case_ids:
                m = evaluations[name][case_ids.index(graph['id'])]
                lines.append(f"- {name}: {m['top1']}/{m['queries']}")
    lines += ['', '## Testfälle', '',
              '| Fall | vollständig richtige Verfahren / ausgeführt | nicht ausgeführt |',
              '| --- | ---: | ---: |']
    for case in data['cases']:
        states = [status for cid, _, status in statuses if cid == case['id']]
        skipped = states.count('nicht ausgeführt')
        correct = states.count('OK')
        if 'leer, technisch geprüft' in states:
            value = 'leer, technisch geprüft'
        else:
            value = f'{correct}/{len(states) - skipped}'
        lines.append(f"| {case['id']}: {case['title']} | {value} | {skipped} |")
    lines += ['', f'Technische Fehler: {error_count}. '
              'Nicht unterstützte Sprachen stehen direkt in der Matrixdatei.']
    overview.write_text('\n'.join(lines) + '\n')


def main():
    """Lies CLI-Optionen und starte den Vergleich mit festem Threshold."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=HERE / 'model-cases.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--models', action='store_true')
    parser.add_argument('--extended', action='store_true',
                        help='Preprocessing, weights, lexicon hybrids and assignments')
    parser.add_argument(
        '--lexicons', action='store_true', help='WordNet (DE→EN) and German OpenThesaurus')
    parser.add_argument(
        '--threshold', type=float, default=0.5, help='Evaluation only; matrices stay complete')
    parser.add_argument(
        '--preprocessing', nargs='*', default=None, help='Ordered steps; omit for normalize/lowercase')
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    if args.extended:
        if args.preprocessing is not None:
            parser.error('--extended uses predefined preprocessing comparisons')
        from synonym_matching.experiments import run_experiments
        errors = run_experiments(
            data, args.output, models=args.models, lexicons=args.lexicons,
            threshold=args.threshold,
        )
    else:
        errors = run(
            data, args.output, args.models, args.threshold,
            args.preprocessing, args.lexicons,
        )
    print(args.output)
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
