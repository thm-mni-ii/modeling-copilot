"""Vergleiche alle in experiments.json aktivierten Verfahren und Kombinationen.

Ein Befehl, eine JSON-Datei: Konfiguration, Rohscores, Entscheidungen und Metriken.
Die Terminalausgabe ist die kurze Übersicht. Es wird nichts auf Testlabels trainiert.
"""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import time
from pathlib import Path

import numpy as np

from synonym_matching.service import MatchingEngine
from .evaluation import evaluate_case, select_matches, global_ranking
from synonym_matching.lexicons import DATA_DIR
from synonym_matching.combinations import REQUIRES, combine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path(__file__).with_name('experiments.json')


def is_wordvec(method):
    """Wortvektor-Verfahren sind in der Konfiguration durch ihre Dateien erkennbar."""
    return 'files' in method


def load_config(path=DEFAULT_CONFIG):
    """Lese und prüfe die Experimentkonfiguration."""
    config = json.loads(Path(path).read_text())
    if not 0 <= config['threshold'] <= 1:
        raise ValueError('threshold must be in [0,1]')
    if not config['preprocessing'] or not config['methods']:
        raise ValueError('nonempty preprocessing and methods required')
    allowed = {'threshold', 'mutual_best', 'hungarian'}
    if not config['strategies'] or set(config['strategies']) - allowed:
        raise ValueError('unknown or empty assignment strategies')
    return config


def combination_spec(entry):
    """Übersetze einen Konfigurationseintrag in Methodenliste und Kombinierer."""
    if 'variant' in entry:
        combiner = {'kind': 'variant', 'name': entry['variant']}
        if 'options' in entry:
            combiner['options'] = entry['options']
        return list(REQUIRES[entry['variant']]), combiner
    return list(entry['weights']), {'kind': 'weighted_mean', 'weights': entry['weights']}


def duplicate_key(spec):
    """Gleiche Methoden, Gewichte und Preprocessing ergeben denselben Versuch."""
    combiner = spec['combiner']
    if combiner['kind'] == 'weighted_mean':
        total = sum(combiner['weights'].values())
        formula = sorted((m, round(w / total, 9)) for m, w in combiner['weights'].items())
    elif combiner['kind'] == 'mean':
        formula = sorted((m, round(1 / len(spec['methods']), 9)) for m in spec['methods'])
    else:
        formula = json.dumps(combiner, sort_keys=True)
    return json.dumps([formula, spec['preprocessing'], spec.get('global_ranking', False)])


def configurations(config):
    """Erstelle alle Versuche aus der Konfiguration; liefere auch die Übersprungenen."""
    methods = config['methods']
    enabled = {name for name, method in methods.items() if method.get('enabled', True)}
    specs = [{'name': name, 'methods': [name], 'combiner': {'kind': 'mean'}}
             for name in methods if name in enabled]
    skipped = []
    for entry in config['combinations']:
        needed, combiner = combination_spec(entry)
        unknown = set(needed) - set(methods)
        if unknown:
            raise ValueError(f"{entry['name']}: unknown methods {sorted(unknown)}")
        if not set(needed) <= enabled:
            skipped.append({'name': entry['name'], 'reason': 'Verfahren deaktiviert'})
            continue
        spec = {'name': entry['name'], 'methods': needed, 'combiner': combiner}
        if entry.get('global_ranking'):
            spec['global_ranking'] = True
        specs.append(spec)

    result, seen = {}, {}
    for spec in specs:
        ablate = any(methods[name].get('ablate') for name in spec['methods'])
        variants = config['preprocessing'] if ablate else {'fixed': ['normalize']}
        for label, steps in variants.items():
            full = {**spec, 'preprocessing': steps, 'embedding_preprocessing': ['normalize']}
            key = duplicate_key(full)
            if key in seen:
                skipped.append({'name': label + '/' + spec['name'],
                                'reason': 'Doppelt zu ' + seen[key]})
                continue
            seen[key] = label + '/' + spec['name']
            result[seen[key]] = full
    return result, skipped


def steps_for(method, steps, methods):
    """Nur ablatierbare Stringverfahren verwenden das jeweilige Preprocessing."""
    return steps if methods[method].get('ablate') else ['normalize']


def unsupported(method, steps, case):
    """Fehlende Ressourcen und unpassende Sprachen sind keine Nullscores."""
    languages = {e.get('language') for e in case['reference'] + case['student']
                 if e['label'].strip()}
    if is_wordvec(method):
        missing = [path for path in method['files'].values() if not (ROOT / path).is_file()]
        if missing:
            return 'Ressource fehlt: ' + ', '.join(missing)
        supported = {'de', 'en'} if method.get('translate_to_en') else set(method['files'])
        if not languages <= supported:
            return 'Keine Wortvektoren für alle angegebenen Sprachen.'
        if method.get('nouns_only') and not languages <= {'de', 'en'}:
            return 'Nomenfilter nur DE/EN.'
    elif 'languages' in method and not languages <= set(method['languages']):
        return 'Nur ' + '/'.join(method['languages']) + ' unterstützt'
    if {'lemmatize', 'stem'} & set(steps) and not languages <= {'de', 'en'}:
        return 'Lemma/stemming: only de/en supported'
    return None


