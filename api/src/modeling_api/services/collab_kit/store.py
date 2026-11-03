"""Der Share eines Hosts, abgelegt in den settings von Collab-Kit (keine eigene DB).

Die settings des Raums kann der Host ändern (er hat dort `manage`), die der Gruppen nicht.
Deshalb gilt der Raum nur als Hinweis: Die Gruppen, die er nennt, müssen sich selbst als
Gruppen dieses Raums ausweisen. Sonst könnte ein Host die ID einer fremden Gruppe eintragen.

Raum:   {"share": {"open": true, "joinable": true, "workpieceId": "…",
                   "groups": {"hosts": "…", "visitors": "…"},
                   "before": {"rights": […], "anonymous": false} (nur während der Sperre)}}
Gruppe: {"share": {"role": "hosts" | "visitors", "roomId": "…", "ownerId": "…" (nur hosts)}}
"""

from typing import Any

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError, not_found
from modeling_api.services.collab_kit import client

KEY = "share"
HOSTS = "hosts"
VISITORS = "visitors"


def group_settings(role: str, room_id: str, owner_id: str | None = None) -> dict[str, Any]:
    """Die settings einer neuen Gruppe: der Beleg, zu welchem Raum und in welcher Rolle sie gehört."""
    share: dict[str, Any] = {"role": role, "roomId": room_id}
    if owner_id is not None:
        share["ownerId"] = owner_id
    return {KEY: share}


def _share_of(settings_: Any) -> dict[str, Any]:
    share = settings_.get(KEY) if isinstance(settings_, dict) else None
    return share if isinstance(share, dict) else {}


async def find_by_owner(owner_id: str) -> dict[str, Any] | None:
    """Der Share dieses Hosts oder None; bei mehreren (Doppelklick) gewinnt der ältere."""
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
    """Der Share eines Raums mit geprüften Gruppen; ein Raum ohne Share ist 404."""
    room = await client.get_room(room_id)
    share = _share_of(room["settings"])
    # Räume legt nur der Dienst an; was anderes hat keinen Share.
    if not share or room["createdBy"] != settings.service_actor:
        raise not_found()
    groups = share.get("groups") if isinstance(share.get("groups"), dict) else {}
    if not {HOSTS, VISITORS} <= groups.keys():
        raise ApiError(409, "SHARE_INVALID", "The share of this room is inconsistent.")
    for role, group_id in groups.items():
        belongs = _share_of((await client.get_group(group_id))["settings"])
        if belongs.get("role") != role or belongs.get("roomId") != room_id:
            raise ApiError(409, "SHARE_INVALID", "The share of this room is inconsistent.")
    return {
        "roomId": room_id,
        "open": share.get("open") is True,
        # Ob der Link für Neue gilt; ohne Angabe ja, so bleiben bestehende Räume beitrittsfähig.
        "joinable": share.get("joinable") is not False,
        "workpieceId": share.get("workpieceId"),
        "groups": groups,
        # Die Rechte der Besucher vor der Sperre, solange der Raum gesperrt ist.
        "before": share.get("before") if isinstance(share.get("before"), dict) else None,
    }


async def save(room_id: str, **fields: Any) -> None:
    """Setzt `open`, `joinable`, `workpieceId`, `groups` oder `before` und lässt alle anderen settings des Raums stehen."""
    room = await client.get_room(room_id)
    current = room["settings"] if isinstance(room["settings"], dict) else {}
    await client.update_room_settings(
        room_id, {**current, KEY: {**_share_of(current), **fields}}
    )
