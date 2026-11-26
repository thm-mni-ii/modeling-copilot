"""DE/EN-Erkennung und Lexikonrouting gegen OdeNet-only, ohne neue Embeddings."""

import argparse
from collections import Counter
import gzip
from importlib.metadata import version
import json
from pathlib import Path
import time

import numpy as np

from .compare import sha256
from .compare_component_lexicons import LexiconSources
from .compare_embeddings import evaluate, tree_scores
from .decision_tree import _read, production_modules
from .experiments import DEFAULT_CONFIG, ROOT, load_config


class LanguageDetection:
    """Lingua nur mit DE/EN; Ergebnis und Konfidenzen einmal je Originaltext."""

    def __init__(self, minimum_relative_distance):
        from lingua import Language, LanguageDetectorBuilder
        self.detector = (LanguageDetectorBuilder.from_languages(Language.GERMAN, Language.ENGLISH)
                         .with_minimum_relative_distance(minimum_relative_distance).build())
        self.cache = {}

    def detect(self, text):
        if text not in self.cache:
            language = self.detector.detect_language_of(text) if text.strip() else None
            confidence = self.detector.compute_language_confidence_values(text) if text.strip() else []
            self.cache[text] = {'language': language.iso_code_639_1.name.lower() if language else None,
                'confidence': {item.language.iso_code_639_1.name.lower(): item.value for item in confidence}}
        return self.cache[text]


def odenet_first_routes(detections, known):
    """OdeNet-Treffer bevorzugen; sonst nur sicher erkanntes Englisch zulassen."""
    return [{**d, 'allowed_lexicons': ['de'] if found else ['en'] if d['language'] == 'en' else []}
            for d, found in zip(detections, known, strict=True)]


def allowed_lexicons(detection):
    """Explizite Quellenwahl oder die bisherige Lingua-Regel verwenden."""
    if 'allowed_lexicons' in detection:
        return set(detection['allowed_lexicons'])
    return {detection['language']} if detection['language'] else {'de', 'en'}


def route_features(candidates, left, right):
    """Je Paar nur Quellen verwenden, die zu beiden erkannten Sprachen passen.

    Unsicher erlaubt DE und EN. Keine sprachübergreifende Synsetabbildung.
    Bei zwei Quellen gewinnt gemeinsame Bedeutung nur ohne Gegenrelation;
    alleinige Gegenrelation bei unsicherer Quellenwahl bleibt ebenfalls offen.
    Kein Maximalwert-Mischen von Synsets/Taxonomie verschiedener Lexika.
    """
    shape = (len(left), len(right))
    result = {key: np.zeros(shape) for key in candidates['de']}
    conflicts = np.zeros(shape, dtype=bool)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            allowed = allowed_lexicons(a) & allowed_lexicons(b)
            known = [lang for lang in sorted(allowed) if candidates[lang]['pair_known'][i, j] == 1]
            positives = [lang for lang in known if candidates[lang]['shared_synset'][i, j] == 1]
            negatives = [lang for lang in known if any(candidates[lang][k][i, j] == 1
                        for k in ('antonym', 'reference_hypernym', 'reference_hyponym'))]
            conflicts[i, j] = len(allowed) > 1 and bool(negatives)
            choice = next(iter(positives or negatives or known), None)
            if choice:
                for key in result:
                    result[key][i, j] = candidates[choice][key][i, j]
    return result, conflicts


