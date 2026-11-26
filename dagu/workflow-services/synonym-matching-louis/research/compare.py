"""Ein Befehl: aktuelle Pipelines auf frischen Labels bei 0,80/0,85/0,90 vergleichen."""

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import random
import time

import numpy as np

from synonym_matching import MatchingPipeline
from .evaluation import evaluate_case, summarize

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def case_metrics(case, data, output, *, changed):
    """Labor: geänderte Schülerlabels gegen alle Referenzkandidaten, sonst volle Mengen."""
    shape = (len(case['reference']), len(case['student']))
    predicted = np.asarray([[m['verdict'] == 'confirmed' for m in row['matches']]
                            for row in output['synonymMatrix']], dtype=float).reshape(shape)
    scores = np.asarray([[m['embedding_similarity'] for m in row] for row in data['scores']]).reshape(shape)
    if changed:
        columns = [j for j, e in enumerate(case['student']) if e['id'] in case.get('changed_student_ids', [])]
        if not columns:
            return None
        case = {**case, 'reference': [case['student'][j] for j in columns], 'student': case['reference'],
                'annotations': [[row[j] for row in case['annotations']] for j in columns]}
        predicted, scores = predicted.T[columns], scores.T[columns]
    metrics = evaluate_case(case, predicted, .5)
    # Keine Top-1 aus binären Entscheidungen: Rangliste stammt nur vom Embedding.
    ranking = evaluate_case(case, scores, .5)
    metrics.update(top1=ranking['top1'], queries=ranking['queries'])
    return metrics


def run(config_path, output_path, *, only=None):
    if output_path.exists():
        raise FileExistsError('choose a new output filename')
    config = json.loads(config_path.read_text())
    random.seed(config['seed'])
    np.random.seed(config['seed'])
    pipelines = {k: v for k, v in config['pipelines'].items() if not only or k in only}
    if not pipelines or (only and set(only) - pipelines.keys()):
        raise ValueError('unknown or empty pipeline selection')
    for threshold in config['thresholds']:
        MatchingPipeline._validate_thresholds(threshold)
    datasets = {Path(name).stem: json.loads((config_path.parent/name).read_text()) for name in config['datasets']}
    result = {'seed': config['seed'], 'config': config, 'datasets': datasets, 'runs': {},
        'source_hashes': {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT/'src').rglob('*.py'))},
        'runner_hashes': {str(p): sha256(p) for p in (Path(__file__), Path(__file__).with_name('evaluation.py'), config_path)},
        'data_hashes': {name: sha256(config_path.parent/name) for name in config['datasets']},
        'packages': {name: version(name) for name in ('numpy', 'rapidfuzz', 'torch', 'sentence-transformers', 'transformers', 'wn', 'lingua-language-detector')},
        'resources': {'odenet': 'odenet:1.4', 'wordnet': 'omw-en:1.4', 'lingua_minimum_relative_distance': .2},
        'policy': 'Known development data. No language annotation used by pipeline. '
                  'No held-out quality claim. Full matrix, unrounded decisions. '
                  'Top-1 is raw embedding ranking, not binary tree ranking. '
                  'Models/lexicons/label embeddings reused within each run.'}
    for name, options in pipelines.items():
        pipeline = MatchingPipeline(**options)
        runs = {}
        for dataset_name, dataset in datasets.items():
            changed = any(c.get('changed_student_ids') for c in dataset['cases'])
            metrics = {str(t): [] for t in config['thresholds']}
            cases = []
            started = time.perf_counter()
            for case in dataset['cases']:
                before = time.perf_counter()
                data = pipeline.features(case['reference'], case['student'])
                feature_seconds = time.perf_counter() - before
                outputs = {}
                for threshold in config['thresholds']:
                    output = pipeline.from_features(data, meaning_threshold=threshold, decimals=None)
                    outputs[str(threshold)] = output
                    m = case_metrics(case, data, output, changed=changed)
                    if m is not None:
                        metrics[str(threshold)].append(m)
                cases.append({'id': case['id'], 'features': data, 'feature_seconds': feature_seconds, 'outputs': outputs})
            summary = {t: summarize(values) for t, values in metrics.items()}
            for threshold, m in summary.items():
                m['top1_accuracy'] = m['top1'] / m['queries'] if m['queries'] else 0
                print(f'{dataset_name} / {name} / {threshold}: TP={m["tp"]} FP={m["fp"]} '
                      f'P={m["precision"]:.4f} R={m["recall"]:.4f} F1={m["f1"]:.4f}', flush=True)
            runs[dataset_name] = {'summary': summary, 'seconds': time.perf_counter() - started, 'cases': cases}
        result['runs'][name] = {'options': options, 'model': pipeline.embedding.metadata(), 'datasets': runs}
        if 'lexicon_database_sha256' not in result['resources']:
            database = pipeline.lexicons.backends['de'].path/'wn.db'
            result['resources']['lexicon_database_sha256'] = sha256(database)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False)
    print(output_path, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('experiments.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    run(args.config, args.output, only=args.only)


if __name__ == '__main__':
    main()
