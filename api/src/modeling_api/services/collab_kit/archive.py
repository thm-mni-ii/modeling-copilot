"""Archivieren in Collab-Kit (CK): was der Copilot ins Archiv gibt und wann.

Die Schalter stehen im Bereich archive der Collab-Einstellungen (web/src/collab/connection/collabSettings.ts),
Standard ist alles aus. CK verschiebt ein archiviertes Werkstück samt Abzweigen, Kommentaren und Aufgaben in
sein Archiv; zurückgeholt kommt es unverändert wieder, auch in die Räume, in denen es zuletzt lag.

Zwei Wege: beim Beenden einer Share sofort (`archive_closed_share`) und stündlich, was nach einer Share ohne
Raum liegen blieb und seit einer Frist niemand benutzt hat (`archive_unused`). Der zweite holt auch nach, was
beim Beenden scheiterte. Zurückholen zählt in CK als Aktivität, die Frist beginnt dann von vorn.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client, collab_settings
from modeling_api.services.collab_kit.errors import SHARING_DISABLED

logger = logging.getLogger(__name__)

# Die Schalter und die Frist stehen im Bereich archive (collab_settings.py); nicht lesbar gilt alles als aus.
AREA = "archive"
SHARE_CLOSED = "share closed"
# So oft sieht der Job nach; die Frist zählt in Tagen, eine Stunde Verzug fällt nicht ins Gewicht.
JOB_SECONDS = 3600

_task: asyncio.Task | None = None


async def enabled() -> bool:
    """Ob das Archiv in den Collab-Einstellungen an ist; nicht lesbar gilt aus."""
    return (await collab_settings.read(AREA))["enabled"]


async def archive_closed_share(workpiece_ids: list[str | None]) -> None:
    """Archiviert Modell und Aufgabe einer beendeten Share, wenn Archiv und archiveOnShareClose an sind.

    Erst aufrufen, wenn die Werkstücke aus dem Raum sind: zurückgeholt kämen sie sonst in den Raum des
    Hosts, den seine nächste Share wieder nutzt. Scheitert es, bleibt das Werkstück wie bisher ohne Raum.
    """
    values = await collab_settings.read(AREA)
    if not (values["enabled"] and values["archiveOnShareClose"]):
        return
    for workpiece_id in filter(None, workpiece_ids):
        try:
            await client.archive_workpiece(workpiece_id, SHARE_CLOSED)
        except ApiError:
            # 409, solange CK es verschiebt, oder CK antwortet nicht: die Share ist trotzdem beendet.
            logger.warning("Workpiece %s could not be archived.", workpiece_id, exc_info=True)


async def archive_unused(now: datetime | None = None) -> int:
    """Archiviert Werkstücke des Copilots ohne Raum, die seit der Frist niemand benutzt hat; gibt zurück, wie viele.

    Laufende Shares und Gruppenarbeit liegen in Räumen, Werkstücke von Personen tragen deren Namen in
    `createdBy`; beides bleibt. Ohne jede Spur am Werkstück zählt sein Anlegen.
    """
    values = await collab_settings.read(AREA)
    # Ohne Archiv gilt die Frist nicht, also nie.
    days = values["archiveUnusedAfterDays"] if values["enabled"] else 0
    if days == 0:
        return 0
    now = now or datetime.now(timezone.utc)
    in_rooms = {workpiece_id for room in await client.list_rooms() for workpiece_id in room.get("workpieces", [])}
    count = 0
    for workpiece in await client.list_workpieces():
        if workpiece["createdBy"] != settings.service_actor or workpiece["_id"] in in_rooms:
            continue
        try:
            traces = [workpiece["createdAt"], *(entry["at"] for entry in await client.workpiece_activity(workpiece["_id"]))]
            if now - max(datetime.fromisoformat(at) for at in traces) < timedelta(days=days):
                continue
            await client.archive_workpiece(workpiece["_id"], f"unused for {days} {'day' if days == 1 else 'days'}")
            count += 1
        except ApiError:
            # Eine andere Instanz war schneller (404), CK verschiebt es (409) oder antwortet nicht: die nächste Runde.
            logger.warning("Workpiece %s could not be archived.", workpiece["_id"], exc_info=True)
    return count


async def _run() -> None:
    global _task
    while True:
        try:
            await archive_unused()
        except ApiError as error:
            if error.code == SHARING_DISABLED:
                _task = None
                return
            logger.warning("Archiving unused workpieces failed.", exc_info=True)
        await asyncio.sleep(JOB_SECONDS)


def ensure_running() -> None:
    """Startet den Job, wenn keiner läuft; einmal beim Start der API."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.get_running_loop().create_task(_run())


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None
