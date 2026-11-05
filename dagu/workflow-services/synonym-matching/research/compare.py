"""Vergleiche alle in experiments.json aktivierten Verfahren und Kombinationen.

Ein Befehl, eine JSON-Datei: Konfiguration, Rohscores, Entscheidungen und Metriken.
Die Terminalausgabe ist die kurze Übersicht. Es wird nichts auf Testlabels trainiert.
"""

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import platform
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np

from synonym_matching.service import MatchingEngine
from . import word_matching
from .evaluation import evaluate_case, select_matches, global_ranking
from synonym_matching.lexicons import DATA_DIR, OpenThesaurus, WordNet
from synonym_matching.combinations import REQUIRES, combine
from synonym_matching.methods import EmbeddingMethod
from synonym_matching.translation import Translator

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


def resource_hash(path):
    """Nutze die beim Download geprüfte Prüfsumme, wenn Pfad und Dateigröße passen."""
    manifest = ROOT / '.cache/word-vectors/huggingface-download-manifest.json'
    path = Path(path)
    if manifest.is_file():
        for entry in json.loads(manifest.read_text()):
            if str(ROOT / entry['path']) == str(path) and entry['bytes'] == path.stat().st_size:
                return entry['sha256'], 'manifest'
    return sha256(path), 'berechnet'


LOAD_SECONDS = [0.0]


@contextlib.contextmanager
def track_loading():
    """Messe Modellladezeiten getrennt von der Rechenzeit, ohne den Service zu ändern."""
    targets = [(EmbeddingMethod, '_load'), (Translator, '_load'), (WordNet, '_load'),
               (OpenThesaurus, '_load'), (word_matching, 'load_vectors')]
    originals = [(owner, name, getattr(owner, name)) for owner, name in targets]

    def timed(function):
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                LOAD_SECONDS[0] += time.perf_counter() - started
        return wrapper

    for owner, name, function in originals:
        setattr(owner, name, timed(function))
    try:
        yield
    finally:
        for owner, name, function in originals:
            setattr(owner, name, function)


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


def make_engine(name, method, steps, translator, models):
    """Einzige Stelle, an der Wortvektoren und Servicemethoden unterschieden werden.

    Beide Arten liefern danach dasselbe Objekt mit compute_scores().
    """
    if is_wordvec(method):
        from .word_matching import WordMatching
        files = {lang: str(ROOT / path) for lang, path in method['files'].items()}
        engine = WordMatching({**method, 'files': files, 'preprocessing': steps},
                              translator, name=name, models=models)
        return engine, engine.translator or translator
    engine = MatchingEngine({'methods': [name], 'preprocessing': steps})
    if name in {'wordnet', 'translated_string', 'translated_embedding'}:
        translator = translator or engine.translator
        engine.translator = translator
        if name == 'translated_embedding':
            engine.backends[name].translator = translator
    return engine, translator


def calculate_features(cases, definitions, methods):
    """Berechne jede Methode/Preprocessing-Kombination pro Testfall genau einmal."""
    tasks = {}
    for config in definitions.values():
        for method in config['methods']:
            steps = steps_for(method, config['preprocessing'], methods)
            tasks.setdefault(method, {})[tuple(steps)] = steps
    features, engines, errors = {}, {}, []
    translator = None
    word_backends = {}
    # Große Wortmodelle zuerst: ein Modell wird einmal geladen, für alle
    # Preprocessing-Varianten wiederverwendet und danach freigegeben.
    for method in sorted(tasks, key=lambda name: not is_wordvec(methods[name])):
        models = {}
        for steps_key, steps in tasks[method].items():
            key = (method, steps_key)
            engine = None
            for case in cases:
                reason = unsupported(methods[method], steps, case)
                if reason:
                    features[key, case['id']] = {'status': 'unsupported', 'reason': reason}
                    continue
                try:
                    if engine is None:
                        engine, translator = make_engine(method, methods[method], steps, translator, models)
                        if is_wordvec(methods[method]):
                            word_backends[method] = engine
                        else:
                            engines[key] = engine
                    load_before = LOAD_SECONDS[0]
                    started = time.perf_counter()
                    result = engine.compute_scores(case['reference'], case['student'])
                    elapsed = time.perf_counter() - started
                    load = LOAD_SECONDS[0] - load_before
                    features[key, case['id']] = {
                        'status': 'ok', 'scores': result['scores'][method].tolist(),
                        'shape': result['shape'], 'seconds': elapsed - load,
                        'load_seconds': load,
                        'processedLabels': result['processedLabels'][method],
                        'eligible': (result['validPairs'] & result['usablePairs'][method]).tolist(),
                    }
                except Exception as error:
                    reason = f'{type(error).__name__}: {error}'
                    features[key, case['id']] = {'status': 'error', 'reason': reason}
                    errors.append({'method': method, 'preprocessing': steps,
                                   'case': case['id'], 'reason': reason})
        # Die Kombinationen verwenden danach nur noch die gespeicherten Scores.
        models.clear()
    word_vectors = {}
    for name, backend in word_backends.items():
        word_vectors[name] = {
            'config': methods[name],
            'sha256': {}, 'sha256_source': {},
            'translation_revision': backend.translator.revision if backend.translator else None}
        for lang, path in backend.files.items():
            if Path(path).is_file():
                digest, source = resource_hash(path)
                word_vectors[name]['sha256'][lang] = digest
                word_vectors[name]['sha256_source'][lang] = source
    return features, engines, errors, word_vectors


