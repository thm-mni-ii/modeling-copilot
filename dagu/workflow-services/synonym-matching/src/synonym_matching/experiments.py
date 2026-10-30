"""Vergleiche feste Pipelines, ohne den Service oder seine API zu verändern.

Ein JSON enthält Konfiguration, Rohscores, Entscheidungen und Metriken. Die
Markdown-Datei ist die kurze Übersicht. Es wird nichts auf Testlabels trainiert.
"""

import hashlib
import importlib.metadata
import json
import platform
import time
from pathlib import Path

import numpy as np

from .assignment import select_matches
from .engine import MatchingEngine, nonempty_pairs
from .evaluation import evaluate_case, summarize
from .lexicons import DATA_DIR
from .variants import REQUIRES, evaluate_variant

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
# Diese Aliasfunktionen bleiben für bestehende API-Aufrufer erhalten.
ALIASES = {
    'translation_string', 'translation_monolingual', 'multilingual_only',
    'string_multilingual', 'weighted_fusion',
}


def catalogue(models=False, lexicons=False):
    """Erstelle eindeutige Spezifikationen statt mehrfacher Namen für dieselbe Formel."""
    methods = list(STRING_METHODS) + ['exact_match']
    if models:
        methods += ['multilingual', 'translated_embedding', 'translated_string']
    if lexicons:
        methods += ['wordnet', 'openthesaurus']
    specs = [{'name': name, 'kind': 'single', 'requires': [name]} for name in methods]
    for name, requires in REQUIRES.items():
        if name not in ALIASES and set(requires) <= set(methods):
            specs.append({'name': name, 'kind': 'variant', 'requires': list(requires)})
    if models:
        for embedding_weight in (.25, .5, .75):
            string_weight = 1 - embedding_weight
            specs.append({
                'name': f'string_multi_{int(string_weight * 100)}_{int(embedding_weight * 100)}',
                'kind': 'variant', 'function': 'weighted_fusion',
                'requires': list(REQUIRES['weighted_fusion']),
                'options': {'embedding_weight': embedding_weight},
            })
    if lexicons:
        for lexicon in ('wordnet', 'openthesaurus'):
            specs.append({'name': lexicon + '_string', 'kind': 'lexicon_string',
                          'requires': [lexicon] + list(REQUIRES['string_ensemble'])})
            if models:
                specs.append({'name': lexicon + '_multilingual', 'kind': 'mean',
                              'requires': [lexicon, 'multilingual']})
        specs.append({'name': 'wordnet_openthesaurus', 'kind': 'mean',
                      'requires': ['wordnet', 'openthesaurus']})
    return methods, specs


def combine_spec(spec, raw):
    """Begrenze Scores wie im Service; Lexikon-Hybride gewichten beide Seiten gleich."""
    selected = {name: np.clip(raw[name], 0, 1) for name in spec['requires']}
    if spec['kind'] == 'single':
        return selected[spec['requires'][0]]
    if spec['kind'] == 'variant':
        return evaluate_variant(spec.get('function', spec['name']), selected,
                                **spec.get('options', {}))
    if spec['kind'] == 'lexicon_string':
        lexical = selected[spec['requires'][0]]
        return (lexical + evaluate_variant('string_ensemble', selected)) / 2
    return np.mean(list(selected.values()), axis=0)


def unsupported(method, steps, case):
    """Unpassende Sprachen sind fehlende Abdeckung, keine Nullscores."""
    languages = {e.get('language') for e in case['reference'] + case['student']
                 if e['label'].strip()}
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
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(engines):
    """Speichere die Umgebung und tatsächlich geladenen Modellrevisionen."""
    packages = {}
    for name in ('numpy', 'scipy', 'nltk', 'spacy', 'rapidfuzz', 'torch',
                 'transformers', 'sentence-transformers', 'de_core_news_sm',
                 'en_core_web_sm'):
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
    from .methods import EMBEDDING_MODELS
    resources = {}
    for name in ('openthesaurus.txt', 'nltk_data/corpora/wordnet.zip'):
        path = DATA_DIR / name
        if path.exists():
            resources[name] = sha256(path)
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'packages': packages, 'models': models, 'model_names': EMBEDDING_MODELS,
            'translation_model': 'Helsinki-NLP/opus-mt-de-en',
            'resources': resources,
            'source_hashes': {p.name: sha256(p) for p in Path(__file__).parent.glob('*.py')}}


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


