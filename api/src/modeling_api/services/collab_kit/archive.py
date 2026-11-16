"""Archivieren in Collab-Kit (CK): was der Copilot ins Archiv gibt und wann.

Die Schalter stehen im Bereich archive der Collab-Einstellungen (web/src/collab/connection/collabSettings.ts),
Standard ist alles aus. CK verschiebt ein archiviertes Werkstück samt Abzweigen, Kommentaren und Aufgaben in
sein Archiv; zurückgeholt kommt es unverändert wieder, auch in die Räume, in denen es zuletzt lag.
"""

import logging

from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client

logger = logging.getLogger(__name__)

AREA = "archive"
SHARE_CLOSED = "share closed"


async def _settings() -> dict:
    """Die Werte des Bereichs archive; sind sie nicht lesbar, gilt alles als aus."""
    try:
        return await client.get_settings(AREA)
    except ApiError:
        logger.warning("Archive settings could not be read; nothing is archived.", exc_info=True)
        return {}


async def archive_closed_share(workpiece_ids: list[str | None]) -> None:
    """Archiviert Modell und Aufgabe einer beendeten Share, wenn Archiv und archiveOnShareClose an sind.

    Erst aufrufen, wenn die Werkstücke aus dem Raum sind: zurückgeholt kämen sie sonst in den Raum des
    Hosts, den seine nächste Share wieder nutzt. Scheitert es, bleibt das Werkstück wie bisher ohne Raum.
    """
    values = await _settings()
    if values.get("enabled") is not True or values.get("archiveOnShareClose") is not True:
        return
    for workpiece_id in filter(None, workpiece_ids):
        try:
            await client.archive_workpiece(workpiece_id, SHARE_CLOSED)
        except ApiError:
            # 409, solange CK es verschiebt, oder CK antwortet nicht: die Share ist trotzdem beendet.
            logger.warning("Workpiece %s could not be archived.", workpiece_id, exc_info=True)