def split_by_language(data, languages):
    """Trenne Fälle mit nicht erlaubten Sprachen ab; sie werden gemeldet, nicht still entfernt."""
    if not languages:
        return data, []
    kept, excluded = [], []
    for case in data['cases']:
        used = {e['language'] for side in ('reference', 'student') for e in case[side]
                if e['label'].strip() and e.get('language')}
        if used <= set(languages):
            kept.append(case)
        else:
            excluded.append({'case': case['id'], 'languages': sorted(used - set(languages))})
    return {**data, 'cases': kept}, excluded


def run_experiments(data, output, config):
    """Berechne gemeinsame Features einmal; vergleiche alle Varianten ohne Tuning."""
    output = Path(output)
    if output.exists():
        raise FileExistsError('choose a new output filename')
    dataset_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    data, excluded = split_by_language(data, config.get('languages'))
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
    with track_loading():
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
    model_load_seconds = Counter()
    for item in feature_records:
        model_load_seconds[item['method']] += item.get('load_seconds', 0)
    payload = {'version': 3, 'seed': config['seed'], 'threshold': threshold, 'config': config,
               'score_policy': 'raw cosine [-1,1]; combinations clip to [0,1]; no calibration',
               'timing_policy': ('sequential CPU; compute seconds exclude model loading, which is stored '
                                 'in model_load_seconds (shared models count for the first method needing '
                                 'them; spaCy loads are not separated); excludes candidate construction '
                                 'and JSON conversion'),
               'model_load_seconds': dict(model_load_seconds),
               'dataset': data, 'excluded_cases': excluded, 'definitions': definitions,
               'skipped_definitions': skipped,
               'features': feature_records, 'records': records, 'errors': errors,
               'provenance': provenance(engines),
               'additional_resources': {'word_vectors': word_vectors},
               'score_statistics': score_statistics(feature_records),
               'dataset_sha256': dataset_hash,
               'elapsed_seconds': time.perf_counter() - started}
    from .rank_results import build_rankings, print_rankings
    strategy = 'threshold' if 'threshold' in strategies else strategies[0]
    rankings = build_rankings(payload, strategy)
    payload['rankings'] = {strategy: rankings}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print_rankings(rankings)
    if excluded:
        print('Nicht ausgewertet (Sprache nicht in "languages" von experiments.json): ' +
              ', '.join(f"{e['case']} ({'/'.join(e['languages'])})" for e in excluded))
    # Nicht ausführbare Verfahren erscheinen mit Grund, nie als Nullergebnis.
    runs = Counter(item['method'] for item in feature_records)
    reasons = Counter((item['method'], item['reason']) for item in feature_records
                      if item['status'] != 'ok')
    for (method, reason), count in sorted(reasons.items()):
        print(f'Nicht vollständig ausgeführt: {method}: {reason} ({count} von {runs[method]} Läufen)')
    for item in skipped:
        print(f"Übersprungen: {item['name']}: {item['reason']}")
    loaded = {m: s for m, s in model_load_seconds.items() if s >= 0.05}
    if loaded:
        print('Modellladezeit (nicht in den Rechenzeiten): ' +
              ', '.join(f'{m} {s:.1f}s' for m, s in sorted(loaded.items())))
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
