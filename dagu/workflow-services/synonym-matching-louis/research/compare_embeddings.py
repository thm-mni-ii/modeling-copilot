"""Vergleiche Embeddings bei unveränderten Labels, Lexikonmerkmalen und Regeln."""

import argparse
import gc
import gzip
import json
from importlib.metadata import version
from pathlib import Path
import random
import time

import numpy as np

from synonym_matching.cache import Cache
from synonym_matching.methods import EmbeddingMethod, EMBEDDING_MODELS, JINA_CODE_REVISION
from synonym_matching.preprocessing import normalize
from .compare import sha256
from .decision_tree import _read, decide, production_modules
from .evaluation import evaluate_case, summarize, nonempty_pairs
from .experiments import DEFAULT_CONFIG, ROOT, load_config


def evaluate(cases, records, threshold, *, changed=False):
    """Labor: geänderte Schülerlabels gegen alle Referenzkandidaten auswerten."""
    metrics = []
    for case, record in zip(cases, records, strict=True):
        values = np.asarray(record['scores']).reshape(len(case['reference']), len(case['student']))
        if changed:
            columns = [j for j, item in enumerate(case['student'])
                       if item['id'] in case.get('changed_student_ids', [])]
            if not columns:
                continue
            case = {**case, 'reference': [case['student'][j] for j in columns],
                    'student': case['reference'],
                    'annotations': [[row[j] for row in case['annotations']] for j in columns]}
            values = values.T[columns]
        metrics.append(evaluate_case(case, values, threshold))
    result = summarize(metrics)
    result['top1_accuracy'] = result['top1'] / result['queries'] if result['queries'] else 0
    return result


def tree_scores(case, feature, scores, threshold, settings, adapter, *,
                taxonomy_policy=None, taxonomy_single_sense=True, decision_options=None):
    """Ersetze ausschließlich die Embedding-Matrix; behalte den Textadapter bei."""
    raw = {'damerau_canonical': np.asarray(feature['scores']['damerau_canonical']),
           'multilingual_expanded': scores}
    # Leere Achsen behalten, auch wenn JSON [] die zweite Dimension nicht enthält.
    shape = (len(case['reference']), len(case['student']))
    raw = {key: value.reshape(shape) for key, value in raw.items()}
    candidate = {'methods': [{'name': key, 'scoreRange': [-1, 1] if key == 'multilingual_expanded' else [0, 1]} for key in raw],
        'synonymMatrix': [{'referenceElementId': a['id'], 'referenceLabel': a['label'],
            'matches': [{'submissionElementId': b['id'], 'submissionLabel': b['label'],
                         'scoreStatus': 'scored', 'scores': {key: float(v[i, j]) for key, v in raw.items()}}
                        for j, b in enumerate(case['student'])]}
            for i, a in enumerate(case['reference'])]}
    options = dict(decision_options or {})
    tiers = [{'name': 'canonical', 'minimumSimilarity': {'damerau_canonical': 1.}},
             {'name': 'spelling', 'minimumSimilarity': {'damerau_canonical': settings['thresholds']['spelling']}},
             {'name': 'meaning', 'minimumSimilarity': {'multilingual_expanded': threshold},
              'confirmationFloor': {'multilingual_expanded': min(threshold, settings['thresholds']['meaning_floor'])}}]
    evidence = adapter.pair_similarity(candidate, adapter.configured_tiers(candidate, {'textEvidence': {'tiers': tiers}}))
    output = {}
    for source, features in feature['lexicons'].items():
        values = {key: np.asarray(v).reshape(shape) for key, v in features.items()}
        predictions = np.zeros(shape)
        reasons = np.full(shape, '', dtype=object)
        for i, a in enumerate(case['reference']):
            for j, b in enumerate(case['student']):
                verdict, reasons[i, j] = decide({key: float(v[i, j]) for key, v in values.items()},
                    evidence[a['id'], b['id']], valid=bool(a['label'].strip() and b['label'].strip()),
                    require_single_synset=settings.get('require_single_synset', False),
                    shared_synset_first=settings.get('shared_synset_first', True),
                    taxonomy_policy=taxonomy_policy, taxonomy_single_sense=taxonomy_single_sense,
                    exact_equal=normalize(a['label']).lower() == normalize(b['label']).lower(),
                    **options)
                predictions[i, j] = verdict == 'confirmed'
        output[source] = {'scores': predictions.tolist(), 'reasons': reasons.tolist()}
    return output


