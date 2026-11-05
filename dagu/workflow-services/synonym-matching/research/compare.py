"""Vergleiche feste Pipelines, ohne den Service oder seine API zu verändern.

Ein JSON enthält Konfiguration, Rohscores, Entscheidungen und Metriken. Die
Terminalausgabe ist die kurze Übersicht. Es wird nichts auf Testlabels trainiert.
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

PIPELINES = {
    'raw': [],
    'normalize': ['normalize'],
    'lowercase': ['normalize', 'lowercase'],
    'lemma': ['normalize', 'lemmatize', 'lowercase'],
    'stem': ['normalize', 'lowercase', 'stem'],
    'identifiers': ['normalize', 'split_identifiers', 'lowercase'],
    'compounds': ['normalize', 'lowercase', 'split_compounds'],
}
STRING_METHODS = (
    'levenshtein', 'damerau_levenshtein', 'jaro_winkler', 'char_bigram',
    'char_trigram', 'token_jaccard', 'token_sort_ratio', 'word_order',
)
STRATEGIES = ('threshold', 'mutual_best', 'hungarian')
WORD_METHODS = {name + '_matching': name for name in ('word2vec', 'fasttext', 'glove', 'paragram')}

# Diese Aliasfunktionen bleiben für bestehende API-Aufrufer erhalten.
ALIASES = {
    'translation_string', 'translation_monolingual', 'multilingual_only',
    'string_multilingual', 'weighted_fusion',
}


def configurations(models=False, lexicons=False, pipelines=None, new_methods=False):
    """Erstelle eindeutige Spezifikationen statt mehrfacher Namen für dieselbe Formel."""
    methods = list(STRING_METHODS) + ['exact_match']
    if models:
        methods += ['multilingual', 'translated_embedding', 'translated_string']
    if lexicons:
        methods += ['wordnet', 'openthesaurus']
    specs = [{'name': name, 'methods': [name], 'combiner': {'kind': 'mean'}} for name in methods]
    for name, requires in REQUIRES.items():
        if name not in ALIASES and set(requires) <= set(methods):
            specs.append({'name': name, 'methods': list(requires),
                          'combiner': {'kind': 'variant', 'name': name}})
    if models:
        for embedding_weight in (.25, .5, .75):
            string_weight = 1 - embedding_weight
            specs.append({
                'name': f'string_multi_{int(string_weight * 100)}_{int(embedding_weight * 100)}',
                'methods': list(REQUIRES['weighted_fusion']),
                'combiner': {'kind': 'variant', 'name': 'weighted_fusion',
                             'options': {'embedding_weight': embedding_weight}},
            })
    if lexicons:
        for lexicon in ('wordnet', 'openthesaurus'):
            strings = list(REQUIRES['string_ensemble'])
            specs.append({'name': lexicon + '_string', 'methods': [lexicon] + strings,
                          'combiner': {'kind': 'weighted_mean',
                                       'weights': {lexicon: .5, **{n: .5 / len(strings) for n in strings}}}})
            if models:
                specs.append({'name': lexicon + '_multilingual', 'methods': [lexicon, 'multilingual'],
                              'combiner': {'kind': 'mean'}})
        specs.append({'name': 'wordnet_openthesaurus', 'methods': ['wordnet', 'openthesaurus'],
                      'combiner': {'kind': 'mean'}})
    if new_methods:
        specs += [{'name': name, 'methods': [name], 'combiner': {'kind': 'mean'}}
                  for name in list(WORD_METHODS)]
        # 22 und 32 verwenden dieselbe FastText-Matrix; Hungarian läuft bereits separat.
        specs.append({'name': 'fasttext_levenshtein',
                      'methods': ['fasttext_matching', 'levenshtein'], 'combiner': {'kind': 'mean'}})
        specs.append({'name': 'glove_fasttext_paragram',
                      'methods': ['glove_matching', 'fasttext_matching', 'paragram_matching'],
                      'combiner': {'kind': 'weighted_mean',
                                   'weights': {'glove_matching': 1, 'fasttext_matching': 1, 'paragram_matching': 1}}})
        if models:
            specs.append({'name': 'string_embedding_global_ranking',
                          'methods': list(REQUIRES['weighted_fusion']),
                          'combiner': {'kind': 'variant', 'name': 'weighted_fusion',
                                       'options': {'embedding_weight': .5}}, 'global_ranking': True})
    # Jede Zeile beschreibt genau einen Versuch. Hier neue Kombinationen ergänzen.
    pipelines = PIPELINES if pipelines is None else pipelines
    result = {}
    for spec in specs:
        uses_strings = bool(set(spec['methods']) & set(STRING_METHODS))
        preprocessing = pipelines if uses_strings else {'fixed': ['normalize']}
        for name, steps in preprocessing.items():
            result[name + '/' + spec['name']] = {
                **spec, 'preprocessing': steps, 'embedding_preprocessing': ['normalize'],
            }
    return result


def unsupported(method, steps, case, word_vectors=None):
    """Unpassende Sprachen sind fehlende Abdeckung, keine Nullscores."""
    languages = {e.get('language') for e in case['reference'] + case['student']
                 if e['label'].strip()}
    if method in WORD_METHODS:
        config = (word_vectors or {}).get(WORD_METHODS[method])
        if config is None:
            return 'Lokale Wortvektoren fehlen.'
        supported = {'de', 'en'} if config.get('translate_to_en') else set(config.get('files', {}))
        if not languages <= supported:
            return 'Keine Wortvektoren für alle angegebenen Sprachen.'
        if config.get('nouns_only') and not languages <= {'de', 'en'}:
            return 'Nomenfilter nur DE/EN.'
    if method == 'openthesaurus' and not languages <= {'de'}:
        return 'OpenThesaurus: only de supported'
    if method in {'wordnet', 'translated_string', 'translated_embedding'}:
        if not languages <= {'de', 'en'}:
            return 'Translation: only de/en supported'
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
                str(p.relative_to(DATA_DIR.parent.parent)): sha256(p)
                for folder in (Path(__file__).parent,
                               DATA_DIR.parent.parent / 'src/synonym_matching')
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


def calculate_features(cases, definitions, word_vectors=None):
    """Berechne jede Methode/Preprocessing-Kombination pro Testfall genau einmal."""
    tasks = {}
    for config in definitions.values():
        for method in config['methods']:
            steps = config['preprocessing'] if method in STRING_METHODS else ['normalize']
            tasks[method, tuple(steps)] = steps
    features, engines, errors = {}, {}, []
    translator = None
    word_backends = {}
    extra = {'word_vectors': {}}
    # Große Wortmodelle vor Embeddings laden und direkt danach wieder freigeben.
    for key in sorted(tasks, key=lambda item: item[0] not in WORD_METHODS):
        steps = tasks[key]
        method = key[0]
        engine = None
        for case in cases:
            reason = unsupported(method, steps, case, word_vectors)
            if reason:
                features[key, case['id']] = {'status': 'unsupported', 'reason': reason}
                continue
            try:
                if engine is None:
                    if method in WORD_METHODS:
                        from .word_matching import WordMatching
                        model = WORD_METHODS[method]
                        engine = WordMatching(word_vectors[model], translator, name=method)
                        word_backends[model] = engine
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
        if method in WORD_METHODS and engine is not None:
            engine.models.clear()
    for name, backend in word_backends.items():
        extra['word_vectors'][name] = {'config': backend.config,
            'sha256': {lang: sha256(path) if Path(path).is_file() else None for lang, path in backend.files.items()},
            'translation_revision': backend.translator.revision if backend.translator else None}
    return features, engines, errors, extra


def run_experiments(data, output, *, models=False, lexicons=False, threshold=.5,
                    pipelines=None, strategies=STRATEGIES, new_methods=False,
                    word_vectors=None):
    """Berechne gemeinsame Features einmal; vergleiche alle Varianten ohne Tuning."""
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('threshold must be in [0,1]')
    output = Path(output)
    if output.exists():
        raise FileExistsError('choose a new output filename')
    pipelines = PIPELINES if pipelines is None else pipelines
    if not pipelines or not data.get('cases'):
        raise ValueError('nonempty pipelines and cases required')
    case_ids = [case['id'] for case in data['cases']]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError('case IDs must be unique')
    if not strategies or set(strategies) - set(STRATEGIES):
        raise ValueError('unknown or empty assignment strategies')
    # Seeds einmal pro Versuch setzen, nicht bei jeder Engine-Erzeugung.
    random.seed(42)
    np.random.seed(42)
    definitions = configurations(models, lexicons, pipelines, new_methods)
    started = time.perf_counter()
    features, engines, errors, extra = calculate_features(data['cases'], definitions, word_vectors)
    for spec in definitions.values():
        options = {
            method: extra['word_vectors'][WORD_METHODS[method]]['config']
            for method in spec['methods'] if method in WORD_METHODS
            and WORD_METHODS[method] in extra['word_vectors']}
        if options:
            spec['word_matching'] = options
    records = []

    for identifier, spec in definitions.items():
        for case in data['cases']:
            parts = {}
            for name in spec['methods']:
                steps = spec['preprocessing'] if name in STRING_METHODS else ['normalize']
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
    payload = {'version': 2, 'seed': 42, 'threshold': threshold,
               'score_policy': 'raw cosine [-1,1]; combinations clip to [0,1]; no calibration',
               'timing_policy': ('sequential CPU; shared cached raw features; load time included on first use; '
                                 'feature time excludes candidate construction and JSON conversion'),
               'dataset': data, 'definitions': definitions, 'features': feature_records,
               'records': records, 'errors': errors, 'provenance': provenance(engines),
               'additional_resources': extra,
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
    if new_methods:
        for method in list(WORD_METHODS):
            reasons = sorted({item['reason'] for item in feature_records
                              if item['method'] == method and item['status'] != 'ok'})
            if reasons:
                print(f"Nicht vollständig ausgeführt: {method}: {'; '.join(reasons)}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path(__file__).with_name('model-cases.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--models', action='store_true', help='Embedding- und Übersetzungsverfahren')
    parser.add_argument('--lexicons', action='store_true', help='WordNet und OpenThesaurus')
    parser.add_argument('--new-methods', action='store_true', help='Neue Wortvektor- und Ranking-Vergleiche')
    parser.add_argument('--word-vectors', type=Path, help='JSON mit lokalen Vektormodellpfaden je Sprache')
    parser.add_argument('--threshold', type=float, default=.5)
    parser.add_argument('--preprocessing', nargs='*', default=None,
                        help='Nur diese Schritte vergleichen; ohne Angabe alle Ablationen')
    parser.add_argument('--extended', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.word_vectors and not args.new_methods:
        parser.error('--word-vectors requires --new-methods')
    pipelines = None if args.preprocessing is None else {'custom': args.preprocessing}
    errors = run_experiments(
        json.loads(args.data.read_text()), args.output,
        models=args.models, lexicons=args.lexicons, threshold=args.threshold,
        pipelines=pipelines,
        new_methods=args.new_methods,
        word_vectors=json.loads(args.word_vectors.read_text()) if args.word_vectors else None,
    )
    print(f'Gespeichert: {args.output}; technische Fehler: {len(errors)}')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
