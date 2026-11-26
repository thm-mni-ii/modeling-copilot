"""Drei parallele Lexikonpfade mit Path-/Wu-Palmer-Ablationen auf denselben Fällen."""

import argparse
import gzip
import json
from pathlib import Path
import random
import time

import numpy as np

from synonym_matching.cache import Cache
from synonym_matching.lexicons import WordNet, OdeNet, RELATION_FEATURES
from synonym_matching.preprocessing import normalize
from synonym_matching.translation import Translator
from .compare import sha256
from .decision_tree import decide, production_modules, _summary
from .experiments import DEFAULT_CONFIG, ROOT, load_config


def validate_cases(data):
    """Die beiden Sprachfassungen müssen dieselben IDs, Größen und Goldurteile haben."""
    identities = set()
    for case in data['cases']:
        if case['id'] in identities:
            raise ValueError('duplicate case id')
        identities.add(case['id'])
        for side in ('reference', 'student'):
            a, b = case['de'][side], case['en'][side]
            if [e['id'] for e in a] != [e['id'] for e in b] or len({e['id'] for e in a}) != len(a):
                raise ValueError('paired variants need identical unique IDs and order')
            if any(not e['label'].strip() for e in a+b):
                raise ValueError('this language comparison requires nonempty labels')
        if (len(case['annotations']) != len(case['de']['reference']) or
                any(len(row) != len(case['de']['student']) or
                    any(v not in {'correct', 'incorrect'} for v in row) for row in case['annotations'])):
            raise ValueError('invalid paired annotations')