def run_experiments(data, output, *, models=False, lexicons=False, threshold=.5,
                    pipelines=None, strategies=STRATEGIES):
    """Berechne gemeinsame Features einmal; vergleiche alle Varianten ohne Tuning."""
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('threshold must be in [0,1]')
    output = Path(output)
    if output.exists() or output.with_suffix('.md').exists():
        raise FileExistsError('choose a new output filename')
    pipelines = PIPELINES if pipelines is None else pipelines
    if not pipelines or not data.get('cases'):
        raise ValueError('nonempty pipelines and cases required')
    case_ids = [case['id'] for case in data['cases']]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError('case IDs must be unique')
    if not strategies or set(strategies) - set(STRATEGIES):
        raise ValueError('unknown or empty assignment strategies')
    methods, specs = catalogue(models, lexicons)
    engines, features, errors = {}, {}, []
    records, definitions = [], {}
    started = time.perf_counter()

    def feature(method, pipeline, case):
        """Cache-Schlüssel enthält die tatsächlich wirksame Verarbeitungskette."""
        steps = pipelines[pipeline] if method in STRING_METHODS else ['normalize']
        key = (method, tuple(steps))
        cache_key = (key, case['id'])
        if cache_key in features:
            return features[cache_key]
        reason = unsupported(method, steps, case)
        if reason:
            item = {'status': 'unsupported', 'reason': reason}
        else:
            try:
                if key not in engines:
                    engines[key] = MatchingEngine({'methods': [method],
                                                   'preprocessing': steps})
                    # Über die Sprachpfade hinweg keine identische Übersetzung wiederholen.
                    if method in {'wordnet', 'translated_string', 'translated_embedding'}:
                        for other in engines.values():
                            if other is not engines[key] and any(n in other.methods for n in
                                    {'wordnet', 'translated_string', 'translated_embedding'}):
                                engines[key].translator = other.translator
                                if method == 'translated_embedding':
                                    engines[key].backends[method].translator = other.translator
                                break
                t0 = time.perf_counter()
                result = engines[key].match(case['reference'], case['student'])
                seconds = time.perf_counter() - t0
                texts = result['processedLabels'][method]
                item = {'status': 'ok', 'scores': result['scores'][method],
                        'shape': result['shape'], 'seconds': seconds,
                        'processedLabels': texts,
                        'eligible': nonempty_pairs(texts['reference'], texts['student']).tolist()}
            except Exception as error:
                item = {'status': 'error', 'reason': f'{type(error).__name__}: {error}'}
                errors.append({'method': method, 'pipeline': pipeline,
                               'case': case['id'], 'reason': item['reason']})
        features[cache_key] = item
        return item

    for spec in specs:
        # Embeddings/Lexika/Exact Match bleiben invariant und laufen nur einmal.
        affected = bool(set(spec['requires']) & set(STRING_METHODS))
        active_pipelines = list(pipelines) if affected else [next(iter(pipelines))]
        for pipeline in active_pipelines:
            label = pipeline if affected else 'fixed'
            identifier = label + '/' + spec['name']
            definitions[identifier] = {'preprocessing': pipelines[pipeline] if affected else ['normalize'],
                                       'embedding_preprocessing': ['normalize'], **spec}
            for case in data['cases']:
                parts = {name: feature(name, pipeline, case) for name in spec['requires']}
                base = {'experiment': identifier, 'case': case['id']}
                missing = {n: p for n, p in parts.items() if p['status'] != 'ok'}
                if missing:
                    records.append({**base, 'status': 'unavailable', 'missing': missing})
                    continue
                shape = (len(case['reference']), len(case['student']))
                raw = {n: np.asarray(p['scores']).reshape(shape) for n, p in parts.items()}
                eligible = np.logical_or.reduce([
                    np.asarray(p['eligible'], dtype=bool).reshape(shape) for p in parts.values()])
                eligible &= nonempty_pairs([e['label'] for e in case['reference']],
                                           [e['label'] for e in case['student']])
                t0 = time.perf_counter()
                scores = combine_spec(spec, raw)
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
    payload = {'version': 1, 'seed': 42, 'threshold': threshold,
               'score_policy': 'raw cosine [-1,1]; combinations clip to [0,1]; no calibration',
               'timing_policy': 'sequential CPU; shared cached features; load time included on first use',
               'dataset': data, 'definitions': definitions, 'features': feature_records,
               'records': records, 'errors': errors, 'provenance': provenance(engines),
               'score_statistics': score_statistics(feature_records),
               'dataset_sha256': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
               'elapsed_seconds': time.perf_counter() - started}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    write_report(output.with_suffix('.md'), payload)
    return errors


