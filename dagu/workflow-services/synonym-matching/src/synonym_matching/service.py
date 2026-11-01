"""Einfacher Serviceaufruf ohne Experimentauswertung oder Dateiausgabe."""

from .engine import MatchingEngine, format_synonym_matrix


def match(reference, student, config=None, *, threshold=None):
    """Vergleiche zwei Labelmengen mit den konfigurierten Verfahren.

    Ohne Konfiguration gelten die bisherigen String-Baselines. Über ``methods``
    und ``combiner`` können andere Verfahren gewählt werden. IDs und Originaltexte
    bleiben erhalten; nur die ausgegebenen Scores werden auf vier Stellen gerundet.
    """
    result = MatchingEngine(config).match(reference, student, threshold=threshold)
    return {'synonymMatrix': format_synonym_matrix(result['synonymMatrix'])}
