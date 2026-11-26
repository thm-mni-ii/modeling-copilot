"""Expliziter Regelbaum auf Ganzlabels; keine Wahrscheinlichkeit und kein Combined Score."""

import argparse
from collections import Counter
import gzip
import importlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import time

import numpy as np

from .compare import sha256
from .compare_component_lexicons import LexiconSources
from .evaluation import evaluate_case, nonempty_pairs, summarize
from .experiments import DEFAULT_CONFIG, ROOT, load_config
from synonym_matching.preprocessing import expand_modeling_abbreviations


def label_forms(items, mapping):
    """IDs und Originaldatensatz erhalten, nur Vergleichstexte zusätzlich expandieren."""
    return [{**e, 'label': expand_modeling_abbreviations(e['label'], e.get('language'),
                                                     abbreviations=mapping)} for e in items]


def production_modules():
    """Lese produktive Textmethoden unter eigenem Namen, ohne Forschung zu überschreiben."""
    path = ROOT.parent / 'synonym-matching/src/synonym_matching'
    name = '_decision_tree_production'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path / '__init__.py',
                                                     submodule_search_locations=[str(path)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    registry = importlib.import_module(name + '.methods.registry')
    # Der reine Textadapter des Graphmatchers nutzt zwei benachbarte Hilfsmodule.
    graph_path = ROOT.parent / 'one-to-one-graph-matching/src'
    spec = importlib.util.spec_from_file_location('_decision_tree_text', graph_path / 'text_similarity.py')
    adapter = importlib.util.module_from_spec(spec)
    previous = sys.path[:]
    try:
        sys.path[:0] = [str(graph_path), str(path)]
        spec.loader.exec_module(adapter)
    finally:
        sys.path[:] = previous
    return registry, adapter


def decide(features, text, *, embedding_action='confirm', valid=True):
    """Erst eindeutige Relationen, dann kanonische/lexikalische/semantische Evidenz.

    Genau ein Synset ist nur eine konservative Näherung, keine echte Disambiguierung.
    Fehlende Gegenrelation ist kein Beweis für Gleichwertigkeit.
    """
    if embedding_action not in {'confirm', 'open'}:
        raise ValueError('embedding_action must be confirm or open')
    if not valid:
        return 'not_evaluable', 'empty_or_ineligible'
    known = features['pair_known'] == 1
    single = known and features['reference_synset_count'] == features['student_synset_count'] == 1
    shared = features['shared_synset'] == 1
    counter = any(features[name] == 1 for name in ('antonym', 'reference_hypernym', 'reference_hyponym'))
    if known and counter:
        if not single or shared:
            return 'open', 'ambiguous_or_conflicting_relation'
        return 'rejected', 'single_sense_counterrelation'
    if single and shared:
        return 'confirmed', 'single_sense_shared_synset'
    if text.get('veto') == 'digit_mismatch':
        return 'rejected', 'digit_mismatch'
    if text['status'] == 'supported':
        tier = text['tier']
        if tier == 'meaning' and embedding_action == 'open':
            return 'open', 'semantic_similarity_only'
        return 'confirmed', tier
    return 'open', 'insufficient_evidence'


def _read(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def _summary(cases, records, names, changed=False):
    output = {}
    by_id = {case['id']: case for case in cases}
    for name in names:
        counts, metrics = Counter(), []
        for record in records:
            if record['variant'] != name:
                continue
            case = by_id[record['case']]
            shape = (len(case['reference']), len(case['student']))
            verdict = np.asarray(record['verdicts']).reshape(shape)
            valid = np.asarray(record['eligible'], dtype=bool).reshape(shape)
            predicted = verdict == 'confirmed'
            if changed:
                ids = set(case.get('changed_student_ids', []))
                columns = [j for j, e in enumerate(case['student']) if e['id'] in ids]
                if not columns:
                    continue
                case = {**case, 'reference': [case['student'][j] for j in columns],
                        'student': case['reference'],
                        'annotations': [[row[j] for row in case['annotations']] for j in columns]}
                predicted, valid, verdict = predicted.T[columns], valid.T[columns], verdict.T[columns]
            metrics.append(evaluate_case(case, predicted.astype(float), .5, eligible=valid))
            # Top-1 wird hier bewusst nicht aus binären Entscheidungen erzeugt.
            counts.update(verdict[valid].tolist())
        if metrics:
            totals = summarize(metrics)
            for key in ('top1', 'queries'):
                totals.pop(key)
            output[name] = {**totals, 'verdict_counts': dict(counts),
                            'automatic_decision_coverage': (counts['confirmed'] + counts['rejected']) / sum(counts.values())
                            if counts else 0}
    return output


def run(config):
    settings = config['decision_tree']
    registry, adapter = production_modules()
    random.seed(config['seed'])
    np.random.seed(config['seed'])
    methods = registry.resolve_methods(['damerau_canonical', 'multilingual_expanded'])
    states = {m.state_key: m.initialize() if m.initialize else None for m in methods}
    lexicons = LexiconSources()
    # Geänderte deutsche Kürzel dürfen nicht mit veralteten WordNet-Merkmalen
    # des Originaltexts bewertet werden. Übersetzung nutzt den vorhandenen Cache.
    from synonym_matching import MatchingEngine
    from synonym_matching.combinations import SEMANTIC_FEATURES
    wordnet_engine = MatchingEngine({'methods': ['wordnet'],
        'preprocessing': ['normalize'], 'semantic_features': {'wordnet': list(SEMANTIC_FEATURES)}})
    names = ['text_tiers'] + [f'{source}_{action}' for source in settings['lexicons']
                            for action in settings['embedding_actions']]
    paths = [ROOT / d['output'] for d in settings['datasets']]
    if len(set(paths)) != len(paths) or any(p.exists() for p in paths):
        raise FileExistsError('choose distinct, new output filenames')
    for dataset, output in zip(settings['datasets'], paths):
        path = ROOT / dataset['source']
        saved = _read(path)
        if saved['seed'] != config['seed']:
            raise ValueError('seed differs from saved source')
        whole = {(f['case'], f['method']): f for f in saved['features']}
        records, feature_records = [], []
        for case in saved['dataset']['cases']:
            started = time.perf_counter()
            original = [case['reference'], case['student']]
            mapping = settings.get('modeling_abbreviations', {})
            left, right = [label_forms(items, mapping) for items in original]
            changed = [left, right] != original
            shape = (len(left), len(right))
            valid = nonempty_pairs([e['label'] for e in left], [e['label'] for e in right])
            raw = {}
            for method in methods:
                sides = []
                for items in (left, right):
                    texts = [e['label'] for e in items]
                    for step in method.preprocessing:
                        texts = [registry.PREPROCESSORS[step](text) for text in texts]
                    sides.append(texts)
                raw[method.name] = method.compute(states[method.state_key], *sides)
            candidates = {'methods': [{'name': m.name, 'scoreRange': m.score_range} for m in methods],
                'synonymMatrix': [{'referenceElementId': a['id'], 'referenceLabel': a['label'],
                    'matches': [{'submissionElementId': b['id'], 'submissionLabel': b['label'],
                                 'scoreStatus': 'scored', 'scores': {k: float(v[i,j]) for k,v in raw.items()}}
                                for j,b in enumerate(right)]} for i,a in enumerate(left)]}
            thresholds = settings['thresholds']
            tiers = [{'name': 'canonical', 'minimumSimilarity': {'damerau_canonical': 1.}},
                     {'name': 'spelling', 'minimumSimilarity': {'damerau_canonical': thresholds['spelling']}},
                     {'name': 'meaning', 'minimumSimilarity': {'multilingual_expanded': thresholds['meaning']},
                      'confirmationFloor': {'multilingual_expanded': thresholds['meaning_floor']}}]
            text = adapter.pair_similarity(candidates, adapter.configured_tiers(candidates, {'textEvidence': {'tiers': tiers}}))
            sources = {}
            for source in settings['lexicons']:
                if source == 'wordnet':
                    if changed:
                        recalculated = wordnet_engine.compute_scores(left, right)
                        sources[source] = {'shared_synset': recalculated['scores']['wordnet'],
                                           **recalculated['semantic_features']['wordnet']}
                        continue
                    part = whole[case['id'], 'wordnet']
                    if part['status'] != 'ok':
                        raise ValueError('missing successful whole-label WordNet features')
                    sources[source] = {'shared_synset': np.asarray(part['scores']).reshape(shape),
                        **{k: np.asarray(v).reshape(shape) for k,v in part['relation_features'].items()}}
                else:
                    shared, values, _ = lexicons.matrices(left, right, linked=source == 'ili')
                    sources[source] = {**values, 'shared_synset': shared}
            feature_records.append({'case': case['id'], 'scores': {k:v.tolist() for k,v in raw.items()},
                'lexicons': {s:{k:v.tolist() for k,v in fs.items()} for s,fs in sources.items()},
                'comparison_labels': {'reference': left, 'student': right},
                'candidate_labels': {side: label_forms(items, settings.get('candidate_abbreviations', {}))
                                     for side,items in [('reference', left), ('student', right)]},
                'seconds': time.perf_counter() - started})
            for name in names:
                verdicts, reasons = np.full(shape, 'open', dtype=object), np.full(shape, '', dtype=object)
                for i,a in enumerate(left):
                    for j,b in enumerate(right):
                        evidence = text[a['id'],b['id']]
                        if name == 'text_tiers':
                            verdicts[i,j] = 'not_evaluable' if not valid[i,j] else 'confirmed' if evidence['status'] == 'supported' else 'open'
                            reasons[i,j] = evidence['tier'] or evidence['veto'] or 'insufficient_evidence'
                        else:
                            source, action = name.rsplit('_',1)
                            values = {k:float(v[i,j]) for k,v in sources[source].items()}
                            verdicts[i,j], reasons[i,j] = decide(values, evidence, valid=bool(valid[i,j]), embedding_action=action)
                matrix = []
                for i,a in enumerate(left):
                    matches = []
                    for j,b in enumerate(right):
                        scores = {k:float(v[i,j]) for k,v in raw.items()}
                        if name != 'text_tiers':
                            scores.update({k:float(v[i,j]) for k,v in sources[name.rsplit('_',1)[0]].items()})
                        matches.append({'submissionElement': case['student'][j], 'scores': scores,
                                        'verdict': verdicts[i,j], 'reason': reasons[i,j]})
                    matrix.append({'referenceElement': case['reference'][i], 'matches': matches})
                records.append({'variant': name, 'case': case['id'], 'eligible': valid.tolist(),
                                'verdicts': verdicts.tolist(), 'reasons': reasons.tolist(),
                                'synonymMatrix': matrix})
        result = {'seed': config['seed'], 'config': settings, 'dataset': saved['dataset'],
                  'source': {'path': str(path), 'sha256': sha256(path)},
                  'source_hashes': {str(p):sha256(p) for p in [Path(__file__),
                    ROOT/'src/synonym_matching/preprocessing.py',
                    ROOT/'src/synonym_matching/lexicons.py',
                    ROOT/'research/compare_component_lexicons.py',
                    ROOT.parent/'synonym-matching/src/synonym_matching/methods/registry.py',
                    ROOT.parent/'synonym-matching/src/synonym_matching/preprocessing.py',
                    ROOT.parent/'one-to-one-graph-matching/src/text_similarity.py']},
                  'embedding': states['multilingual'].resource_metadata(),
                  'features': feature_records, 'records': records,
                  'summary': _summary(saved['dataset']['cases'], records, names),
                  'changed_labels': _summary(saved['dataset']['cases'], records, names, changed=True),
                  'policy': 'Label-only benchmark; productive text adapter, no glossary, segment sources or graph context. '
                            'Open/not-evaluable are not confirmed. Binary predictions used only for P/R/F1, not as similarity scores. '
                            'No Top-1 from binary verdicts or global assignment; single-sense guard is not WSD. Known development data.'}
        output.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(output, 'wt', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, allow_nan=False)
        print(dataset['name'], flush=True)
        for name,m in (result['changed_labels'] or result['summary']).items():
            print(f'{name}: TP={m["tp"]} FP={m["fp"]} FN={m["fn"]} F1={m["f1"]:.4f} '
                  f'offen={m["verdict_counts"].get("open",0)}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    run(load_config(args.config))


if __name__ == '__main__':
    main()
