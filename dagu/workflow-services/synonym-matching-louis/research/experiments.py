"""Baukasten-Konfiguration: aus experiments.json werden die auszuführenden Versuche.

Preprocessing, Verfahren, Ketten und Mischungen sind Daten in der JSON-Datei. Dieses
Modul baut daraus die Versuche und prüft, ob ein Verfahren für einen Fall passt.
Es rechnet nichts; die Berechnung steht in compare.py.
"""

import json
from pathlib import Path

from synonym_matching.combinations import REQUIRES
from synonym_matching.lexicons import RELATION_FEATURES
from synonym_matching.preprocessing import STEPS as PREPROCESSING_STEPS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path(__file__).with_name('experiments.json')


def is_wordvec(method):
    """Wortvektor-Verfahren sind in der Konfiguration durch ihre Dateien erkennbar."""
    return 'files' in method


def load_config(path=DEFAULT_CONFIG):
    """Lese und prüfe die Experimentkonfiguration."""
    config = json.loads(Path(path).read_text())
    # Eine Variante übernimmt alle Eigenschaften ihres Basisverfahrens (z. B. dieselben
    # Modelldateien) und überschreibt nur das Genannte.
    for name, method in config['methods'].items():
        if 'based_on' in method:
            base = config['methods'][method['based_on']]
            config['methods'][name] = {**base, **{k: v for k, v in method.items() if k != 'based_on'}}
        steps = config['methods'][name].get('preprocessing_steps')
        if steps is not None and (not isinstance(steps, list)
                                  or any(step not in PREPROCESSING_STEPS for step in steps)):
            raise ValueError(f'{name}: unknown preprocessing_steps')
        relations = config['methods'][name].get('relation_features')
        if relations is not None:
            if (name not in {'wordnet', 'odenet'} or not isinstance(relations, list)
                    or any(not isinstance(r, str) or r not in RELATION_FEATURES for r in relations)
                    or len(relations) != len(set(relations))):
                raise ValueError(f'{name}: invalid relation_features')
        if 'relation_depth' in config['methods'][name]:
            raise ValueError(f'{name}: relation_depth removed; wn.closure follows all hypernyms')
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
        """Variiere nur erlaubte Schritte der Verfahren mit '$pre'.

        Feste Ketten, etwa Embeddings mit normalize, bleiben dabei unverändert.
        Bei Mischungen muss das Profil für alle variierenden Teile passen.
        """
        if any('$pre' in chain for chain in chains):
            allowed = [set(methods[chain[-1]].get('preprocessing_steps', PREPROCESSING_STEPS))
                       for chain in chains if '$pre' in chain]
            return {name: steps for name, steps in config['preprocessing'].items()
                    if all(set(steps) <= permitted for permitted in allowed)}
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
