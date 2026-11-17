"""Die Collab-Einstellungen, die das Backend liest, mit ihren Grenzen.

Jeder Bereich ist ein Dokument in Collab-Kit (CK); CK kennt weder Bereiche noch Schlüssel, die Grenzen
prüft nur der Copilot. Standard, kleinster und größter Wert sind dieselben wie in
web/src/collab/connection/collabSettings.ts (COLLAB_LIMITS); hier stehen nur die Bereiche des Backends.
"""

import logging
from typing import Any

from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client
from modeling_api.services.collab_kit.errors import SHARING_DISABLED

logger = logging.getLogger(__name__)

LIMITS: dict[str, dict[str, dict[str, Any]]] = {
    # Die Wartezeiten des Sweeps (sweep.py).
    "sharing": {
        "sweepSeconds": {"default": 30, "min": 10, "max": 120},
        "visitorGraceSeconds": {"default": 120, "min": 30, "max": 3600},
        "hostGraceSeconds": {"default": 120, "min": 30, "max": 3600},
        "hostEndSeconds": {"default": 300, "min": 30, "max": 7200},
    },
    # Die Schalter und die Frist des Archivs (archive.py); 0 Tage heißt nie.
    "archive": {
        "enabled": {"default": False},
        "archiveOnShareClose": {"default": False},
        "archiveUnusedAfterDays": {"default": 0, "min": 0, "max": 365},
    },
}


def defaults(area: str) -> dict[str, Any]:
    """Die Standardwerte eines Bereichs."""
    return {key: limit["default"] for key, limit in LIMITS[area].items()}


def _fits(limit: dict[str, Any], value: Any) -> bool:
    """Ob ein Wert passt: eine ganze Zahl in den Grenzen oder ein Wahrheitswert."""
    # type() statt isinstance(), denn auch True und False wären sonst Zahlen.
    if "min" in limit:
        return type(value) is int and limit["min"] <= value <= limit["max"]
    return type(value) is bool


async def read(area: str) -> dict[str, Any]:
    """Die geltenden Werte eines Bereichs; fehlt einer, passt er nicht oder ist der Bereich nicht lesbar, gilt sein Standard.

    Ohne Teilen auf diesem Server (`SHARING_DISABLED`) geht der Fehler weiter, daran enden die Jobs.
    """
    try:
        values = await client.get_settings(area)
    except ApiError as error:
        if error.code == SHARING_DISABLED:
            raise
        logger.warning("Collab settings %s could not be read; the defaults apply.", area, exc_info=True)
        values = {}
    return {
        key: value if _fits(limit, value := values.get(key)) else limit["default"]
        for key, limit in LIMITS[area].items()
    }