def run(config):
    settings = config['language_path_comparison']
    source, output = ROOT/settings['data'], ROOT/settings['output']
    if output.exists():
        raise FileExistsError('choose a new output filename')
    data = json.loads(source.read_text())
    validate_cases(data)
    random.seed(config['seed'])
    np.random.seed(config['seed'])
    registry, adapter = production_modules()
    methods = registry.resolve_methods(['damerau_canonical', 'multilingual_expanded'])
    states = {m.state_key: m.initialize() if m.initialize else None for m in methods}
    english, german = WordNet(), OdeNet()
    cache = Cache()
    translator = Translator({}, cache)
    loads = {}
    for name, initialize in [('wordnet', english._load), ('odenet', german._load),
                             ('embedding', states['multilingual']._load), ('translation', translator._load)]:
        started = time.perf_counter()
        initialize()
        loads[name] = time.perf_counter() - started
    # Übersetzung einmal pro eindeutigem DE-Label, nicht je Paar oder Testfall.
    originals = list(dict.fromkeys(normalize(e['label']) for c in data['cases']
                                   for side in ('reference', 'student') for e in c['de'][side]))
    started = time.perf_counter()
    translations = dict(zip(originals, translator.translate(originals, ['de']*len(originals)), strict=True))
    translation_seconds = time.perf_counter() - started
    thresholds = config['decision_tree']['thresholds']
    tiers = [{'name':'canonical','minimumSimilarity':{'damerau_canonical':1.}},
             {'name':'spelling','minimumSimilarity':{'damerau_canonical':thresholds['spelling']}},
             {'name':'meaning','minimumSimilarity':{'multilingual_expanded':thresholds['meaning']},
              'confirmationFloor':{'multilingual_expanded':thresholds['meaning_floor']}}]
    paths = [('de_odenet','de',german), ('en_wordnet','en',english),
             ('de_translated_wordnet','de',english)]
    taxonomy = settings['taxonomy_guard']
    modes = {'text_only':None, 'lexicon_only':None, 'tree':None,
             'lexicon_only_single_synset':None, 'tree_single_synset':None,
             'tree_path':{'path_similarity':taxonomy['path_similarity']},
             'tree_wup':{'wup_similarity':taxonomy['wup_similarity']},
             'tree_taxonomy':taxonomy}
    records, features, views, coverage, timings = [], [], {}, {}, {}
    # Derselbe DE-Textzweig wird in A und C exakt wiederverwendet.
    text_cache = {}
    for path, form, backend in paths:
        path_cases, label_inputs, lexical_seconds, text_seconds = [], {}, 0., 0.
        for case in data['cases']:
            view = {'id':case['id'], **case[form], 'annotations':case['annotations']}
            path_cases.append(view)
            left, right = view['reference'], view['student']
            shape = (len(left), len(right))
            labels = [[normalize(e['label']) for e in side] for side in (left,right)]
            lookup = [[translations[t] if path=='de_translated_wordnet' else t for t in side] for side in labels]
            label_inputs.update(zip(labels[0]+labels[1], lookup[0]+lookup[1], strict=True))
            started = time.perf_counter()
            shared = backend.matrix(*lookup)
            lexical = {'shared_synset':shared, **backend.relation_features(*lookup, list(RELATION_FEATURES))}
            lexical_seconds += time.perf_counter() - started
            key = (form, case['id'])
            if key not in text_cache:
                started = time.perf_counter()
                scores = {}
                for method in methods:
                    prepared = [side[:] for side in labels]
                    for step in method.preprocessing:
                        prepared = [[registry.PREPROCESSORS[step](t) for t in side] for side in prepared]
                    scores[method.name] = method.compute(states[method.state_key], *prepared)
                candidates = {'methods':[{'name':m.name,'scoreRange':m.score_range} for m in methods],
                    'synonymMatrix':[{'referenceElementId':a['id'],'referenceLabel':a['label'],
                      'matches':[{'submissionElementId':b['id'],'submissionLabel':b['label'],
                                  'scoreStatus':'scored','scores':{k:float(v[i,j]) for k,v in scores.items()}}
                                 for j,b in enumerate(right)]} for i,a in enumerate(left)]}
                evidence = adapter.pair_similarity(candidates, tiers)
                text_cache[key] = scores, evidence
                text_seconds += time.perf_counter() - started
            scores, evidence = text_cache[key]
            features.append({'path':path,'case':case['id'],'lexicon_inputs':lookup,
                             'scores':{k:v.tolist() for k,v in scores.items()},
                             'lexicon_features':{k:v.tolist() for k,v in lexical.items()}})
            for mode,policy in modes.items():
                verdicts, reasons = np.full(shape,'open',dtype=object), np.full(shape,'',dtype=object)
                for i,a in enumerate(left):
                    for j,b in enumerate(right):
                        text = evidence[a['id'],b['id']]
                        if mode=='text_only':
                            verdicts[i,j] = 'confirmed' if text['status']=='supported' else 'open'
                            reasons[i,j] = text['tier'] or text['veto'] or 'insufficient_evidence'
                        else:
                            if mode.startswith('lexicon_only'):text={'status':'below_threshold','tier':None,'veto':None}
                            verdicts[i,j],reasons[i,j] = decide({k:float(v[i,j]) for k,v in lexical.items()},
                                text,taxonomy_policy=policy,require_single_synset=(
                                    True if mode.endswith('_single_synset') else
                                    config['decision_tree'].get('require_single_synset',False)))
                records.append({'variant':path+'_'+mode,'case':case['id'],'eligible':np.ones(shape,dtype=bool).tolist(),
                                'verdicts':verdicts.tolist(),'reasons':reasons.tolist()})
        names = [path+'_'+mode for mode in modes]
        views[path] = _summary(path_cases,records,names)
        inputs = label_inputs
        known = sum(bool(backend.lookup(t)) for t in label_inputs.values())
        coverage[path] = {'labels':len(label_inputs),'known':known,
                          'shared_synset_pairs':sum(int(np.asarray(f['lexicon_features']['shared_synset']).sum())
                              for f in features if f['path']==path), 'inputs':inputs}
        timings[path] = {'lexical_first_pass_seconds':lexical_seconds,'text_compute_seconds':text_seconds,
                         'text_features_reused':path=='de_translated_wordnet'}
        print(path, 'coverage', coverage[path]['known'],'/',coverage[path]['labels'], flush=True)
        for name,m in views[path].items():
            print(name, f'TP={m["tp"]} FP={m["fp"]} FN={m["fn"]} F1={m["f1"]:.4f}',flush=True)
    result = {'seed':config['seed'],'dataset':data,'thresholds':thresholds,
        'taxonomy_guard':taxonomy,'summary':views,
        'coverage':coverage,'records':records,'features':features,'timings':timings,
        'initialization_seconds':loads,'translation_seconds':translation_seconds,'translations':translations,
        'translation_cache':{'hits':cache.hits,'misses':cache.misses},
        'lexicons':{'de':german.version,'en':english.version},
        'embedding':states['multilingual'].resource_metadata(),'translation_revision':translator.revision,
        'source_hashes':{str(p):sha256(p) for p in [source,Path(__file__),Path(__file__).with_name('decision_tree.py'),
            ROOT/'src/synonym_matching/lexicons.py',ROOT/'src/synonym_matching/translation.py',
            ROOT.parent/'synonym-matching/src/synonym_matching/preprocessing.py',
            ROOT.parent/'synonym-matching/src/synonym_matching/methods/registry.py',
            ROOT.parent/'one-to-one-graph-matching/src/text_similarity.py']},
        'policy':'Synthetic matched DE/EN versions, 27 cases/62 pair occurrences, not independent validation. '
                 'No input language attribute or detection: route fixed by experimental group. '
                 'Lexicon lookup on normalized whole labels, no extra stemming or abbreviation expansion. '
                 'A/C share exact German text scores; only lexicon input changes. '
                 'Taxonomy guards only constrain embedding confirmation with single-sense connected pairs; '
                 'high taxonomy alone never confirms; missing taxonomy abstains. Provisional thresholds, no tuning. '
                 'Single-synset synonym requirement disabled by default, strict ablation retained; '
                 'counterrelation and taxonomy conditions unchanged. '
                 'B uses authored English variants. Open is not confirmation. '
                 'Single-synset guard is not WSD. No graph matching or Top-1 from binary verdicts. '
                 'First-pass times share caches and are not isolated cold benchmarks; model initialization separated.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(output,'wt',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,allow_nan=False)
    print('Saved:',output,flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    args=parser.parse_args()
    run(load_config(args.config))


if __name__=='__main__':
    main()
