"""Diagnostiziere Lexikoneinträge, ohne daraus Gleichwertigkeit abzuleiten."""

import re
from collections import Counter


def inspect_labels(texts, lookup):
    """Prüfe ganze Labels und einfache Worttokens mit demselben Lexikonzugriff.

    Die Tokensuche trennt an Satzzeichen/Leerraum, zerlegt aber keine Komposita
    oder Identifier. Bekannte Tokens ersetzen keinen fehlenden Mehrworteintrag.
    Einträge können Synsets (WordNet/OdeNet) oder Gruppen (OpenThesaurus) sein.
    """
    cache = {}

    def entries(text):
        if text not in cache:
            cache[text] = lookup(text)
        return cache[text]

    result = []
    for text in texts:
        if not text.strip():
            result.append({'status': 'empty', 'whole_label_known': False,
                           'entry_count': 0, 'token_count': 0, 'known_token_count': 0,
                           'token_coverage': None})
            continue
        whole = entries(text)
        tokens = re.findall(r'\w+', text, flags=re.UNICODE)
        known = sum(bool(entries(token)) for token in tokens)
        status = 'known' if whole else 'partial' if known else 'unknown'
        result.append({'status': status, 'whole_label_known': bool(whole),
                       'entry_count': len(whole), 'token_count': len(tokens),
                       'known_token_count': known,
                       'token_coverage': known / len(tokens) if tokens else None})
    return result


def summarize_coverage(features, cases):
    """Zähle eindeutige Original-/Suchtextpaare je Kette, Fall und Ausgangssprache.

    Wiederholte IDs mit denselben Labels erhöhen die Abdeckung nicht künstlich.
    WordNet-Suchtexte sind bereits übersetzt; das ist keine deutsche Direktabdeckung.
    """
    cases = {case['id']: case for case in cases}
    summaries = []
    for feature in features:
        if 'lexicon_coverage' not in feature:
            continue
        case = cases[feature['case']]
        groups = {}
        for side in ('reference', 'student'):
            for original, text, coverage in zip(
                    case[side], feature['processedLabels'][side],
                    feature['lexicon_coverage'][side], strict=True):
                language = original.get('language')
                groups.setdefault(language, {})[original['label'], text] = coverage
        for language, labels in groups.items():
            counts = Counter(item['status'] for item in labels.values())
            nonempty = len(labels) - counts['empty']
            summaries.append({
                'chain': feature['chain'], 'case': feature['case'],
                'source_language': language, 'unique_labels': len(labels),
                'known': counts['known'], 'partial': counts['partial'],
                'unknown': counts['unknown'], 'empty': counts['empty'],
                'whole_label_coverage': counts['known'] / nonempty if nonempty else None,
                'uncovered_labels': [
                    {'original': original, 'lookup_text': text, 'status': coverage['status']}
                    for (original, text), coverage in labels.items()
                    if coverage['status'] in {'partial', 'unknown'}],
            })
    return summaries
