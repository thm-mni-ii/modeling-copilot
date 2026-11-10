"""Looks after the shares so that no one stays behind: visitors who are gone and a host who is gone.

Two ends are kept strictly apart. The orderly one is the host's own (dialog to quit, `share.close`):
the sweep never takes part in it and never touches a share that has ended. The disorderly one is a
host who is simply gone: after the grace period the sweep locks the room (`autoLocked`), after the
end period it takes the visitors out; workpiece and state stay in the room, only the host can reach
them, and when the host is back the sweep opens the room again. It opens only a lock it set itself,
never one of the host, and everything the host does clears the mark.

Collab-Kit tells who is connected only when asked, so a task asks every few seconds while there is
something to look after, and ends itself when there is not: no open share, or only one whose host is
gone and whose visitors are out. The host coming back wakes it again (`GET /v1/share`). Times are kept
in memory only; after a restart or a sleep of the task they start again. Every step can be repeated,
so several instances doing the same sweep do no harm.
"""

import asyncio
import logging
import time

from modeling_api.core.errors import ApiError
from modeling_api.services import models
from modeling_api.services.collab_kit import client, share, store

logger = logging.getLogger(__name__)

# How often the open shares are looked at, and how long a visitor or the host may be gone before the sweep acts.
SWEEP_SECONDS = 30
VISITOR_GRACE_SECONDS = 120
HOST_GRACE_SECONDS = 120
HOST_END_SECONDS = 300

_task: asyncio.Task | None = None
# Set when a share starts while a sweep may already have missed it; the task then looks once more before it ends.
_again = False
# Since when a visitor is missing, as (room, actor) -> time.monotonic().
_missing: dict[tuple[str, str], float] = {}
# Since when the host of a room is missing, as room -> time.monotonic().
_host_missing: dict[str, float] = {}


async def _sweep_host(room: dict, here: set[str], now: float) -> None:
    room_id, host_id = room["roomId"], room["hostId"]
    if host_id in here:
        _host_missing.pop(room_id, None)
        if room["autoLocked"]:
            # Looked at again right before acting: the host may have ended the share meanwhile.
            fresh = await store.read(room_id)
            if fresh["workpieceId"] and fresh["autoLocked"]:
                await share.set_open(host_id, True)
        return
    since = _host_missing.setdefault(room_id, now)
    # Only an open room is locked: one the host has locked themselves stays theirs.
    if room["open"] and now - since >= HOST_GRACE_SECONDS:
        fresh = await store.read(room_id)
        if fresh["workpieceId"] and fresh["open"]:
            await share.set_open(host_id, False, auto=True)


async def _sweep_room(room: dict, now: float) -> bool:
    """Looks after one room; gives back whether it still needs looking after."""
    room_id = room["roomId"]
    here = {entry["actorId"] for entry in await client.room_presence(room_id)}
    await _sweep_host(room, here, now)
    gone_since = _host_missing.get(room_id)
    # The host stayed away so long that the visitors are taken out; the share itself stays for the host.
    ended = gone_since is not None and now - gone_since >= HOST_END_SECONDS
    visitors = await client.get_group(room["groups"][store.VISITORS])
    members = set(visitors["members"])
    remaining = set(members)
    for actor in members:
        key = (room_id, actor)
        if ended or (actor not in here and now - _missing.setdefault(key, now) >= VISITOR_GRACE_SECONDS):
            await client.remove_member(visitors["_id"], actor)
            # Wer hinausgenommen wird, braucht seine Arbeitskopie nicht mehr, etwa nach einem geschlossenen Tab.
            await models.delete_room_models(room_id, actor)
            _missing.pop(key, None)
            remaining.discard(actor)
        elif actor in here:
            _missing.pop(key, None)
    # Whoever is no visitor any more needs no time.
    for key in [key for key in _missing if key[0] == room_id and key[1] not in remaining]:
        del _missing[key]
    # A share whose host is gone and whose visitors are out has nothing left to look after until the host is back.
    return not (ended and not remaining)


async def sweep_once(now: float | None = None) -> int:
    """Looks at every open share once and gives back how many still need looking after."""
    now = time.monotonic() if now is None else now
    active = 0
    for room in await store.open_rooms():
        try:
            active += await _sweep_room(room, now)
        except ApiError:
            # Collab-Kit not answering says nothing about who is there: nobody is taken out, and the times start over.
            for key in [key for key in _missing if key[0] == room["roomId"]]:
                del _missing[key]
            _host_missing.pop(room["roomId"], None)
            logger.warning("Sweep of room %s failed.", room["roomId"], exc_info=True)
            active += 1
    return active


async def _run() -> None:
    global _task, _again
    while True:
        _again = False
        try:
            count = await sweep_once()
        except ApiError as error:
            if error.code == "SHARING_DISABLED":
                _task = None
                return
            logger.warning("Sweep failed.", exc_info=True)
            count = 1
        if count == 0 and not _again:
            # No await between this check and the end, so a share starting later starts a new task.
            # The times go too: a host who wakes the task again must not be met with old ones.
            _missing.clear()
            _host_missing.clear()
            _task = None
            return
        await asyncio.sleep(SWEEP_SECONDS)


def ensure_running() -> None:
    """Starts the task if none runs; called when a share starts or opens again, when the host is back, and once when the API starts."""
    global _task, _again
    _again = True
    if _task is None or _task.done():
        _task = asyncio.get_running_loop().create_task(_run())


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None
