"""Vergleiche konfigurierte Komponentenfusionen auf gespeicherten Merkmalen, ohne Modelle."""

import argparse
import gzip
import json
import time
from pathlib import Path

import numpy as np

from synonym_matching.combinations import component_evidence_fusion
from .compare import sha256
from .evaluation import evaluate_case, select_matches
from .experiments import DEFAULT_CONFIG, ROOT, configurations, load_config
from .rank_results import build_rankings, print_rankings


def run_sweep(source, output, config):
    """Verwende denselben Datenstand und dieselben Merkmale für alle Gewichte."""
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError('choose a new output filename')
    opener = gzip.open if source.suffix == '.gz' else open
    with opener(source, 'rt', encoding='utf-8') as stream:
        payload = json.load(stream)
    if payload['threshold'] != config['threshold'] or payload['seed'] != config['seed']:
        raise ValueError('source and config must use the same threshold and seed')
    definitions, skipped = configurations(config)
    selected = {name: spec for name, spec in definitions.items()
                if spec['combiner']['kind'] == 'component_evidence'}
    if not selected:
        raise ValueError('no component evidence experiments configured')
    features = {(tuple(f['chain']), f['case']): f for f in payload['features']}
    # Komponenten-Basis ist bereits als Rasterpunkt ohne Lexikon/Regeln enthalten.
    baselines = {name: spec for name, spec in payload['definitions'].items()
                 if 'component_evidence' not in spec['methods']}
    records = [r for r in payload['records'] if r['experiment'] in baselines]
    started = time.perf_counter()
    for name, spec in selected.items():
        chain = tuple(spec['chains']['component_evidence'])
        for case in payload['dataset']['cases']:
            part = features.get((chain, case['id']))
            if part is None or part['status'] != 'ok':
                raise ValueError(f'missing successful component features: {chain}, {case["id"]}')
            shape = (len(case['reference']), len(case['student']))
            values = {key: np.asarray(v).reshape(shape)
                      for key, v in part['component_features'].items()}
            eligible = np.asarray(part['eligible'], dtype=bool).reshape(shape)
            t0 = time.perf_counter()
            scores = component_evidence_fusion(values, **spec['combiner']['options'])
            combination_seconds = time.perf_counter() - t0
            decisions = {}
            for strategy in config['strategies']:
                t0 = time.perf_counter()
                chosen = select_matches(scores, eligible, config['threshold'], strategy)
                decisions[strategy] = {
                    'selected': chosen.tolist(), 'seconds': time.perf_counter() - t0,
                    'metrics': evaluate_case(case, scores, config['threshold'],
                                             eligible=eligible, selected=chosen)}
            records.append({'experiment': name, 'case': case['id'], 'status': 'ok',
                            'shape': list(shape), 'combinedScores': scores.tolist(),
                            'decisions': decisions, 'feature_seconds': 0.,
                            'original_feature_seconds': part['seconds'],
                            'combine_seconds': combination_seconds})
    payload.update(config=config, selected_experiments=list(selected),
                   definitions={**baselines, **selected}, skipped_definitions=skipped,
                   records=records, elapsed_seconds=time.perf_counter() - started,
                   feature_source={'path': str(source), 'sha256': sha256(source)},
                   timing_policy='New records: fusion/assignment only; features reused, no model time. '
                                 'Retained baseline timings are historical, not comparable.',
                   fusion_source_hashes={str(path.relative_to(ROOT)): sha256(path) for path in
                       [Path(__file__), Path(__file__).with_name('experiments.py'),
                        ROOT / 'src/synonym_matching/combinations.py']})
    # Die bisherige provenance beschreibt ausdrücklich die gespeicherte Merkmalsberechnung.
    payload['rankings'] = {'threshold': build_rankings(payload, 'threshold')}
    output.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if output.suffix == '.gz' else open
    with opener(output, 'wt', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        stream.write('\n')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    result = run_sweep(args.features, args.output, load_config(args.config))
    print_rankings(result['rankings']['threshold'])
    print(f'Gespeichert: {args.output}; {len(result["selected_experiments"])} Fusionen, keine Modellläufe.')


if __name__ == '__main__':
    main()
