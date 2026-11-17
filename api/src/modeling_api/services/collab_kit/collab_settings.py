"""The collab settings the backend reads, with their limits.

Each area is one document in Collab-Kit (CK); CK knows neither areas nor keys, only the Copilot checks
the limits. Default, smallest and largest value are the same as in
web/src/collab/connection/collabSettings.ts (COLLAB_LIMITS); only the areas of the backend are listed here.
"""

import logging
from typing import Any

from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client
from modeling_api.services.collab_kit.errors import SHARING_DISABLED

logger = logging.getLogger(__name__)

LIMITS: dict[str, dict[str, dict[str, Any]]] = {
    # The waiting times of the sweep (sweep.py).
    "sharing": {
        "sweepSeconds": {"default": 30, "min": 10, "max": 120},
        "visitorGraceSeconds": {"default": 120, "min": 30, "max": 3600},
        "hostGraceSeconds": {"default": 120, "min": 30, "max": 3600},
        "hostEndSeconds": {"default": 300, "min": 30, "max": 7200},
    },
    # The switches and the period of the archive (archive.py); 0 days means never.
    "archive": {
        "enabled": {"default": False},
        "archiveOnShareClose": {"default": False},
        "archiveUnusedAfterDays": {"default": 0, "min": 0, "max": 365},
    },
}


def defaults(area: str) -> dict[str, Any]:
    """The default values of an area."""
    return {key: limit["default"] for key, limit in LIMITS[area].items()}


def _fits(limit: dict[str, Any], value: Any) -> bool:
    """Whether a value fits: an integer within the limits, or a boolean."""
    # type() instead of isinstance(), since True and False would otherwise count as numbers too.
    if "min" in limit:
        return type(value) is int and limit["min"] <= value <= limit["max"]
    return type(value) is bool


async def read(area: str) -> dict[str, Any]:
    """The current values of an area; a missing or invalid value, or an unreadable area, falls back to the default.

    Without sharing on this server (`SHARING_DISABLED`) the error is passed on; the jobs end on it.
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