def write_report(path, payload):
    """Vergleiche nur auf identischen Fällen; zeige zusätzlich Abdeckung und Fehler."""
    records = payload['records']
    definitions = payload['definitions']
    nonempty = {c['id'] for c in payload['dataset']['cases'] if c['reference'] and c['student']}
    supported = {name: {r['case'] for r in records if r['experiment'] == name and r['status'] == 'ok'}
                 for name in definitions}
    common = nonempty.intersection(*supported.values())
    hard = {c['id'] for c in payload['dataset']['cases']
            if c['case_number'] in range(15, 21) or c['case_number'] == 27 or c.get('hard_negative')}
    multi = {c['id'] for c in payload['dataset']['cases'] if len(c['student']) > 1}
    lines = ['# Erweiterter Vergleich', '',
             f"Fester Threshold: {payload['threshold']}; Seed: 42. Kein Tuning/Training.",
             f'Gemeinsame nichtleere Fälle: {len(common)}. IDs: {sorted(common)}',
             'Top-1 bezieht sich auf die unveränderte Score-Rangliste, nur bei mehreren Kandidaten.',
             'MBM erhält Gleichstände; Hungarian erlaubt Nichtzuordnung und erzwingt höchstens 1:1.',
             'Recall kann bei mehreren korrekten Alternativen durch 1:1 sinken: Annotationen sind nicht eindeutige Identitätszuordnungen.',
             'Alle Rohscores, Entscheidungen und Metriken je Fall stehen im JSON.', '',
             '| Pipeline | Zuordnung | Abdeckung | Precision | Recall | F1 | Top-1 | FP schwierig | s Features* | s Kombination+Zuordnung |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in definitions:
        available = [r for r in records if r['experiment'] == name and r['status'] == 'ok']
        rows = [r for r in available if r['case'] in common]
        strategies = list(available[0]['decisions']) if available else []
        for strategy in strategies:
            metrics = summarize([r['decisions'][strategy]['metrics'] for r in rows])
            top = summarize([r['decisions'][strategy]['metrics'] for r in rows if r['case'] in multi])
            top1 = f"{top['top1'] / top['queries']:.3f}" if top['queries'] else 'n/a'
            fp = sum(r['decisions'][strategy]['metrics']['fp'] for r in rows if r['case'] in hard)
            seconds = sum(r['combine_seconds'] + r['decisions'][strategy]['seconds'] for r in rows)
            feature_seconds = sum(r['feature_seconds'] for r in rows)
            scores = f"{metrics['precision']:.3f} | {metrics['recall']:.3f} | {metrics['f1']:.3f}" if common else 'n/a | n/a | n/a'
            lines.append(f'| {name} | {strategy} | {len(supported[name] & nonempty)} | {scores} | {top1} | {fp} | {feature_seconds:.4f} | {seconds:.4f} |')
    # Ohne die rein deutsche Ressource bleiben Übersetzungen und Graphfall sichtbar.
    core_names = [name for name in definitions
                  if name.startswith(('fixed/', 'lowercase/'))
                  and 'openthesaurus' not in definitions[name]['requires']]
    if core_names:
        core_cases = nonempty.intersection(*(supported[name] for name in core_names))
        lines += ['', '## Kernvergleich auf gemeinsamer DE/EN-Abdeckung', '',
                  f'Fälle: {sorted(core_cases)}. Nur Threshold-Auswahl; keine Gewichtsoptimierung.', '',
                  '| Pipeline | Precision | Recall | F1 | Top-1 (mehrere Kandidaten) |',
                  '| --- | ---: | ---: | ---: | ---: |']
        for name in core_names:
            rows = [r for r in records if r['experiment'] == name
                    and r['status'] == 'ok' and r['case'] in core_cases]
            stats = summarize([r['decisions']['threshold']['metrics'] for r in rows
                               if 'threshold' in r['decisions']])
            ranking = summarize([r['decisions']['threshold']['metrics'] for r in rows
                                 if r['case'] in multi and 'threshold' in r['decisions']])
            accuracy = ranking['top1'] / ranking['queries'] if ranking['queries'] else 0
            lines.append(f"| {name} | {stats['precision']:.3f} | {stats['recall']:.3f} | {stats['f1']:.3f} | {accuracy:.3f} |")
    lines += ['', '## Prüfung der Score-Skalen', '',
              '| Methode/Preprocessing | n | Min | Max | Mittel | Nullanteil | Einsanteil | negative Rohscores |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name, stats in payload['score_statistics'].items():
        if name.endswith('/normalize,lowercase') or name.split('/')[0] not in STRING_METHODS:
            lines.append(f"| {name} | {stats['n']} | {stats['min']:.3f} | {stats['max']:.3f} | {stats['mean']:.3f} | {stats['zero_fraction']:.3f} | {stats['one_fraction']:.3f} | {stats['negative_count']} |")
    lines += ['', '*Featurezeiten werden zwischen Varianten geteilt; keine isolierten End-to-End-Zeiten.',
              'Cosinus, Stringähnlichkeit und binäre Lexikonevidenz sind keine kalibrierten Wahrscheinlichkeiten.',
              'Keine Min-Max-Normalisierung pro Testmatrix, keine Auswahl von Gewichten anhand der Testlabels.',
              'Bei fehlenden Ressourcen wird keine Nullleistung erfunden; Abdeckung/Fehler im JSON prüfen.',
              f"Technische Fehler: {len(payload['errors'])}. Gesamtlaufzeit: {payload['elapsed_seconds']:.2f} s.",
              'Logistic Regression zurückgestellt: kein unabhängiger gruppierter Trainings-/Validierungs-/Testdatensatz vorhanden.']
    path.write_text('\n'.join(lines) + '\n')