def run(config, output):
    settings = config['lingua_comparison']
    if output.exists():
        raise FileExistsError('choose a new output filename')
    path = ROOT / settings['source']
    saved = _read(path)
    if saved['seed'] != config['seed']:
        raise ValueError('seed differs from saved source')
    detector = LanguageDetection(settings['minimum_relative_distance'])
    lexicons = LexiconSources()
    _, adapter = production_modules()
    result = {'seed': config['seed'], 'config': settings, 'lingua_version': version('lingua-language-detector'),
        'model': saved['models'][settings['model']],
        'source': {'path': str(path), 'sha256': sha256(path)}, 'datasets': {},
        'source_hashes': {str(p): sha256(p) for p in [Path(__file__), Path(__file__).with_name('decision_tree.py'),
                        Path(__file__).with_name('compare_embeddings.py'), Path(__file__).with_name('compare_component_lexicons.py')]},
        'policy': 'DE/EN assumed. Original label only for detection; supplied language used only for diagnostics. '
                  'Saved string/Jina scores and expanded comparison labels held fixed, including previous '
                  'language-informed abbreviation preprocessing: isolates lexicon routing, not end-to-end language-free. '
                  'No translation or ILI. Different confident languages: unknown lexical evidence. '
                  'Uncertain: both sources, counterrelation evidence leaves pair open. '
                  'odenet_first: per-label OdeNet lookup overrides detector, otherwise confident English selects '
                  'WordNet, other cases no lexical evidence. Known development data; '
                  'configured relative distance is an unvalidated experimental setting.'}
    for dataset_name, dataset in saved['datasets'].items():
        source = Path(dataset['source']['path'])
        if sha256(source) != dataset['source']['sha256']:
            raise ValueError('lexicon source changed')
        lexical = _read(source)
        cases = dataset['dataset']['cases']
        if cases != lexical['dataset']['cases']:
            raise ValueError('dataset differs')
        model = dataset['models'][settings['model']]
        records = {str(t): {v: [] for v in settings['variants']} for t in settings['thresholds']}
        features, language_rows, changes = [], [], []
        started = time.perf_counter()
        for case, feature, raw in zip(cases, lexical['features'], model['records'], strict=True):
            if case['id'] != feature['case'] or case['id'] != raw['case']:
                raise ValueError('case order differs')
            detections = {}
            for side in ('reference', 'student'):
                detections[side] = [detector.detect(e['label']) for e in case[side]]
                language_rows += [{'case': case['id'], 'side': side, 'id': e['id'], 'label': e['label'],
                    'annotated_language': e.get('language'), **d} for e, d in zip(case[side], detections[side], strict=True)
                    if e['label'].strip()]
            candidates = {}
            for lang in ('de', 'en'):
                sides = [[{**e, 'language': lang} for e in feature['comparison_labels'][side]]
                         for side in ('reference', 'student')]
                shared, values, _ = lexicons.matrices(*sides)
                candidates[lang] = {**values, 'shared_synset': shared}
            routes = {}
            for side in ('reference', 'student'):
                known = [bool(lexicons.backends['de'].lookup(e['label']))
                         for e in feature['comparison_labels'][side]]
                routes[side] = odenet_first_routes(detections[side], known)
            routing = {'lingua': detections, 'odenet_first': routes}
            routed_features, conflict_masks = {}, {}
            for name, sides in routing.items():
                routed, conflicts = route_features(candidates, sides['reference'], sides['student'])
                routed_features[name] = {k: v.tolist() for k, v in routed.items()}
                conflict_masks[name] = conflicts
            new_feature = {**feature, 'lexicons': routed_features}
            features.append({'case': case['id'], 'detections': detections,
                'lexicons': {lang: {k: v.tolist() for k, v in fs.items()} for lang, fs in candidates.items()},
                'routes': routes, 'routed': routed_features,
                'conflicts': {name: mask.tolist() for name, mask in conflict_masks.items()}})
            shape = (len(case['reference']), len(case['student']))
            for threshold in settings['thresholds']:
                key = str(threshold)
                base = model['tree_predictions'][key]['odenet'][len(records[key]['odenet'])]
                reproduced = tree_scores(case, feature, np.asarray(raw['scores']), threshold, lexical['config'], adapter)['odenet']
                if reproduced != base:
                    raise ValueError('baseline decisions/reasons not reproduced')
                records[key]['odenet'].append(base)
                predictions = tree_scores(case, new_feature, np.asarray(raw['scores']), threshold, lexical['config'], adapter)
                for name in settings['variants']:
                    if name == 'odenet':
                        continue
                    prediction = predictions[name]
                    for i, j in zip(*np.where(conflict_masks[name])):
                        if case['reference'][i]['label'].strip() and case['student'][j]['label'].strip():
                            prediction['scores'][i][j] = 0.
                            prediction['reasons'][i][j] = 'uncertain_language_counterrelation'
                    records[key][name].append(prediction)
                    for i, j in zip(*np.where(np.asarray(base['scores']).reshape(shape) != np.asarray(prediction['scores']).reshape(shape))):
                        if not any(c.get('changed_student_ids') for c in cases) or case['student'][j]['id'] in case.get('changed_student_ids', []):
                            changes.append({'variant': name, 'threshold': threshold, 'case': case['id'], 'reference': case['reference'][i],
                                'student': case['student'][j], 'gold': case['annotations'][i][j],
                                'before': base['reasons'][i][j], 'after': prediction['reasons'][i][j]})
        summaries = {}
        changed = any(c.get('changed_student_ids') for c in cases)
        for key, variants in records.items():
            summaries[key] = {}
            for name, predictions in variants.items():
                metrics = evaluate(cases, predictions, .5, changed=changed)
                for k in ('top1', 'queries', 'top1_accuracy'):
                    metrics.pop(k)
                summaries[key][name] = metrics
                print(f'{dataset_name} / {key} / {name}: TP={metrics["tp"]} FP={metrics["fp"]} '
                      f'P={metrics["precision"]:.4f} R={metrics["recall"]:.4f} F1={metrics["f1"]:.4f}', flush=True)
        counts = Counter('uncertain' if r['language'] is None else 'correct' if r['language'] == r['annotated_language']
                         else 'different_from_annotation' for r in language_rows if r['annotated_language'] in ('de', 'en'))
        result['datasets'][dataset_name] = {'summary': summaries, 'language_counts': dict(counts),
            'language_rows': language_rows, 'features': features, 'predictions': records, 'changes': changes,
            'seconds': time.perf_counter() - started}
    result['unique_labels'] = detector.cache
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
    run(config, args.output or ROOT / config['lingua_comparison']['output'])


if __name__ == '__main__':
    main()
