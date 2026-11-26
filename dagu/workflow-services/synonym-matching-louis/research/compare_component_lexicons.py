"""Vergleiche Lexikonquellen auf gespeicherten Komponenten, ohne Embeddingläufe."""

import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import time

import numpy as np

from synonym_matching.component_evidence import ComponentEvidence
from synonym_matching.combinations import component_evidence_fusion
from synonym_matching.lexicons import WordNet, OdeNet, RELATION_FEATURES
from .compare import sha256
from .evaluation import evaluate_case, select_matches, summarize
from .experiments import DEFAULT_CONFIG, load_config
from .rank_results import changed_label_rankings


class LexiconSources:
    """Cache Original- und ILI-Profile; nutze die bestehende Relationsberechnung."""

    def __init__(self):
        self.backends = {'en': WordNet(), 'de': OdeNet()}
        self.linked = {}
        self.relations = WordNet()

    def profile(self, element, linked=False):
        language, text = element['language'], element['label']
        if language not in self.backends:
            raise ValueError('lexicon comparison requires explicit de/en language')
        source = self.backends[language]
        original = source._relation_profile(text)
        if not linked or language == 'en':
            return original
        key = (language, text)
        if key not in self.linked:
            english = self.backends['en']
            if english.reader is None:
                english._load()
            identifiers = source.translate(text)
            nodes = [english.reader.synset(identifier) for identifier in identifiers]
            senses = {sense.id: sense for identifier in original['senses']
                      for sense in source.reader.sense(identifier).translate(lexicon=english.version)}
            self.linked[key] = {
                'synsets': identifiers, 'nodes': nodes,
                'ancestors': {node.id for synset in nodes
                              for node in synset.closure('hypernym', 'instance_hypernym')
                              if node.id != synset.id},
                'antonym_synsets': {node.id for synset in nodes
                                   for node in synset.relations('antonym').get('antonym', [])},
                'senses': set(senses),
                'antonym_senses': {other.id for sense in senses.values()
                                  for other in sense.relations('antonym').get('antonym', [])},
            }
        return self.linked[key]

    def matrices(self, reference, student, linked=False):
        """Direkte Vergleiche verschiedener Sprachen bleiben nicht vergleichbar."""
        elements = reference + student
        keys = [f'element{i}' for i in range(len(elements))]
        profiles = [self.profile(e, linked) for e in elements]
        # Die bestehenden Relationsformeln werden unverändert wiederverwendet.
        self.relations.relation_cache = dict(zip(keys, profiles, strict=True))
        left, right = keys[:len(reference)], keys[len(reference):]
        values = self.relations.relation_features(left, right, list(RELATION_FEATURES))
        shape = (len(reference), len(student))
        shared = np.zeros(shape)
        comparable = np.zeros(shape)
        for i, a in enumerate(reference):
            for j, b in enumerate(student):
                valid = linked or a['language'] == b['language']
                comparable[i, j] = valid
                if valid:
                    shared[i, j] = bool(profiles[i]['synsets'] & profiles[len(reference)+j]['synsets'])
        for name in values:
            if name not in {'reference_synset_count', 'student_synset_count'}:
                values[name] *= comparable
        if linked:
            # Eine ILI-Abbildung darf Mehrdeutigkeit des Originalworts nicht verstecken.
            original_counts = [len(self.profile(e)['synsets']) for e in elements]
            for i in range(len(reference)):
                values['reference_synset_count'][i, :] = np.maximum(
                    values['reference_synset_count'][i, :], original_counts[i])
            for j in range(len(student)):
                values['student_synset_count'][:, j] = np.maximum(
                    values['student_synset_count'][:, j], original_counts[len(reference)+j])
            # Bekannt, aber ohne ILI-Verbindung bleibt pair_known=0, keine negative Evidenz.
        return shared, values, comparable

    def odenet_matrices(self, reference, student):
        """Alle Texte in OdeNet nachschlagen, ohne Sprachangaben vorauszusetzen.

        Die interne Quellenwahl de bezeichnet nur das Lexikon, keine erkannte
        Sprache. Originalelemente und ihre Metadaten werden nicht verändert.
        """
        left = [{**e, 'language': 'de'} for e in reference]
        right = [{**e, 'language': 'de'} for e in student]
        return self.matrices(left, right)


def combine_sources(first, second):
    """Nutze verfügbare Evidenz; bei Synonym-/Gegenrelation-Konflikt enthalte dich."""
    result = deepcopy(first)
    for name in result:
        if name not in {'string_similarity', 'embedding_similarity',
                        'levenshtein', 'jaro_winkler', 'char_trigram', 'ontology_similarity'}:
            result[name] = np.maximum(first[name], second[name])
    positive = (first['shared_synset_fraction'] > 0) | (second['shared_synset_fraction'] > 0)
    negative = sum(first[n] + second[n] for n in
                   ('antonym_relation', 'hypernym_relation', 'hyponym_relation')) > 0
    conflict = positive & negative
    # Keine widersprüchliche Evidenz in den unveränderten Fusionsregeln verwenden.
    for name in ('lexicon_coverage', 'shared_synset_fraction', 'shared_synset',
                 'full_synonym_evidence', 'antonym_evidence', 'hierarchy_evidence'):
        result[name] = np.where(conflict, 0., result[name])
    return result, conflict


