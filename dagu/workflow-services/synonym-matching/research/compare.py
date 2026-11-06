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
from synonym_matching.cache import Cache
from synonym_matching.preprocessing import STEPS as PREPROCESSING_STEPS, Preprocessor
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
    if not config['preprocessing'] or not config['methods'] or not config['chains']:
        raise ValueError('nonempty preprocessing, methods and chains required')
    allowed = {'threshold', 'mutual_best', 'hungarian'}
    if not config['strategies'] or set(config['strategies']) - allowed:
        raise ValueError('unknown or empty assignment strategies')
    return config


def chain_name(chain):
    """Name direkt aus der Kette, z. B. 'normalize+stem → levenshtein'."""
    return ('+'.join(chain[:-1]) or 'raw') + ' → ' + chain[-1]


def check_chain(chain, methods):
    """Alle Glieder außer dem letzten sind '$pre', Preprocessing oder 'translate', das letzte ein Verfahren."""
    *steps, method = chain
    unknown = [s for s in steps if s not in ('$pre', 'translate') and s not in PREPROCESSING_STEPS]
    if (method not in methods or unknown or steps.count('translate') > 1
            or steps.count('$pre') > 1):
        raise ValueError(f'invalid chain {chain}')


def expand(chain, steps):
    """Ersetze den Platzhalter '$pre' durch die Schritte einer Preprocessing-Pipeline."""
    return [step for token in chain for step in (steps if token == '$pre' else [token])]


def definition(name, chains, combiner, steps=(), **extra):
    """Ein Versuch: benannte Ketten, deren Matrizen der Kombinierer verrechnet."""
    return {'name': name, 'methods': [chain[-1] for chain in chains.values()],
            'chains': chains, 'combiner': combiner, 'preprocessing': list(steps),
            'embedding_preprocessing': ['normalize'], **extra}


def duplicate_key(spec):
    """Gleiche Ketten und normierte Gewichte ergeben denselben Versuch."""
    combiner, chains = spec['combiner'], spec['chains']
    if combiner['kind'] == 'weighted_mean':
        total = sum(combiner['weights'].values())
        formula = sorted((chains[key], round(weight / total, 9))
                         for key, weight in combiner['weights'].items())
    elif combiner['kind'] == 'mean':
        formula = sorted((chain, round(1 / len(chains), 9)) for chain in chains.values())
    else:
        formula = [combiner, sorted(chains.items())]
    return json.dumps([formula, spec.get('global_ranking', False)], sort_keys=True)


def configurations(config):
    """Erstelle alle Versuche aus der Konfiguration; liefere auch die Übersprungenen."""
    methods = config['methods']
    enabled = {name for name, method in methods.items() if method.get('enabled', True)}
    result, seen, skipped = {}, {}, []

    def add(identifier, spec):
        key = duplicate_key(spec)
        if key in seen:
            skipped.append({'name': identifier, 'reason': 'Doppelt zu ' + seen[key]})
        else:
            seen[key] = identifier
            result[identifier] = spec

    def pipelines(chains):
        """Ohne '$pre' läuft ein Versuch einmal, mit '$pre' einmal je Pipeline."""
        if any('$pre' in chain for chain in chains):
            return config['preprocessing']
        return {None: []}

    blocks = config['chains']
    for chain in blocks.values():
        check_chain(chain, methods)
    for alias, chain in blocks.items():
        if chain[-1] not in enabled:
            skipped.append({'name': alias, 'reason': 'Verfahren deaktiviert'})
            continue
        for steps in pipelines([chain]).values():
            full = expand(chain, steps)
            add(chain_name(full), definition(chain_name(full), {chain[-1]: full},
                                             {'kind': 'mean'}, steps, chain_based=True))
    for entry in config['mixes']:
        aliases = list(entry['weights']) if 'weights' in entry else entry['parts']
        unknown = [alias for alias in aliases if alias not in blocks]
        if unknown:
            raise ValueError(f'mix uses unknown chains {unknown}')
        if not {blocks[alias][-1] for alias in aliases} <= enabled:
            skipped.append({'name': entry.get('name', ' + '.join(aliases)),
                            'reason': 'Verfahren deaktiviert'})
            continue
        for label, steps in pipelines([blocks[alias] for alias in aliases]).items():
            full = {alias: expand(blocks[alias], steps) for alias in aliases}
            if 'variant' in entry:
                # Varianten des Service erwarten die Matrizen unter dem Verfahrensnamen.
                chains = {chain[-1]: chain for chain in full.values()}
                missing = set(REQUIRES[entry['variant']]) - set(chains)
                if len(chains) != len(full) or missing:
                    raise ValueError(f"{entry['name']}: needs exactly one chain per method {sorted(missing)}")
                combiner = {'kind': 'variant', 'name': entry['variant']}
                if 'options' in entry:
                    combiner['options'] = entry['options']
                extra = {}
                # Ohne '$pre' tragen alle Ketten ihr Preprocessing selbst.
                shown = steps if label else full[aliases[0]][:-1]
            else:
                chains = {chain_name(chain): chain for chain in full.values()}
                if len(chains) != len(full):
                    raise ValueError('a mix may use each chain only once')
                weights = {chain_name(full[alias]): weight
                           for alias, weight in (entry.get('weights') or dict.fromkeys(aliases, 1)).items()}
                combiner = {'kind': 'weighted_mean', 'weights': weights}
                extra = {'chain_based': True}
                shown = steps
            if entry.get('global_ranking'):
                extra['global_ranking'] = True
            name = entry.get('name') or ' + '.join(
                f'{100 * w / sum(weights.values()):g}% {n}' for n, w in weights.items())
            add(f'{label}/{name}' if label else name,
                definition(name, chains, combiner, shown, **extra))
    return result, skipped


