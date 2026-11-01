"""Compare fixed methods on the 28 requested categories: JSON matrices and terminal summary."""
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
from research.evaluation import evaluate_case, summarize
from synonym_matching.variants import REQUIRES, evaluate_variant

HERE = Path(__file__).resolve().parent
STRINGS = ['levenshtein', 'damerau_levenshtein', 'jaro_winkler', 'char_bigram',
           'char_trigram', 'token_jaccard', 'token_sort_ratio', 'word_order', 'exact_match']


def run(data, output, models=False, threshold=0.5, preprocessing=None, lexicons=False):
    """Vergleiche Methoden auf denselben Fällen; speichere JSON und zeige die Übersicht im Terminal."""
    if (type(threshold) not in (int, float)
            or not np.isfinite(threshold) or not 0 <= threshold <= 1):
        raise ValueError('threshold must be in [0,1]')
    output = Path(output)
    if output.exists():
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
                item['metrics'] = result
                evaluations.setdefault(name, []).append(result)
            records.append(item)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(f'Threshold: {threshold}; Laufzeit: {time.perf_counter() - started:.2f}s')
    for name, results in evaluations.items():
        stats = summarize(results)
        print(f"{name}: P={stats['precision']:.3f} R={stats['recall']:.3f} "
              f"F1={stats['f1']:.3f}; {len(results)} Fälle")
    print('Unterschiedliche Abdeckung beachten; Gesamtwerte sind nicht direkt vergleichbar.')
    print(f'Technische Fehler: {len(errors)}')
    return errors


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
        from research.experiments import run_experiments
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
