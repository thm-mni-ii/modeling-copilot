"""Paarweises Label-Matching, unabhängig von Dagu und HTTP."""

from .engine import MatchingEngine
from .service import match

__all__ = ["MatchingEngine", "match"]
