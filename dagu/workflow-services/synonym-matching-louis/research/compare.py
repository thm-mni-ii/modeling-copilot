"""Vergleiche alle in experiments.json aktivierten Verfahren und Mischungen.

Ein Befehl, eine JSON-Datei: Konfiguration, Rohscores, Entscheidungen und Metriken.
Die Terminalausgabe ist die kurze Übersicht. Es wird nichts auf Testlabels trainiert.
Die Versuche selbst werden in experiments.py aus der Konfiguration gebaut.
"""

import argparse
import contextlib
import gzip
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
from .lexicon_coverage import inspect_labels, summarize_coverage
from .evaluation import evaluate_case, select_matches, global_ranking
from .experiments import (DEFAULT_CONFIG, ROOT, configurations, is_wordvec, load_config,
                          unsupported)
from synonym_matching.lexicons import DATA_DIR, OdeNet, OpenThesaurus, WordNet
from synonym_matching.combinations import combine, evidence_fusion
from synonym_matching.methods import EmbeddingMethod
from synonym_matching.cache import Cache
from synonym_matching.translation import Translator


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
               (OpenThesaurus, '_load'), (OdeNet, '_load'), (word_matching, 'load_vectors')]
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


def provenance(engines, translator=None):
    """Speichere die Umgebung und tatsächlich geladenen Modellrevisionen."""
    packages = {}
    for name in ('numpy', 'scipy', 'nltk', 'spacy', 'rapidfuzz', 'torch',
                 'transformers', 'sentence-transformers', 'de_core_news_sm',
                 'en_core_web_sm', 'gensim', 'fasttext', 'wn'):
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
    # Alle Übersetzungen laufen über dieselbe Instanz.
    if translator is not None and translator.revision:
        models['translation'] = translator.revision
    from synonym_matching.methods import EMBEDDING_MODELS
    resources = {}
    for name in ('openthesaurus.txt', 'wn/wn.db'):
        path = DATA_DIR / name
        if path.exists():
            resources[name] = sha256(path)
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'packages': packages, 'models': models, 'model_names': EMBEDDING_MODELS,
            'translation_model': 'Helsinki-NLP/opus-mt-de-en',
            'odenet_version': OdeNet.version,
            'wordnet_version': WordNet.version,
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

    Beide Arten liefern danach dasselbe Objekt mit compute_scores() und verarbeiten
    die Schritte der Kette (inklusive 'translate') mit demselben Preprocessor.
    """
    if is_wordvec(method):
        from .word_matching import WordMatching
        files = {lang: str(ROOT / path) for lang, path in method['files'].items()}
        return WordMatching({**method, 'files': files, 'preprocessing': steps},
                            translator, name=name, models=models)
    config = {'methods': [name], 'preprocessing': steps, 'embedding_preprocessing': steps}
    if 'relation_features' in method:
        config['semantic_features'] = {name: method['relation_features']}
    return MatchingEngine(config, translator)


def calculate_features(cases, definitions, methods):
    """Berechne jede Kette pro Testfall genau einmal."""
    tasks = {}
    for spec in definitions.values():
        for chain in spec['chains'].values():
            tasks.setdefault(chain[-1], {})[tuple(chain)] = chain
    features, engines, errors = {}, {}, []
    translator = Translator({}, Cache())
    word_backends = {}
    # Große Wortmodelle zuerst; Verfahren mit denselben Modelldateien stehen hintereinander
    # und teilen das geladene Modell. Es wird freigegeben, sobald andere Dateien folgen.
    models, loaded_files = {}, None
    for method in sorted(tasks, key=lambda name: (not is_wordvec(methods[name]),
                                                  str(methods[name].get('files')))):
        if methods[method].get('files') != loaded_files:
            models.clear()
            loaded_files = methods[method].get('files')
        for key, chain in tasks[method].items():
            engine = None
            for case in cases:
                reason = unsupported(methods[method], chain, case)
                if reason:
                    features[key, case['id']] = {'status': 'unsupported', 'reason': reason}
                    continue
                try:
                    if engine is None:
                        engine = make_engine(method, methods[method], list(chain[:-1]),
                                             translator, models)
                        if is_wordvec(methods[method]):
                            word_backends[method] = engine
                        else:
                            engines[key] = engine
                    load_before = LOAD_SECONDS[0]
                    started = time.perf_counter()
                    result = engine.compute_scores(case['reference'], case['student'])
                    elapsed = time.perf_counter() - started
                    load = LOAD_SECONDS[0] - load_before
                    relation_seconds = result.get('semantic_seconds', {}).get(method, 0)
                    features[key, case['id']] = {
                        'status': 'ok', 'scores': result['scores'][method].tolist(),
                        'shape': result['shape'], 'seconds': elapsed - load - relation_seconds,
                        'load_seconds': load,
                        'processedLabels': result['processedLabels'][method],
                        'eligible': (result['validPairs'] & result['usablePairs'][method]).tolist(),
                    }
                    backend = getattr(engine, 'backends', {}).get(method)
                    if method == 'wn_translation':
                        features[key, case['id']]['crosslingual_coverage'] = backend['coverage']
                    if isinstance(backend, (WordNet, OdeNet, OpenThesaurus)):
                        # Reine Diagnose nach der Scoreberechnung; kein zusätzlicher
                        # Kombinationsscore, keine Änderung der Kandidatenmaske.
                        diagnosis_started = time.perf_counter()
                        features[key, case['id']]['lexicon_coverage'] = {
                            side: inspect_labels(texts, backend.lookup)
                            for side, texts in result['processedLabels'][method].items()}
                        features[key, case['id']]['coverage_seconds'] = (
                            time.perf_counter() - diagnosis_started)
                    if method in result.get('semantic_features', {}):
                        relations = result['semantic_features'][method]
                        features[key, case['id']]['relation_features'] = {
                            name: values.tolist() for name, values in relations.items()}
                        features[key, case['id']]['relation_seconds'] = relation_seconds
                except Exception as error:
                    reason = f'{type(error).__name__}: {error}'
                    features[key, case['id']] = {'status': 'error', 'reason': reason}
                    errors.append({'chain': list(chain), 'case': case['id'], 'reason': reason})
    # Die Kombinationen verwenden danach nur noch die gespeicherten Scores.
    models.clear()
    word_vectors = {}
    for name, backend in word_backends.items():
        word_vectors[name] = {'config': methods[name], 'sha256': {}, 'sha256_source': {}}
        for lang, path in backend.files.items():
            if Path(path).is_file():
                digest, source = resource_hash(path)
                word_vectors[name]['sha256'][lang] = digest
                word_vectors[name]['sha256_source'][lang] = source
    return features, engines, errors, word_vectors, translator


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


def run_experiments(data, output, config, *, only=None):
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
    if only is not None:
        unknown = set(only) - definitions.keys()
        if unknown or not only:
            raise ValueError(f'unknown or empty experiment selection: {sorted(unknown)}')
        definitions = {name: definitions[name] for name in dict.fromkeys(only)}
    methods = config['methods']
    started = time.perf_counter()
    with track_loading():
        features, engines, errors, word_vectors, translator = calculate_features(
            data['cases'], definitions, methods)
    for spec in definitions.values():
        options = {name: word_vectors[name]['config']
                   for name in spec['methods'] if name in word_vectors}
        if options:
            spec['word_matching'] = options
    records = []

    for identifier, spec in definitions.items():
        for case in data['cases']:
            parts = {key: features[(tuple(chain), case['id'])] for key, chain in spec['chains'].items()}
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
            changes = []
            if spec['combiner']['kind'] == 'evidence':
                baseline = spec['combiner']['baseline']
                lexical = spec['combiner']['lexicon']
                scores = evidence_fusion(raw[baseline], raw[lexical], parts[lexical]['relation_features'])
                before = np.clip(raw[baseline], 0, 1)
                for i, j in np.argwhere(scores != before):
                    changes.append({'reference_id': case['reference'][i]['id'],
                                    'student_id': case['student'][j]['id'],
                                    'before': float(before[i, j]), 'after': float(scores[i, j]),
                                    'reason': 'single_sense_synonym' if scores[i, j] == 1
                                              else 'single_sense_counterrelation'})
            else:
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
            if spec['combiner']['kind'] == 'evidence':
                records[-1]['evidence_changes'] = changes
                records[-1]['feature_seconds'] += parts[lexical].get('relation_seconds', 0)

    # Eine einzige Datei reicht zur Rekonstruktion: Daten, Parameter und Rohscores.
    feature_records = []
    for (chain, case_id), item in features.items():
        feature_records.append({'chain': list(chain), 'method': chain[-1],
                                'preprocessing': list(chain[:-1]), 'case': case_id, **item})
    model_load_seconds = Counter()
    for item in feature_records:
        model_load_seconds[item['method']] += item.get('load_seconds', 0)
    payload = {'version': 3, 'seed': config['seed'], 'threshold': threshold, 'config': config,
               'selected_experiments': only,
               'score_policy': 'raw cosine [-1,1]; combinations clip to [0,1]; no calibration',
               'timing_policy': ('sequential CPU; compute seconds exclude model loading, which is stored '
                                 'in model_load_seconds (shared models count for the first method needing '
                                 'them; spaCy loads are not separated); excludes candidate construction '
                                 'and JSON conversion'),
               'model_load_seconds': dict(model_load_seconds),
               'dataset': data, 'excluded_cases': excluded, 'definitions': definitions,
               'skipped_definitions': skipped,
               'features': feature_records, 'records': records, 'errors': errors,
               'provenance': provenance(engines, translator),
               'additional_resources': {'word_vectors': word_vectors},
               'score_statistics': score_statistics(feature_records),
               'lexicon_coverage': summarize_coverage(feature_records, data['cases']),
               'relation_policy': ('Only explicit evidence mixes use relations in combinedScores. Binary values '
                                   'mean a relation exists for at least one possible sense; '
                                   '0 may mean unknown. Synset counts are raw counts. '
                                   'Direction is reference to student; wn.closure follows all hypernyms. '
                                   'Path/Wu-Palmer use native wn metrics, max over connected noun/verb '
                                   'sense pairs, no simulated root; check taxonomy_available.'),
               'dataset_sha256': dataset_hash,
               'elapsed_seconds': time.perf_counter() - started}
    from .rank_results import build_rankings, print_rankings
    strategy = 'threshold' if 'threshold' in strategies else strategies[0]
    rankings = build_rankings(payload, strategy)
    payload['rankings'] = {strategy: rankings}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Ganze Modelle ergeben große Matrizen. Kompakt und direkt in den Stream
    # schreiben; optional .json.gz spart zusätzlich Platz ohne Scores wegzulassen.
    if output.suffix == '.gz':
        stream = gzip.open(output, 'wt', encoding='utf-8', compresslevel=6)
    else:
        stream = output.open('w', encoding='utf-8')
    with stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        stream.write('\n')
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
    parser.add_argument('--only', nargs='+', help='Nur die genannten Experiment-IDs ausführen')
    args = parser.parse_args()
    errors = run_experiments(json.loads(args.data.read_text()), args.output, load_config(args.config),
                             only=args.only)
    print(f'Gespeichert: {args.output}; technische Fehler: {len(errors)}')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
