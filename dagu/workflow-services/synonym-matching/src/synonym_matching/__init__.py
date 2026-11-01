"""Pairwise label matching, independent of Dagu and HTTP."""

from .engine import MatchingEngine
from .service import match

__all__ = ["MatchingEngine", "match"]
