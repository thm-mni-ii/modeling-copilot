"""Path-/Wu-Palmer-Ablationen auf gespeicherten Jina-Scores, ohne Modellladen."""

import argparse
import gzip
import json
from pathlib import Path
import time

import numpy as np

from .compare import sha256
from .compare_embeddings import evaluate, tree_scores
from .decision_tree import _read, production_modules
from .evaluation import nonempty_pairs
from .experiments import DEFAULT_CONFIG, ROOT, load_config


def diagnostic_rows(case, feature, baseline, source, *, changed):
    """Unbekannt/unverbunden separat von niedriger vorhandener Ähnlichkeit halten."""
    shape = (len(case['reference']), len(case['student']))
    values = {k: np.asarray(v).reshape(shape) for k, v in feature['lexicons'][source].items()}
    mask = nonempty_pairs([e['label'] for e in case['reference']], [e['label'] for e in case['student']])
    if changed:
        mask &= np.asarray([e['id'] in case.get('changed_student_ids', [])
                            for e in case['student']], dtype=bool)[None, :]
    reasons = np.asarray(baseline['reasons']).reshape(shape)
    predictions = np.asarray(baseline['scores']).reshape(shape)
    rows = []
    for i, j in zip(*np.where(mask)):
        available = values['pair_known'][i, j] == values['taxonomy_available'][i, j] == 1
        rows.append({'case': case['id'], 'reference': case['reference'][i],
            'student': case['student'][j], 'correct': case['annotations'][i][j] == 'correct',
            'confirmed': bool(predictions[i, j]), 'reason': str(reasons[i, j]),
            'pair_known': bool(values['pair_known'][i, j]), 'taxonomy_available': bool(available),
            'single_sense': bool(values['reference_synset_count'][i, j] == values['student_synset_count'][i, j] == 1),
            **{metric: float(values[metric][i, j]) if available else None
               for metric in ('path_similarity', 'wup_similarity')}})
    return rows


def distributions(rows):
    """Abdeckung und Verteilungen für Goldlabels sowie bestätigte Paare ausgeben."""
    groups = {'correct': lambda r: r['correct'], 'incorrect': lambda r: not r['correct'],
              'true_positives': lambda r: r['correct'] and r['confirmed'],
              'false_positives': lambda r: not r['correct'] and r['confirmed'],
              'meaning_correct': lambda r: r['correct'] and r['reason'] == 'meaning',
              'meaning_incorrect': lambda r: not r['correct'] and r['reason'] == 'meaning'}
    output = {}
    for name, select in groups.items():
        selected = [r for r in rows if select(r)]
        available = [r for r in selected if r['taxonomy_available']]
        output[name] = {'pairs': len(selected), 'pair_known': sum(r['pair_known'] for r in selected),
            'taxonomy_available': len(available), 'single_sense_available': sum(r['single_sense'] for r in available),
            'coverage': len(available) / len(selected) if selected else 0,
            **{metric: dict(zip(('min', 'q25', 'median', 'q75', 'max'),
                     np.quantile([r[metric] for r in available], [0, .25, .5, .75, 1]).tolist()))
                if available else None for metric in ('path_similarity', 'wup_similarity')}}
    return output


