"""Lesbare Pipelinebeschreibungen für die Forschungsausgabe."""

from synonym_matching.variants import STRINGS, TOKENS

METHOD_NAMES = {
    'levenshtein': 'Levenshtein',
    'damerau_levenshtein': 'Damerau-Levenshtein',
    'jaro_winkler': 'Jaro-Winkler',
    'char_bigram': 'Zeichen-Bigramme',
    'char_trigram': 'Zeichen-Trigramme',
    'token_jaccard': 'Token-Jaccard',
    'token_sort_ratio': 'Token-Sort-Ratio',
    'word_order': 'Wortreihenfolge (Token-LCS)',
    'exact_match': 'Exakter Textvergleich',
    'multilingual': 'Multilinguales Embedding',
    'translated_embedding': 'DE→EN-Übersetzung → monolinguales Embedding',
    'wordnet': 'DE→EN-Übersetzung → WordNet',
    'openthesaurus': 'OpenThesaurus',
}


def mean(names):
    return 'Mittel(' + ' + '.join(names) + ')'


def describe_pipeline(spec):
    """Zeige Schritte in Ausführungsreihenfolge und die tatsächliche Kombination."""
    strings = mean([METHOD_NAMES[name] for name in STRINGS])
    tokens = mean([METHOD_NAMES[name] for name in TOKENS])
    multi = METHOD_NAMES['multilingual']
    translated = METHOD_NAMES['translated_embedding']
    hybrid = f'50% {strings} + 50% {multi}'
    expressions = {
        **METHOD_NAMES,
        'translated_string': f'DE→EN-Übersetzung → {strings}',
        'string_ensemble': strings,
        'token_ensemble': tokens,
        'character_token_ensemble': f'50% {strings} + 50% {tokens}',
        'embedding_ensemble': mean([translated, multi]),
        'string_multilingual': hybrid,
        'string_translation_embedding': f'50% {strings} + 50% {translated}',
        'string_both_embeddings': mean([strings, translated, multi]),
        'maximum_fusion': f'Maximum({strings}; {multi})',
        'geometric_fusion': f'Geometrisches Mittel({strings}; {multi})',
        'exact_match_fusion': f'Exakt-Regel (bei Textgleichheit 1, sonst {hybrid})',
        'context_aware': f'Kandidatenkonkurrenz-Korrektur({hybrid}; penalty=0.5)',
    }
    name = spec.get('function', spec.get('name', ''))
    requires = spec.get('requires', [])
    if name == 'weighted_fusion':
        weight = spec.get('options', {}).get('embedding_weight', .5)
        expression = f'{(1 - weight) * 100:g}% {strings} + {weight * 100:g}% {multi}'
    elif spec.get('kind') == 'lexicon_string':
        expression = f'50% {METHOD_NAMES[requires[0]]} + 50% {strings}'
    elif spec.get('kind') == 'mean':
        expression = mean([METHOD_NAMES.get(method, method) for method in requires])
    else:
        expression = expressions.get(name, name or 'Unbekanntes Verfahren')
    steps = spec.get('preprocessing', [])
    preprocessing = '_'.join(steps) if steps else 'ohne_Preprocessing'
    description = f'{preprocessing} - {expression}'
    # Die Ablation verändert Stringverfahren, nicht die separaten Sprachpfade.
    semantic = {'multilingual', 'translated_embedding', 'translated_string', 'wordnet', 'openthesaurus'}
    if set(requires) & semantic and set(requires) & (set(STRINGS) | set(TOKENS)):
        description += ' [Preprocessing vorne: Stringpfad; Sprach-/Lexikonpfade: normalize]'
    if name == 'exact_match_fusion':
        description += ' [Exakt-Prüfung: normalize auf Originaltext]'
    return description
