"""Ausgewählte Synonym-Matching-Pipeline für die produktive Übernahme."""

from .pipeline import MatchingPipeline


def match(reference, student, **options):
    """Bequemer Einzelaufruf; bei mehreren Anfragen MatchingPipeline wiederverwenden."""
    return MatchingPipeline(**options).match(reference, student)


__all__ = ['MatchingPipeline', 'match']