def run(config, output):
    settings = config['taxonomy_comparison']
    if output.exists():
        raise FileExistsError('choose a new output filename')
    path = ROOT / settings['source']
    saved = _read(path)
    if saved['seed'] != config['seed']:
        raise ValueError('seed differs from saved source')
    _, adapter = production_modules()
    policies = {'baseline': (None, True)}
    for scope, single in [('single', True), ('covered', False)]:
        for name, policy in [('path', {'path_similarity': settings['path_minimum']}),
                             ('wup', {'wup_similarity': settings['wup_minimum']}),
                             ('both', {'path_similarity': settings['path_minimum'],
                                       'wup_similarity': settings['wup_minimum']})]:
            policies[f'{name}_{scope}'] = policy, single
    result = {'seed': config['seed'], 'config': settings, 'model': saved['models'][settings['model']],
        'source': {'path': str(path), 'sha256': sha256(path)}, 'datasets': {},
        'source_hashes': {str(p): sha256(p) for p in [Path(__file__), Path(__file__).with_name('decision_tree.py'),
                                                    Path(__file__).with_name('compare_embeddings.py')]},
        'policy': 'Known development data, fixed diagnostic thresholds, no model/threshold tuning. '
                  'Taxonomy can only move embedding confirmations to open; never confirms synonymy alone. '
                  'single=previous unique-sense guard, covered=all known connected pairs, possibly ambiguous. '
                  'Path/Wu-Palmer are independent maxima across senses, not WSD or the same sense pair. '
                  'Unknown/unconnected stays baseline. Top-1 omitted for binary tree verdicts; raw ranking unchanged.'}
    for dataset_name, dataset in saved['datasets'].items():
        source = ROOT / dataset['source']['path']
        if sha256(source) != dataset['source']['sha256']:
            raise ValueError('lexicon source changed since embedding comparison')
        lexical = _read(source)
        cases = dataset['dataset']['cases']
        if cases != lexical['dataset']['cases']:
            raise ValueError('dataset differs from saved lexicon source')
        changed = any(c.get('changed_student_ids') for c in cases)
        model = dataset['models'][settings['model']]
        output_dataset = {'thresholds': {}}
        for threshold in settings['thresholds']:
            key = str(threshold)
            baseline = model['tree_predictions'][key]
            records = {name: {source: [] for source in baseline} for name in policies}
            diagnostics = {source: [] for source in baseline}
            started = time.perf_counter()
            for case, feature, raw in zip(cases, lexical['features'], model['records'], strict=True):
                if case['id'] != feature['case'] or case['id'] != raw['case']:
                    raise ValueError('case order mismatch')
                scores = np.asarray(raw['scores']).reshape(len(case['reference']), len(case['student']))
                for variant, (policy, single) in policies.items():
                    for source, prediction in tree_scores(case, feature, scores, threshold, lexical['config'],
                            adapter, taxonomy_policy=policy, taxonomy_single_sense=single).items():
                        index = len(records[variant][source])
                        if variant == 'baseline':
                            if prediction != baseline[source][index]:
                                raise ValueError('baseline decisions/reasons were not reproduced exactly')
                            diagnostics[source] += diagnostic_rows(case, feature, prediction, source, changed=changed)
                        records[variant][source].append(prediction)
            summaries = {}
            for variant, sources in records.items():
                summaries[variant] = {}
                for source, predictions in sources.items():
                    metrics = evaluate(cases, predictions, .5, changed=changed)
                    for k in ('top1', 'queries', 'top1_accuracy'):
                        metrics.pop(k)
                    base = summaries['baseline'][source] if variant != 'baseline' else metrics
                    metrics['removed_false_positives'] = base['fp'] - metrics['fp']
                    metrics['lost_true_positives'] = base['tp'] - metrics['tp']
                    summaries[variant][source] = metrics
                    print(f'{dataset_name} / {source} / {threshold:.2f} / {variant}: '
                          f'P={metrics["precision"]:.4f} R={metrics["recall"]:.4f} F1={metrics["f1"]:.4f} '
                          f'TP={metrics["tp"]} FP={metrics["fp"]}', flush=True)
            output_dataset['thresholds'][key] = {'summary': summaries, 'predictions': records,
                'diagnostics': {source: {'groups': distributions(rows), 'pairs': rows}
                                for source, rows in diagnostics.items()},
                'seconds': time.perf_counter() - started}
        result['datasets'][dataset_name] = output_dataset
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, 'wt', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False)
    print(output, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    run(config, args.output or ROOT / config['taxonomy_comparison']['output'])


if __name__ == '__main__':
    main()