def split_chain(chain):
    """Teile eine Kette in Schritte vor 'translate', danach und das Verfahren."""
    *steps, method = chain
    if 'translate' not in steps:
        return steps, None, method
    position = steps.index('translate')
    return steps[:position], steps[position + 1:], method


def unsupported(method, chain, case):
    """Fehlende Ressourcen und unpassende Sprachen sind keine Nullscores."""
    languages = {e.get('language') for e in case['reference'] + case['student']
                 if e['label'].strip()}
    before, after, _ = split_chain(chain)
    if after is not None:
        if not languages <= {'de', 'en'}:
            return 'Übersetzung: nur de/en unterstützt'
        # Nach der Übersetzung ist jeder Text englisch.
        translated_languages = {'en'} if languages else set()
    else:
        translated_languages = languages
    if {'lemmatize', 'stem'} & set(before) and not languages <= {'de', 'en'}:
        return 'Lemma/stemming: only de/en supported'
    if is_wordvec(method):
        missing = [path for path in method['files'].values() if not (ROOT / path).is_file()]
        if missing:
            return 'Ressource fehlt: ' + ', '.join(missing)
        if not translated_languages <= set(method['files']):
            return 'Keine Wortvektoren für alle angegebenen Sprachen.'
        if method.get('nouns_only') and not translated_languages <= {'de', 'en'}:
            return 'Nomenfilter nur DE/EN.'
    elif 'languages' in method and not translated_languages <= set(method['languages']):
        return 'Nur ' + '/'.join(method['languages']) + ' unterstützt'
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


def provenance(engines, translator=None):
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
    # Alle Übersetzungen laufen über dieselbe Instanz.
    if translator is not None and translator.revision:
        models['translation'] = translator.revision
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

    Beide Arten liefern danach dasselbe Objekt mit compute_scores(). Die Schritte
    gelten für den Text, den das Verfahren selbst sieht (nach 'translate').
    """
    if is_wordvec(method):
        from .word_matching import WordMatching
        files = {lang: str(ROOT / path) for lang, path in method['files'].items()}
        return WordMatching({**method, 'files': files, 'preprocessing': steps},
                            name=name, models=models)
    engine = MatchingEngine({'methods': [name], 'preprocessing': steps,
                             'embedding_preprocessing': steps})
    if name in {'wordnet', 'translated_string', 'translated_embedding'}:
        engine.translator = translator
        if name == 'translated_embedding':
            engine.backends[name].translator = translator
    return engine


def translate_elements(elements, preprocessor, translator):
    """Wende die Schritte vor 'translate' an und übersetze; danach ist jedes Label englisch."""
    texts = [preprocessor.process(e['label'], e.get('language')) for e in elements]
    translated = translator.translate(texts, [e.get('language') for e in elements])
    return [{**e, 'label': text, 'language': 'en'} for e, text in zip(elements, translated)]


def calculate_features(cases, definitions, methods):
    """Berechne jede Kette pro Testfall genau einmal."""
    tasks = {}
    for spec in definitions.values():
        for chain in spec['chains'].values():
            tasks.setdefault(chain[-1], {})[tuple(chain)] = chain
    features, engines, errors = {}, {}, []
    translator = Translator({}, Cache())
    word_backends = {}
    # Große Wortmodelle zuerst: ein Modell wird einmal geladen, für alle
    # Ketten wiederverwendet und danach freigegeben.
    for method in sorted(tasks, key=lambda name: not is_wordvec(methods[name])):
        models = {}
        for key, chain in tasks[method].items():
            before, after, _ = split_chain(chain)
            preprocessor = Preprocessor(before) if after is not None else None
            engine = None
            for case in cases:
                reason = unsupported(methods[method], chain, case)
                if reason:
                    features[key, case['id']] = {'status': 'unsupported', 'reason': reason}
                    continue
                try:
                    if engine is None:
                        engine = make_engine(method, methods[method],
                                             before if after is None else after, translator, models)
                        if is_wordvec(methods[method]):
                            word_backends[method] = engine
                        else:
                            engines[key] = engine
                    reference, student = case['reference'], case['student']
                    load_before = LOAD_SECONDS[0]
                    started = time.perf_counter()
                    if after is not None:
                        reference = translate_elements(reference, preprocessor, translator)
                        student = translate_elements(student, preprocessor, translator)
                    result = engine.compute_scores(reference, student)
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
    for (chain, case_id), item in features.items():
        feature_records.append({'chain': list(chain), 'method': chain[-1],
                                'preprocessing': list(chain[:-1]), 'case': case_id, **item})
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
               'provenance': provenance(engines, translator),
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
