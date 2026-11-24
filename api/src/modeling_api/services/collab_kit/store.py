"""The share of a host, kept in the settings of Collab-Kit (no database of its own).

The host can change the settings of the room (they have `manage` there), but not those of the
groups. So the room counts only as a hint: the groups it names must vouch for themselves as
groups of this room. Otherwise a host could enter the ID of a foreign group.

Room:   {"share": {"open": true, "joinable": true, "workpieceId": "…", "taskWorkpieceId": "…" | null,
                   "groups": {"hosts": "…", "visitors": "…"},
                   "before": {"rights": […], "anonymous": false} (only while locked),
                   "autoLocked": true (only while the sweep keeps it locked for a missing host)}}
Group:  {"share": {"role": "hosts" | "visitors", "roomId": "…", "ownerId": "…" (hosts only)}}
"""

import asyncio
from typing import Any

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError, not_found
from modeling_api.services.collab_kit import client
from modeling_api.services.collab_kit.errors import share_invalid

KEY = "share"
HOSTS = "hosts"
VISITORS = "visitors"


def group_settings(role: str, room_id: str, owner_id: str | None = None) -> dict[str, Any]:
    """The settings of a new group: the proof of which room and role it belongs to."""
    share: dict[str, Any] = {"role": role, "roomId": room_id}
    if owner_id is not None:
        share["ownerId"] = owner_id
    return {KEY: share}


def _share_of(settings_: Any) -> dict[str, Any]:
    share = settings_.get(KEY) if isinstance(settings_, dict) else None
    return share if isinstance(share, dict) else {}


async def _host_shares(owner_id: str | None = None) -> list[dict[str, Any]]:
    """The readable shares of the host groups, oldest first; with `owner_id` only those of this host.

    A room that is missing (404) or does not match its groups (409) is skipped, such as a
    half-created or an archived one.
    """
    every = await client.list_groups()
    # read() checks the groups of each room against this list instead of asking CK for each of them.
    known = {group["_id"]: group for group in every}
    groups = sorted(
        (
            group
            for group in every
            if _share_of(group["settings"]).get("role") == HOSTS
            and (owner_id is None or _share_of(group["settings"]).get("ownerId") == owner_id)
        ),
        key=lambda group: group["createdAt"],
    )
    shares = []
    for group in groups:
        try:
            shares.append(await read(_share_of(group["settings"])["roomId"], known))
        except ApiError as error:
            if error.status not in (404, 409):
                raise
    return shares


async def find_by_owner(owner_id: str) -> dict[str, Any] | None:
    """The share of this host or None.

    Several host groups come from a double click or, when someone archived or deleted the room in CK,
    from a new room on the next share. A group whose room is missing or does not match
    is skipped; the room with a running share wins, otherwise the oldest. That way a running
    share stays the host's, even when an older room comes back from the archive.
    """
    found = await _host_shares(owner_id)
    return next((current for current in found if current["workpieceId"]), found[0] if found else None)


async def open_rooms() -> list[dict[str, Any]]:
    """The shares that have a workpiece right now, locked ones included; a room that cannot be read is skipped."""
    return [current for current in await _host_shares() if current["workpieceId"]]


async def read(room_id: str, known: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The share of a room with verified groups; a room without a share is a 404.

    `known` are groups already loaded by ID; a group missing there is asked from CK, both at once.
    """
    room = await client.get_room(room_id)
    share = _share_of(room["settings"])
    # Only the service creates rooms; anything else has no share.
    if not share or room["createdBy"] != settings.service_actor:
        raise not_found()
    groups = share.get("groups") if isinstance(share.get("groups"), dict) else {}
    if not {HOSTS, VISITORS} <= groups.keys():
        raise share_invalid()
    async def group_of(group_id: str) -> dict[str, Any]:
        return known[group_id] if known and group_id in known else await client.get_group(group_id)

    found = await asyncio.gather(*(group_of(group_id) for group_id in groups.values()))
    host_id = None
    for role, group in zip(groups, found):
        belongs = _share_of(group["settings"])
        if belongs.get("role") != role or belongs.get("roomId") != room_id:
            raise share_invalid()
        if role == HOSTS:
            host_id = belongs.get("ownerId")
    return {
        "roomId": room_id,
        "open": share.get("open") is True,
        # Whether the link works for new visitors; yes if unset, so existing rooms stay joinable.
        "joinable": share.get("joinable") is not False,
        "workpieceId": share.get("workpieceId"),
        # The workpiece of the shared task, if one came along.
        "taskWorkpieceId": share.get("taskWorkpieceId"),
        "groups": groups,
        # Who owns the room; visitors do not know the host otherwise, and they cannot read the group.
        "hostId": host_id,
        # The rights of the visitors before the lock, as long as the room is locked.
        "before": share.get("before") if isinstance(share.get("before"), dict) else None,
        # Whether the sweep locked the room because the host was gone, and so may open it again when they are back.
        "autoLocked": share.get("autoLocked") is True,
    }


async def save(room_id: str, **fields: Any) -> None:
    """Sets `open`, `joinable`, `workpieceId`, `taskWorkpieceId`, `groups`, `before` or `autoLocked` and leaves all other settings of the room alone."""
    room = await client.get_room(room_id)
    current = room["settings"] if isinstance(room["settings"], dict) else {}
    await client.update_room_settings(
        room_id, {**current, KEY: {**_share_of(current), **fields}}
    )
