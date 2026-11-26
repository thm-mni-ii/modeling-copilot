"""Mische Ganzlabel- und Komponentenscores auf denselben gespeicherten Fällen."""

import argparse
import gzip
import json
from pathlib import Path
import time

import numpy as np

from synonym_matching.combinations import STRINGS, combine, string_ensemble
from .compare import sha256
from .evaluation import evaluate_case, select_matches
from .experiments import DEFAULT_CONFIG, ROOT, load_config
from .rank_results import build_rankings, rank


def read_result(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def run_comparison(whole_path, component_path, output, config):
    """Beide Zweige: 25 % String + 75 % Embedding, ohne Lexikon-/Konfliktregeln."""
    whole_path, component_path, output = map(Path, (whole_path, component_path, output))
    if output.exists():
        raise FileExistsError('choose a new output filename')
    whole, component = read_result(whole_path), read_result(component_path)
    for key in ('seed', 'threshold'):
        if whole[key] != component[key] or whole[key] != config[key]:
            raise ValueError(f'incompatible {key}')
    if whole['dataset']['cases'] != component['dataset']['cases']:
        raise ValueError('datasets, label order and annotations must match exactly')
    for name in ('translated_embedding', 'translation'):
        if whole['provenance']['models'][name] != component['provenance']['models'][name]:
            raise ValueError(f'incompatible model provenance: {name}')
    weights = config['whole_component_comparison']['whole_weights']
    definitions = {}
    for weight in weights:
        name = f'whole_{weight:g}_components_{1-weight:g}'
        definitions[name] = {
            'methods': ['whole_label', 'components'], 'preprocessing': ['normalize'],
            'chains': {'whole_label': ['whole_label'], 'components': ['components']},
            'combiner': {'kind': 'weighted_mean', 'weights': {'whole_label': weight,
                                                          'components': 1-weight}}}
    whole_features = {(f['case'], tuple(f['chain'])): f for f in whole['features']}
    component_features = {(f['case'], tuple(f['chain'])): f for f in component['features']}
    records, features, cases, excluded = [], [], [], []
    for case in whole['dataset']['cases']:
        cid = case['id']
        base = {name: whole_features.get((cid, ('normalize', name)))
                for name in (*STRINGS, 'translated_embedding')}
        part = component_features.get((cid, ('normalize', 'component_evidence')))
        if any(f is None or f['status'] != 'ok' for f in [*base.values(), part]):
            excluded.append({'case': cid, 'reason': 'missing successful normalize features in either branch'})
            continue
        shape = (len(case['reference']), len(case['student']))
        matrices = {name: np.asarray(f['scores']).reshape(shape) for name, f in base.items()}
        cf = part['component_features']
        scores = {
            'whole_label': .25 * string_ensemble(matrices)
                           + .75 * np.clip(matrices['translated_embedding'], 0, 1),
            'components': .25 * np.asarray(cf['string_similarity']).reshape(shape)
                          + .75 * np.clip(np.asarray(cf['embedding_similarity']).reshape(shape), 0, 1)}
        if any(not np.isfinite(a).all() for a in scores.values()):
            raise ValueError('nonfinite branch score')
        # Alle Gewichte, auch die Endpunkte, bekommen dieselben gültigen Kandidaten.
        eligible = np.logical_and.reduce([np.asarray(f['eligible']).reshape(shape).astype(bool)
                                           for f in [*base.values(), part]])
        for name in scores:
            features.append({'case': cid, 'chain': [name], 'method': name, 'status': 'ok',
                             'scores': scores[name].tolist(), 'eligible': eligible.tolist()})
        cases.append(case)
        for name, spec in definitions.items():
            started = time.perf_counter()
            merged = combine(scores, spec['combiner'])
            seconds = time.perf_counter() - started
            decisions = {}
            for strategy in config['strategies']:
                started = time.perf_counter()
                selected = select_matches(merged, eligible, config['threshold'], strategy)
                decisions[strategy] = {'selected': selected.tolist(),
                    'seconds': time.perf_counter() - started,
                    'metrics': evaluate_case(case, merged, config['threshold'],
                                             eligible=eligible, selected=selected)}
            records.append({'experiment': name, 'case': cid, 'status': 'ok', 'shape': list(shape),
                            'combinedScores': merged.tolist(), 'decisions': decisions,
                            'feature_seconds': 0., 'combine_seconds': seconds})
    if not cases:
        raise ValueError('no common successful cases')
    result = {'seed': config['seed'], 'threshold': config['threshold'],
              'config': config['whole_component_comparison'], 'dataset': {'cases': cases},
              'excluded_cases': excluded, 'definitions': definitions, 'features': features,
              'records': records, 'provenance': component['provenance'],
              'sources': {name: {'path': str(path), 'sha256': sha256(path)} for name, path in
                          [('whole', whole_path), ('components', component_path)]},
              'source_hash': sha256(Path(__file__)),
              'score_policy': 'Each branch: 25% normalized original-label strings + 75% translated '
                              'embedding; no lexicon or conflict rules. Fixed threshold, no tuning.',
              'timing_policy': 'Mixing and assignment only; branch features reused, zero new feature time.'}
    result['rankings'] = build_rankings(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if output.suffix == '.gz' else open
    with opener(output, 'wt', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    for cohort in config['whole_component_comparison']['datasets']:
        result = run_comparison(ROOT / cohort['whole'], ROOT / cohort['components'],
                                ROOT / cohort['output'], config)
        ranking = result['rankings'].get('changed_labels', result['rankings'])
        rows = ranking['overall_complete']['top3']
        print(f'\n{cohort["name"]}: beste F1 {rows[0]["metrics"]["f1"]:.4f}; '
              f'ausgeschlossene Fälle: {len(result["excluded_cases"])}')
        # Alle fünf Einstellungen anzeigen, nicht nur die Top 3.
        view = result
        if 'changed_labels' not in result['rankings']:
            for row in rank(view, {c['id'] for c in result['dataset']['cases']}, list(result['definitions'])):
                m = row['metrics']
                w = result['definitions'][row['pipeline']]['combiner']['weights']['whole_label']
                print(f'{w:.0%} Ganzlabel + {1-w:.0%} Komponenten: P={m["precision"]:.4f} R={m["recall"]:.4f} '
                      f'F1={m["f1"]:.4f} TP={m["tp"]} FP={m["fp"]}')
        else:
            from .rank_results import changed_label_rankings
            for name in result['definitions']:
                only = {**result, 'definitions': {name: result['definitions'][name]},
                        'records': [r for r in result['records'] if r['experiment'] == name]}
                row = changed_label_rankings(only, 'threshold')['overall_complete']['top3'][0]
                m = row['metrics']
                w = result['definitions'][name]['combiner']['weights']['whole_label']
                print(f'{w:.0%} Ganzlabel + {1-w:.0%} Komponenten: P={m["precision"]:.4f} R={m["recall"]:.4f} '
                      f'F1={m["f1"]:.4f} TP={m["tp"]} FP={m["fp"]}')
        print(cohort['output'])


if __name__ == '__main__':
    main()