def run_comparison(source, output, config):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError('choose a new output filename')
    opener = gzip.open if source.suffix == '.gz' else open
    with opener(source, 'rt', encoding='utf-8') as stream:
        saved = json.load(stream)
    if (saved['seed'], saved['threshold']) != (config['seed'], config['threshold']):
        raise ValueError('seed and threshold must match the saved experiment')
    settings = config['component_lexicon_comparison']
    options = settings['fusion_options']
    sources = LexiconSources()
    records = []
    cases = {case['id']: case for case in saved['dataset']['cases']}
    for part in saved['features']:
        if part.get('chain') != ['normalize', 'component_evidence'] or part['status'] != 'ok':
            continue
        case = cases[part['case']]
        evidence = part['component_evidence']
        reference, student = evidence['reference_components'], evidence['student_components']
        unique = [reference, student]
        indices = [evidence['reference_indices'], evidence['student_indices']]
        raw = {'scores': {k: np.asarray(v).reshape(evidence['shape'])
                          for k, v in evidence['scores'].items()}}
        # Derselbe Aggregator, dieselbe Teilzuordnung und dieselben S/E-Werte.
        aggregator = ComponentEvidence.__new__(ComponentEvidence)
        shape = (len(case['reference']), len(case['student']))
        features = {'translated_wordnet': {k: np.asarray(v).reshape(shape)
                                          for k, v in part['component_features'].items()}}
        diagnostics = {}
        started = time.perf_counter()
        for variant, linked in [('native', False), ('ili', True)]:
            shared, relations, comparable = sources.matrices(reference, student, linked)
            raw['scores']['wordnet'] = shared
            raw['semantic_features'] = {'wordnet': relations}
            aggregator.aggregate(raw, unique, indices, case['reference'], case['student'])
            features[variant] = deepcopy(aggregator.features)
            diagnostics[variant] = {
                'shared_synset': shared.tolist(), 'relations': {k: v.tolist() for k, v in relations.items()},
                'comparable': comparable.tolist(),
                'lexicons': {lang: backend.version for lang, backend in sources.backends.items()},
                'coverage': [{'element': e, 'source_synsets': len(sources.profile(e)['synsets']),
                              'evaluated_synsets': len(sources.profile(e, linked)['synsets'])}
                             for e in reference + student],
            }
        features['combined'], conflict = combine_sources(features['translated_wordnet'], features['native'])
        seconds = time.perf_counter() - started
        eligible = np.asarray(part['eligible'], dtype=bool).reshape(shape)
        for variant in settings['sources']:
            values = features[variant]
            for name in ('string_similarity', 'embedding_similarity'):
                if not np.array_equal(values[name], features['translated_wordnet'][name]):
                    raise AssertionError('lexicon comparison changed string/embedding scores')
            scores = component_evidence_fusion(values, **options)
            decisions = {}
            for strategy in config['strategies']:
                selected = select_matches(scores, eligible, config['threshold'], strategy)
                decisions[strategy] = {'selected': selected.tolist(), 'seconds': 0., 'metrics': evaluate_case(
                    case, scores, config['threshold'], eligible=eligible, selected=selected)}
            records.append({'case': case['id'], 'source': variant, 'experiment': variant,
                            'status': 'ok', 'shape': list(shape),
                            'feature_seconds': 0., 'combine_seconds': 0.,
                            'combinedScores': scores.tolist(), 'decisions': decisions,
                            'features': {k: v.tolist() for k, v in values.items()},
                            'conflicts': conflict.tolist() if variant == 'combined' else None})
        diagnostics['seconds_all_new_lexicon_sources'] = seconds
        part['lexicon_comparison'] = diagnostics
    if not records:
        raise ValueError('no successful normalize/component_evidence features in source')
    summary = {variant: {strategy: summarize([r['decisions'][strategy]['metrics'] for r in records
                                             if r['source'] == variant])
                         for strategy in config['strategies']} for variant in settings['sources']}
    result = {'seed': saved['seed'], 'threshold': saved['threshold'], 'config': settings,
              'feature_source': {'path': str(source), 'sha256': sha256(source)},
              'source_hash': sha256(Path(__file__)), 'dataset': saved['dataset'],
              'records': records, 'summary': summary,
              'component_diagnostics': [p for p in saved['features'] if 'lexicon_comparison' in p],
              'timing_policy': 'Only new lexical work timed jointly; cached S/E and baseline timings excluded.'}
    result['changed_labels'] = {}
    for variant in settings['sources']:
        view = {**saved, 'records': [r for r in records if r['source'] == variant],
                'definitions': {variant: {'methods': ['component_evidence'],
                    'chains': {'component_evidence': ['normalize', 'component_evidence']},
                    'combiner': {'kind': 'mean'}}}}
        ranking = changed_label_rankings(view, 'threshold')
        if ranking:
            result['changed_labels'][variant] = ranking['overall_complete']['top3'][0]['metrics']
    output.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if output.suffix == '.gz' else open
    with opener(output, 'wt', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    result = run_comparison(args.features, args.output, load_config(args.config))
    print('Nur geänderte Schülerlabels:' if result['changed_labels'] else 'Alle Fälle:')
    for source, strategies in result['summary'].items():
        m = result['changed_labels'].get(source, strategies['threshold'])
        print(f'{source}: P={m["precision"]:.4f} R={m["recall"]:.4f} F1={m["f1"]:.4f}'
              f' TP={m["tp"]} FP={m["fp"]} FN={m["fn"]}')
    print(args.output)


if __name__ == '__main__':
    main()
