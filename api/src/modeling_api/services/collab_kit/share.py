"""Teilen eines Modells in einem Collab-Kit-Raum.

Jeder Host hat genau einen Raum mit den Gruppen "hosts" und "visitors"; er wird beim ersten
Teilen angelegt und danach wiederverwendet. Geteilt wird in einem neuen Werkstück darin.
"""

from typing import Any

from modeling_api.core.errors import ApiError, not_found
from modeling_api.services.collab_kit import client, store

# Der Host darf im Raum alles.
HOST_RIGHTS = ["see", "speak", "edit", "plan", "decide", "manage"]


# Was beim Wiederöffnen an die Besucher zurückgeht; mehr stellt das Backend nicht her.
RESTORABLE = ["see", "speak", "edit"]


def visitor_rights(edit: bool, comment: bool) -> list[str]:
    """Besucher sehen immer, sonst wäre die Einladung sinnlos; `speak` ist das Recht zu kommentieren."""
    return ["see", *(["speak"] if comment else []), *(["edit"] if edit else [])]


async def _create_room(host_id: str, name: str) -> dict[str, Any]:
    """Legt Raum und beide Gruppen an. Die Host-Gruppe kommt zuletzt, denn über sie wird der Raum gefunden."""
    room_id = (await client.create_room(name))["_id"]
    visitors = await client.create_group(
        f"Visitors {host_id}", [], store.group_settings(store.VISITORS, room_id)
    )
    hosts = await client.create_group(
        f"Host {host_id}", [host_id], store.group_settings(store.HOSTS, room_id, host_id)
    )
    await client.set_grant(hosts["_id"], HOST_RIGHTS, room_id)
    groups = {store.HOSTS: hosts["_id"], store.VISITORS: visitors["_id"]}
    await store.save(room_id, open=False, workpieceId=None, groups=groups)
    return {"roomId": room_id, "open": False, "workpieceId": None, "groups": groups}


async def join(user_id: str, room_id: str) -> tuple[str, str]:
    """Nimmt den Nutzer als Besucher auf und gibt Werkstück und Rolle zurück ("host" oder "visitor").

    Wer schon drin ist, wird nicht noch einmal eingetragen und kommt auch durch, wenn der Host den
    Link für Neue gesperrt hat. In einem geschlossenen Raum gibt es für niemanden etwas zu öffnen.
    """
    current = await store.read(room_id)
    if not current["open"] or not current["workpieceId"]:
        raise ApiError(403, "SHARE_CLOSED", "The host is not sharing in this room.")
    hosts = await client.get_group(current["groups"][store.HOSTS])
    visitors = await client.get_group(current["groups"][store.VISITORS])
    if user_id in hosts["members"]:
        return current["workpieceId"], "host"
    if user_id in visitors["members"]:
        return current["workpieceId"], "visitor"
    if not current["joinable"]:
        raise ApiError(403, "SHARE_CLOSED", "The host has closed the link for new visitors.")
    await client.add_member(visitors["_id"], user_id)
    return current["workpieceId"], "visitor"


async def share(
    host_id: str,
    name: str,
    contract: dict[str, Any],
    units: list[dict[str, Any]],
    anonymous: bool,
    edit: bool,
    comment: bool,
) -> tuple[str, str, bool]:
    """Teilt in einem neuen Werkstück; Raum und Gruppen des Hosts werden wiederverwendet.

    Gibt Raum, Werkstück und zurück, ob es neu angelegt wurde. Teilt der Host schon, bleibt alles
    wie es ist, auch die Rechte, die er inzwischen im Raum geändert hat.
    """
    try:
        current = await store.find_by_owner(host_id)
    except ApiError as error:
        # Ein halb angelegter Raum (Abbruch beim Anlegen) wird übergangen und bleibt liegen.
        if error.status not in (404, 409):
            raise
        current = None
    current = current or await _create_room(host_id, name)
    room_id = current["roomId"]

    if current["open"] and current["workpieceId"]:
        return room_id, current["workpieceId"], False

    await client.set_grant(
        current["groups"][store.VISITORS], visitor_rights(edit, comment), room_id, anonymous
    )
    workpiece = await client.create_workpiece(
        {"name": name, "roomId": room_id, "contract": contract, "units": units}
    )
    await store.save(room_id, open=True, joinable=True, workpieceId=workpiece["_id"])
    return room_id, workpiece["_id"], True


async def _own_share(host_id: str) -> dict[str, Any]:
    current = await store.find_by_owner(host_id)
    if current is None:
        raise not_found()
    return current


def _restored(before: dict[str, Any]) -> list[str]:
    """Die gemerkten Rechte, bereinigt: `see` immer, sonst nur, was Besucher haben dürfen."""
    rights = before.get("rights")
    return ["see", *[r for r in RESTORABLE[1:] if isinstance(rights, list) and r in rights]]


async def set_open(host_id: str, open_: bool) -> None:
    """Sperrt den Raum oder öffnet ihn wieder (Abbruch beim Verlassen).

    Gesperrt kommt niemand mehr hinein und die Besucher können nicht mehr bearbeiten, damit alle
    denselben Stand sehen, während der Host speichert. Ihre Rechte davor merkt sich der Raum.
    """
    current = await _own_share(host_id)
    room_id, visitors = current["roomId"], current["groups"][store.VISITORS]
    if not open_:
        # Schon gesperrt: das Gemerkte bleibt, sonst stünden die schon gekürzten Rechte darin.
        before = current["before"]
        if before is None:
            granted = next(
                (g for g in await client.list_grants(room_id) if g["groupId"] == visitors), {}
            )
            before = {"rights": granted.get("rights", ["see"]), "anonymous": granted.get("anonymous") is True}
        await store.save(room_id, open=False, before=before)
        frozen = [right for right in _restored(before) if right != "edit"]
        await client.set_grant(visitors, frozen, room_id, before.get("anonymous") is True)
        return
    if not current["workpieceId"]:
        raise ApiError(409, "SHARE_CLOSED", "The host is not sharing in this room.")
    if current["before"] is not None:
        await client.set_grant(
            visitors, _restored(current["before"]), room_id, current["before"].get("anonymous") is True
        )
    await store.save(room_id, open=True, before=None)


async def set_joinable(host_id: str, joinable: bool) -> None:
    """Schließt den Link für Neue oder öffnet ihn wieder; wer schon drin ist, bleibt, Rechte bleiben."""
    current = await _own_share(host_id)
    if not current["workpieceId"]:
        raise ApiError(409, "SHARE_CLOSED", "The host is not sharing in this room.")
    await store.save(current["roomId"], joinable=joinable)


async def close(host_id: str) -> None:
    """Beendet das Teilen: Besucher raus, Werkstück aus dem Raum; Raum und Gruppen bleiben.

    Jeder Schritt lässt sich wiederholen, ein abgebrochener Aufruf wird durch einen neuen fertig.
    """
    current = await _own_share(host_id)
    room_id = current["roomId"]
    visitors = await client.get_group(current["groups"][store.VISITORS])
    # Zuerst zu, damit sich während des Aufräumens niemand mehr einträgt.
    await store.save(room_id, open=False)
    for member in visitors["members"]:
        await client.remove_member(visitors["_id"], member)
    room = await client.get_room(room_id)
    if current["workpieceId"] in room["workpieces"]:
        await client.remove_workpiece_from_room(room_id, current["workpieceId"])
    await store.save(room_id, workpieceId=None, before=None)