def run(config, output):
    """Lade jedes Modell einmal; gleiche Vorverarbeitung wie im bisherigen Baum."""
    if output.exists():
        raise FileExistsError('choose a new output filename')
    settings = config['embedding_comparison']
    random.seed(config['seed'])
    np.random.seed(config['seed'])
    registry, adapter = production_modules()
    preprocessing = registry.resolve_methods(['multilingual_expanded'])[0].preprocessing
    datasets = []
    for item in config['decision_tree']['datasets']:
        path = ROOT / item['output']
        saved = _read(path)
        if saved['seed'] != config['seed']:
            raise ValueError('seed differs from saved source')
        datasets.append((item['name'], saved, {'path': str(path), 'sha256': sha256(path)}))
    results = {'seed': config['seed'], 'config': settings, 'preprocessing': list(preprocessing),
               'packages': {p: version(p) for p in ('sentence-transformers', 'transformers', 'torch', 'numpy')},
               'models': {}, 'datasets': {}, 'source_hashes': {str(p): sha256(p) for p in
                   [Path(__file__), ROOT/'src/synonym_matching/methods.py', ROOT/'research/decision_tree.py']},
               'policy': 'Development comparison, no held-out quality claim. Threshold grid is diagnostic, '
                         'not validation. Top-1 only from raw scores; binary tree decisions have no Top-1. '
                         'Same saved expanded labels and lexicons for every model; original schema/defaults unchanged.'}
    for name in settings['models']:
        if name not in EMBEDDING_MODELS:
            raise ValueError(f'unknown embedding model: {name}')
        backend = EmbeddingMethod(name, {}, Cache())
        started = time.perf_counter()
        backend._load()
        load_seconds = time.perf_counter() - started
        results['models'][name] = {'model': EMBEDDING_MODELS[name], 'revision': backend.revision,
            'load_seconds': load_seconds, 'input_prefix': 'query: ' if name == 'e5_base' else '',
            'code_revision': JINA_CODE_REVISION if name == 'jina_de' else None}
        for dataset_name, saved, source in datasets:
            cases = saved['dataset']['cases']
            records, trees = [], {str(t): {} for t in settings['thresholds']}
            started = time.perf_counter()
            for case, feature in zip(cases, saved['features'], strict=True):
                if case['id'] != feature['case']:
                    raise ValueError('feature/case order mismatch')
                sides = []
                for side in ('reference', 'student'):
                    texts = [e['label'] for e in feature['comparison_labels'][side]]
                    for step in preprocessing:
                        texts = [registry.PREPROCESSORS[step](text) for text in texts]
                    sides.append(texts)
                before = time.perf_counter()
                scores = backend.matrix(*sides)
                valid = nonempty_pairs(*sides)
                if name == 'multilingual' and not np.allclose(scores[valid],
                        np.asarray(feature['scores']['multilingual_expanded']).reshape(scores.shape)[valid], atol=1e-6):
                    raise ValueError('baseline scores differ from saved comparison')
                records.append({'case': case['id'], 'scores': scores.tolist(),
                                'seconds': time.perf_counter() - before})
                for threshold in settings['thresholds']:
                    for lexicon, prediction in tree_scores(case, feature, scores, threshold,
                                                          saved['config'], adapter).items():
                        trees[str(threshold)].setdefault(lexicon, []).append(prediction)
            changed = any(case.get('changed_student_ids') for case in cases)
            summary = {}
            for threshold in settings['thresholds']:
                summary[str(threshold)] = {'raw': evaluate(cases, records, threshold, changed=changed),
                    'tree': {lexicon: evaluate(cases, predictions, .5, changed=changed)
                             for lexicon, predictions in trees[str(threshold)].items()}}
                for metrics in summary[str(threshold)]['tree'].values():
                    for key in ('top1', 'queries', 'top1_accuracy'):
                        metrics.pop(key)
            results['datasets'].setdefault(dataset_name, {'source': source, 'dataset': saved['dataset'],
                                                           'models': {}})['models'][name] = {
                'seconds': time.perf_counter() - started,
                'embedding_seconds': sum(r['seconds'] for r in records), 'records': records,
                'tree_predictions': trees, 'summary': summary}
            m = summary['0.85']['raw'] if '0.85' in summary else next(iter(summary.values()))['raw']
            print(f'{dataset_name} / {name}: raw TP={m["tp"]} FP={m["fp"]} F1={m["f1"]:.4f} '
                  f'Top-1={m["top1_accuracy"]:.4f}', flush=True)
        del backend
        gc.collect()
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, 'wt', encoding='utf-8') as stream:
        json.dump(results, stream, ensure_ascii=False, allow_nan=False)
    print(output, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    run(config, args.output or ROOT / config['embedding_comparison']['output'])


if __name__ == '__main__':
    main()
