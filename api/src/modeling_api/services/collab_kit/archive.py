"""Archiving in Collab-Kit (CK): what the Copilot puts into the archive, and when.

The switches live in the archive area of the collab settings (web/src/collab/connection/collabSettings.ts);
by default everything is off. CK moves an archived workpiece with its branches, comments and tasks into
its archive; restored, it comes back unchanged, including into the rooms it was last in.

Two paths: right when a share ends (`archive_closed_share`), and nightly for whatever was left without a
room after a share and has not been used by anyone for a period (`archive_unused`). The second also catches up
on what failed when a share ended. Restoring counts as activity in CK, so the period starts over.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client, collab_settings
from modeling_api.services.collab_kit.errors import SHARING_DISABLED

logger = logging.getLogger(__name__)

# The switches and the period live in the archive area (collab_settings.py); if unreadable, everything counts as off.
AREA = "archive"
SHARE_CLOSED = "share closed"
# The job runs once a day at this hour (UTC), at night when nobody works; the period is counted in whole days.
JOB_HOUR = 3

_task: asyncio.Task | None = None


async def enabled() -> bool:
    """Whether the archive is on in the collab settings; unreadable counts as off."""
    return (await collab_settings.read(AREA))["enabled"]


async def archive_closed_share(workpiece_ids: list[str | None]) -> None:
    """Archives model and task of an ended share if the archive and archiveOnShareClose are on.

    Call only once the workpieces are out of the room: otherwise, when restored, they would land in the room
    of the host, which their next share reuses. If it fails, the workpiece stays without a room as before.
    """
    values = await collab_settings.read(AREA)
    if not (values["enabled"] and values["archiveOnShareClose"]):
        return
    for workpiece_id in filter(None, workpiece_ids):
        try:
            await client.archive_workpiece(workpiece_id, SHARE_CLOSED)
        except ApiError:
            # 409 while CK is moving it, or CK does not answer: the share has ended anyway.
            logger.warning("Workpiece %s could not be archived.", workpiece_id, exc_info=True)


async def archive_unused(now: datetime | None = None) -> int:
    """Archives Copilot workpieces without a room that nobody has used within the period; returns how many.

    Running shares and group work live in rooms, and workpieces of people carry their ID in
    `createdBy`; both stay. Without any trace on the workpiece, its creation counts.
    """
    values = await collab_settings.read(AREA)
    # Without the archive the period does not apply, so never.
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
            # Another instance was faster (404), CK is moving it (409) or does not answer: next round.
            logger.warning("Workpiece %s could not be archived.", workpiece["_id"], exc_info=True)
    return count


def seconds_until_next_run(now: datetime | None = None) -> float:
    """Seconds until the next JOB_HOUR; if the hour has passed today, tomorrow's."""
    now = now or datetime.now(timezone.utc)
    next_run = now.replace(hour=JOB_HOUR, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()


async def _run() -> None:
    global _task
    while True:
        try:
            # Read before sleeping, so that a server without sharing ends the job right away.
            await collab_settings.read(AREA)
            await asyncio.sleep(seconds_until_next_run())
            await archive_unused()
        except ApiError as error:
            if error.code == SHARING_DISABLED:
                _task = None
                return
            logger.warning("Archiving unused workpieces failed.", exc_info=True)


def ensure_running() -> None:
    """Starts the job if none is running; called once when the API starts."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.get_running_loop().create_task(_run())


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None