def sha256(path):
    """Identifiziere Code und lokale Ressourcen ohne sie zu kopieren."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def provenance(engines):
    """Speichere die Umgebung und tatsächlich geladenen Modellrevisionen."""
    packages = {}
    for name in ('numpy', 'scipy', 'nltk', 'spacy', 'rapidfuzz', 'torch',
                 'transformers', 'sentence-transformers', 'de_core_news_sm',
                 'en_core_web_sm', 'gensim', 'fasttext'):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    models = {}
    for key, engine in engines.items():
        for name, backend in engine.backends.items():
            if getattr(backend, 'revision', None):
                models[name] = {'revision': backend.revision,
                                'config': engine.config['embedding'].get(name, {})}
        if engine.translator.revision:
            models['translation'] = engine.translator.revision
    from synonym_matching.methods import EMBEDDING_MODELS
    resources = {}
    for name in ('openthesaurus.txt', 'nltk_data/corpora/wordnet.zip'):
        path = DATA_DIR / name
        if path.exists():
            resources[name] = sha256(path)
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'packages': packages, 'models': models, 'model_names': EMBEDDING_MODELS,
            'translation_model': 'Helsinki-NLP/opus-mt-de-en',
            'resources': resources,
            'source_hashes': {
                str(p.relative_to(ROOT)): sha256(p)
                for folder in (Path(__file__).parent, ROOT / 'src/synonym_matching')
                for p in folder.glob('*.py')
            }}


def score_statistics(features):
    """Beschreibe Rohscore-Verteilungen; dies ist keine Kalibrierung."""
    groups = {}
    for item in features:
        if item['status'] != 'ok':
            continue
        key = item['method'] + '/' + ','.join(item['preprocessing'])
        scores = np.asarray(item['scores']).reshape(item['shape'])
        mask = np.asarray(item['eligible'], dtype=bool).reshape(item['shape'])
        groups.setdefault(key, []).extend(scores[mask].tolist())
    result = {}
    for name, values in groups.items():
        scores = np.asarray(values)
        if scores.size:
            result[name] = {
                'n': len(values), 'min': float(scores.min()),
                'max': float(scores.max()), 'mean': float(scores.mean()),
                'negative_count': int((scores < 0).sum()),
                'zero_fraction': float((scores == 0).mean()),
                'one_fraction': float((scores == 1).mean()),
            }
    return result


def calculate_features(cases, definitions, methods):
    """Berechne jede Methode/Preprocessing-Kombination pro Testfall genau einmal."""
    tasks = {}
    for config in definitions.values():
        for method in config['methods']:
            steps = steps_for(method, config['preprocessing'], methods)
            tasks[method, tuple(steps)] = steps
    features, engines, errors = {}, {}, []
    translator = None
    word_backends = {}
    # Große Wortmodelle vor Embeddings laden und direkt danach wieder freigeben.
    for key in sorted(tasks, key=lambda item: not is_wordvec(methods[item[0]])):
        steps = tasks[key]
        method = key[0]
        engine = None
        for case in cases:
            reason = unsupported(methods[method], steps, case)
            if reason:
                features[key, case['id']] = {'status': 'unsupported', 'reason': reason}
                continue
            try:
                if engine is None:
                    if is_wordvec(methods[method]):
                        from .word_matching import WordMatching
                        files = {lang: str(ROOT / path)
                                 for lang, path in methods[method]['files'].items()}
                        engine = WordMatching({**methods[method], 'files': files}, translator, name=method)
                        word_backends[method] = engine
                        translator = engine.translator or translator
                    else:
                        engine = MatchingEngine({'methods': [method], 'preprocessing': steps})
                        engines[key] = engine
                    if method in {'wordnet', 'translated_string', 'translated_embedding'}:
                        translator = translator or engine.translator
                        engine.translator = translator
                        if method == 'translated_embedding':
                            engine.backends[method].translator = translator
                started = time.perf_counter()
                result = engine.compute_scores(case['reference'], case['student'])
                seconds = time.perf_counter() - started
                texts = result['processedLabels'][method]
                features[key, case['id']] = {
                    'status': 'ok', 'scores': result['scores'][method].tolist(),
                    'shape': result['shape'], 'seconds': seconds, 'processedLabels': texts,
                    'eligible': (result['validPairs'] & result['usablePairs'][method]).tolist(),
                }
            except Exception as error:
                reason = f'{type(error).__name__}: {error}'
                features[key, case['id']] = {'status': 'error', 'reason': reason}
                errors.append({'method': method, 'preprocessing': steps,
                               'case': case['id'], 'reason': reason})
        # Die Kombinationen verwenden danach nur noch die gespeicherten Scores.
        if is_wordvec(methods[method]) and engine is not None:
            engine.models.clear()
    word_vectors = {}
    for name, backend in word_backends.items():
        word_vectors[name] = {
            'config': {**backend.config, 'files': methods[name]['files']},
            'sha256': {lang: sha256(path) if Path(path).is_file() else None
                       for lang, path in backend.files.items()},
            'translation_revision': backend.translator.revision if backend.translator else None}
    return features, engines, errors, word_vectors


def run_experiments(data, output, config):
    """Berechne gemeinsame Features einmal; vergleiche alle Varianten ohne Tuning."""
    output = Path(output)
    if output.exists():
        raise FileExistsError('choose a new output filename')
    if not data.get('cases'):
        raise ValueError('nonempty cases required')
    case_ids = [case['id'] for case in data['cases']]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError('case IDs must be unique')
    threshold, strategies = config['threshold'], config['strategies']
    # Seeds einmal pro Versuch setzen, nicht bei jeder Engine-Erzeugung.
    random.seed(config['seed'])
    np.random.seed(config['seed'])
    definitions, skipped = configurations(config)
    methods = config['methods']
    started = time.perf_counter()
    features, engines, errors, word_vectors = calculate_features(data['cases'], definitions, methods)
    for spec in definitions.values():
        options = {name: word_vectors[name]['config']
                   for name in spec['methods'] if name in word_vectors}
        if options:
            spec['word_matching'] = options
    records = []

    for identifier, spec in definitions.items():
        for case in data['cases']:
            parts = {}
            for name in spec['methods']:
                steps = steps_for(name, spec['preprocessing'], methods)
                parts[name] = features[((name, tuple(steps)), case['id'])]
            base = {'experiment': identifier, 'case': case['id']}
            missing = {n: p for n, p in parts.items() if p['status'] != 'ok'}
            if missing:
                records.append({**base, 'status': 'unavailable', 'missing': missing})
                continue
            shape = (len(case['reference']), len(case['student']))
            raw = {n: np.asarray(p['scores']).reshape(shape) for n, p in parts.items()}
            eligible = np.logical_or.reduce([
                np.asarray(p['eligible'], dtype=bool).reshape(shape) for p in parts.values()])
            t0 = time.perf_counter()
            scores = combine(raw, spec['combiner'])
            if spec.get('global_ranking'):
                scores = global_ranking(scores, eligible)
            combine_seconds = time.perf_counter() - t0
            decisions = {}
            for strategy in strategies:
                t0 = time.perf_counter()
                selected = select_matches(scores, eligible, threshold, strategy)
                assignment_seconds = time.perf_counter() - t0
                decisions[strategy] = {
                    'selected': selected.tolist(), 'seconds': assignment_seconds,
                    'metrics': evaluate_case(case, scores, threshold,
                                             eligible=eligible, selected=selected)}
            records.append({**base, 'status': 'ok', 'shape': list(shape),
                            'combinedScores': scores.tolist(), 'decisions': decisions,
                            'feature_seconds': sum(p['seconds'] for p in parts.values()),
                            'combine_seconds': combine_seconds})

    # Eine einzige Datei reicht zur Rekonstruktion: Daten, Parameter und Rohscores.
    feature_records = []
    for ((method, steps), case_id), item in features.items():
        feature_records.append({'method': method, 'preprocessing': list(steps),
                                'case': case_id, **item})
    payload = {'version': 3, 'seed': config['seed'], 'threshold': threshold, 'config': config,
               'score_policy': 'raw cosine [-1,1]; combinations clip to [0,1]; no calibration',
               'timing_policy': ('sequential CPU; shared cached raw features; load time included on first use; '
                                 'feature time excludes candidate construction and JSON conversion'),
               'dataset': data, 'definitions': definitions, 'skipped_definitions': skipped,
               'features': feature_records, 'records': records, 'errors': errors,
               'provenance': provenance(engines),
               'additional_resources': {'word_vectors': word_vectors},
               'score_statistics': score_statistics(feature_records),
               'dataset_sha256': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
               'elapsed_seconds': time.perf_counter() - started}
    from .rank_results import build_rankings, print_rankings
    strategy = 'threshold' if 'threshold' in strategies else strategies[0]
    rankings = build_rankings(payload, strategy)
    payload['rankings'] = {strategy: rankings}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print_rankings(rankings)
    # Nicht ausführbare Verfahren erscheinen mit Grund, nie als Nullergebnis.
    reasons = sorted({(item['method'], item['reason']) for item in feature_records
                      if item['status'] != 'ok'})
    for method, reason in reasons:
        print(f'Nicht vollständig ausgeführt: {method}: {reason}')
    for item in skipped:
        print(f"Übersprungen: {item['name']}: {item['reason']}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--data', type=Path, default=Path(__file__).with_name('model-cases.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    errors = run_experiments(json.loads(args.data.read_text()), args.output, load_config(args.config))
    print(f'Gespeichert: {args.output}; technische Fehler: {len(errors)}')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
