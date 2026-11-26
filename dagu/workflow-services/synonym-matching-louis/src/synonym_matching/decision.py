"""Feste, begründete Entscheidungen. Kein kombinierter Wahrscheinlichkeitsscore."""

from .preprocessing import normalize, text_veto


def decide(features, reference, student, *, spelling_threshold=.85,
           meaning_threshold=.85, exact_first=False):
    """Gemeinsame Bedeutung → Gegenrelation → String → Embedding → offen.

    Die Regeln bestätigen mögliche Labelgleichwertigkeit, keine Graphkorrektheit.
    Die optionale Gleichheitspriorität ist eine separate Forschungsablation.
    """
    if not reference.strip() or not student.strip():
        return 'not_evaluable', 'empty_or_ineligible'
    if exact_first and normalize(reference).lower() == normalize(student).lower():
        return 'confirmed', 'normalized_exact'
    known = features['pair_known'] == 1
    single = known and features['reference_synset_count'] == features['student_synset_count'] == 1
    shared = features['shared_synset'] == 1
    counter = any(features[k] == 1 for k in ('antonym', 'reference_hypernym', 'reference_hyponym'))
    if known and shared:
        return 'confirmed', 'shared_synset_over_counterrelation' if counter else 'shared_synset'
    if known and counter:
        return ('rejected', 'single_sense_counterrelation') if single else ('open', 'ambiguous_or_conflicting_relation')
    veto = text_veto(reference, student)
    if veto == 'digit_mismatch':
        return 'rejected', 'digit_mismatch'
    if veto != 'start_mismatch':
        if features['damerau_canonical'] == 1:
            return 'confirmed', 'canonical'
        if features['damerau_canonical'] >= spelling_threshold:
            return 'confirmed', 'spelling'
    if features['embedding_similarity'] >= meaning_threshold:
        return 'confirmed', 'meaning'
    return 'open', 'insufficient_evidence'
