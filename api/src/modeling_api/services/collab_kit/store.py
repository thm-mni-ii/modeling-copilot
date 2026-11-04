"""The share of a host, kept in the settings of Collab-Kit (no database of its own).

The host can change the settings of the room (they have `manage` there), but not those of the
groups. So the room counts only as a hint: the groups it names must vouch for themselves as
groups of this room. Otherwise a host could enter the ID of a foreign group.

Raum:   {"share": {"open": true, "joinable": true, "workpieceId": "…", "taskWorkpieceId": "…" | null,
                   "groups": {"hosts": "…", "visitors": "…"},
                   "before": {"rights": […], "anonymous": false} (only while locked)}}
Gruppe: {"share": {"role": "hosts" | "visitors", "roomId": "…", "ownerId": "…" (hosts only)}}
"""

from typing import Any

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError, not_found
from modeling_api.services.collab_kit import client

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


async def find_by_owner(owner_id: str) -> dict[str, Any] | None:
    """The share of this host or None; with several (double click) the older one wins."""
    owned = [
        group
        for group in await client.list_groups()
        if _share_of(group["settings"]).get("role") == HOSTS
        and _share_of(group["settings"]).get("ownerId") == owner_id
    ]
    if not owned:
        return None
    oldest = min(owned, key=lambda group: group["createdAt"])
    return await read(_share_of(oldest["settings"])["roomId"])


async def read(room_id: str) -> dict[str, Any]:
    """The share of a room with verified groups; a room without a share is a 404."""
    room = await client.get_room(room_id)
    share = _share_of(room["settings"])
    # Only the service creates rooms; anything else has no share.
    if not share or room["createdBy"] != settings.service_actor:
        raise not_found()
    groups = share.get("groups") if isinstance(share.get("groups"), dict) else {}
    if not {HOSTS, VISITORS} <= groups.keys():
        raise ApiError(409, "SHARE_INVALID", "The share of this room is inconsistent.")
    host_id = None
    for role, group_id in groups.items():
        belongs = _share_of((await client.get_group(group_id))["settings"])
        if belongs.get("role") != role or belongs.get("roomId") != room_id:
            raise ApiError(409, "SHARE_INVALID", "The share of this room is inconsistent.")
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
    }


async def save(room_id: str, **fields: Any) -> None:
    """Sets `open`, `joinable`, `workpieceId`, `taskWorkpieceId`, `groups` or `before` and leaves all other settings of the room alone."""
    room = await client.get_room(room_id)
    current = room["settings"] if isinstance(room["settings"], dict) else {}
    await client.update_room_settings(
        room_id, {**current, KEY: {**_share_of(current), **fields}}
    )
