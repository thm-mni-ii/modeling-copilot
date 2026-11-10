"""Sharing a model in a Collab-Kit room.

Each host has exactly one room with the groups "hosts" and "visitors"; it is created on the
first share and reused afterwards. Sharing happens in a new workpiece inside it.
"""

from typing import Any

from modeling_api.core.errors import ApiError, not_found
from modeling_api.services import models
from modeling_api.services.collab_kit import client, store

# The host may do everything in the room.
HOST_RIGHTS = ["see", "speak", "edit", "plan", "decide", "manage"]


# The workpiece of the shared task and the map of its marks, as the web reads them.
TASK_FORMAT = "copilot-task"
MARKS_MAP = "marks"

# What goes back to the visitors on reopening; the backend restores nothing more.
RESTORABLE = ["see", "speak", "edit"]


def visitor_rights(edit: bool, comment: bool) -> list[str]:
    """Visitors always see, otherwise the invitation would be pointless; `speak` is the right to comment."""
    return ["see", *(["speak"] if comment else []), *(["edit"] if edit else [])]


async def _create_room(host_id: str, name: str) -> dict[str, Any]:
    """Creates the room and both groups. The host group comes last, because the room is found through it."""
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


async def join(user_id: str, room_id: str) -> tuple[str, str, str]:
    """Adds the user as a visitor and returns the workpiece, the role ("host" or "visitor") and the ID of the host.

    Whoever is already in is not added again and still gets through when the host has closed the
    link for new visitors. In a closed room there is nothing to open for anyone.
    """
    current = await store.read(room_id)
    if not current["open"] or not current["workpieceId"]:
        raise ApiError(403, "SHARE_CLOSED", "The host is not sharing in this room.")
    hosts = await client.get_group(current["groups"][store.HOSTS])
    visitors = await client.get_group(current["groups"][store.VISITORS])
    if user_id in hosts["members"]:
        return current["workpieceId"], "host", current["hostId"]
    if user_id in visitors["members"]:
        return current["workpieceId"], "visitor", current["hostId"]
    if not current["joinable"]:
        raise ApiError(403, "SHARE_CLOSED", "The host has closed the link for new visitors.")
    await client.add_member(visitors["_id"], user_id)
    return current["workpieceId"], "visitor", current["hostId"]


async def leave(user_id: str, room_id: str) -> None:
    """Takes the user out of the visitors of the room; a visitor can always go, whatever the host does.

    A room that is closed, gone or never shared is nothing to leave, and whoever is no visitor
    (the host included) is not touched, so the call can be repeated.
    """
    try:
        current = await store.read(room_id)
    except ApiError as error:
        if error.status != 404:
            raise
        # Ohne Raum ist die Arbeitskopie erst recht verwaist.
        await models.delete_room_models(room_id, user_id)
        return
    visitors = await client.get_group(current["groups"][store.VISITORS])
    if user_id in visitors["members"]:
        await client.remove_member(visitors["_id"], user_id)
    # Die Arbeitskopie des Hosts geht erst mit `close`.
    if user_id != current["hostId"]:
        await models.delete_room_models(room_id, user_id)


async def share(
    host_id: str,
    name: str,
    contract: dict[str, Any],
    units: list[dict[str, Any]],
    anonymous: bool,
    edit: bool,
    comment: bool,
    task: dict[str, Any] | None = None,
) -> tuple[str, str, bool]:
    """Shares in a new workpiece; the room and groups of the host are reused.

    With `task` (title, text, version) the task comes along: its text as a fixed CK task, plus a
    second workpiece for marks and notes. The contract of the model points to both.

    Returns the room, the workpiece and whether it was newly created. If the host is already
    sharing, everything stays as it is, including the rights they have changed in the room since.
    """
    try:
        current = await store.find_by_owner(host_id)
    except ApiError as error:
        # A half-created room (aborted while creating) is skipped and left as it is.
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
    task_workpiece_id = None
    if task is not None:
        # The task first, because the contract of the model cannot be changed once created.
        task_workpiece = await client.create_workpiece(
            {
                "name": f"{name} – Task",
                "roomId": room_id,
                "contract": {"tool": "modeling-copilot", "format": TASK_FORMAT, "version": 1, "taskVersion": task["taskVersion"]},
                "units": [{"path": [MARKS_MAP]}],
            }
        )
        task_workpiece_id = task_workpiece["_id"]
        ck_task = await client.create_task(
            {
                "kind": "assignment",
                "title": task["title"],
                "state": "open",
                "anchor": {"kind": "workpiece", "id": task_workpiece_id},
                "detail": {
                    "contentHtml": task["contentHtml"],
                    "taskVersion": task["taskVersion"],
                    **({"settings": task["settings"]} if "settings" in task else {}),
                },
            }
        )
        contract = {**contract, "task": {"workpieceId": task_workpiece_id, "taskId": ck_task["_id"]}}
    workpiece = await client.create_workpiece(
        {"name": name, "roomId": room_id, "contract": contract, "units": units}
    )
    # Auffangnetz: Kopien früherer Shares dieses Raums, die beim Schließen noch offen waren und liegen blieben.
    await models.delete_room_models(room_id, keep_workpiece_id=workpiece["_id"])
    # A new share starts clean: nothing remembered from a lock before may carry over.
    await store.save(
        room_id,
        open=True,
        joinable=True,
        workpieceId=workpiece["_id"],
        taskWorkpieceId=task_workpiece_id,
        before=None,
        autoLocked=False,
    )
    return room_id, workpiece["_id"], True


async def _own_share(host_id: str) -> dict[str, Any]:
    current = await store.find_by_owner(host_id)
    if current is None:
        raise not_found()
    return current


async def own_share(host_id: str) -> dict[str, Any]:
    """The share of the host as stored; a host who never shared gets a 404."""
    return await _own_share(host_id)


def _restored(before: dict[str, Any]) -> list[str]:
    """The remembered rights, cleaned up: `see` always, otherwise only what visitors may have."""
    rights = before.get("rights")
    return ["see", *[r for r in RESTORABLE[1:] if isinstance(rights, list) and r in rights]]


async def set_open(host_id: str, open_: bool, auto: bool = False) -> None:
    """Locks the room or opens it again (aborted while leaving).

    Locked, nobody gets in and the visitors can no longer edit, so that everyone sees the same
    state while the host saves. The room remembers their rights from before.

    Two ends are kept apart: what the host does is orderly and never counts as `auto`; only the sweep
    locks with `auto=True`, because the host is gone, and only such a lock does it open again.
    """
    current = await _own_share(host_id)
    room_id, visitors = current["roomId"], current["groups"][store.VISITORS]
    if not open_:
        # Already locked: what was remembered stays, otherwise the already reduced rights would be in there.
        before = current["before"]
        if before is None:
            granted = next(
                (g for g in await client.list_grants(room_id) if g["groupId"] == visitors), {}
            )
            before = {"rights": granted.get("rights", ["see"]), "anonymous": granted.get("anonymous") is True}
        # Without `auto` the lock is the host's, so the sweep never opens it.
        await store.save(room_id, open=False, before=before, autoLocked=auto)
        frozen = [right for right in _restored(before) if right != "edit"]
        await client.set_grant(visitors, frozen, room_id, before.get("anonymous") is True)
        return
    if not current["workpieceId"]:
        raise ApiError(409, "SHARE_CLOSED", "The host is not sharing in this room.")
    if current["before"] is not None:
        await client.set_grant(
            visitors, _restored(current["before"]), room_id, current["before"].get("anonymous") is True
        )
    await store.save(room_id, open=True, before=None, autoLocked=False)


async def set_joinable(host_id: str, joinable: bool) -> None:
    """Closes the link for new visitors or opens it again; whoever is already in stays, rights stay."""
    current = await _own_share(host_id)
    if not current["workpieceId"]:
        raise ApiError(409, "SHARE_CLOSED", "The host is not sharing in this room.")
    await store.save(current["roomId"], joinable=joinable)


async def close(host_id: str) -> None:
    """Ends sharing: visitors out, workpieces out of the room; the room and groups stay.

    Every step can be repeated, an aborted call is finished by a new one.
    """
    current = await _own_share(host_id)
    room_id = current["roomId"]
    # Wer gerade verbunden ist, hat seine Arbeitskopie noch offen; sie geht erst mit seinem `leave`.
    try:
        here: set[str] | None = {entry["actorId"] for entry in await client.room_presence(room_id)}
    except ApiError:
        here = None
    visitors = await client.get_group(current["groups"][store.VISITORS])
    # Close first, so that nobody joins while cleaning up.
    await store.save(room_id, open=False)
    for member in visitors["members"]:
        await client.remove_member(visitors["_id"], member)
    room = await client.get_room(room_id)
    for workpiece_id in (current["workpieceId"], current["taskWorkpieceId"]):
        if workpiece_id in room["workpieces"]:
            await client.remove_workpiece_from_room(room_id, workpiece_id)
    # Die Kopie des Hosts geht immer, er hat gespeichert; die der Visitors nur, wenn sie nicht mehr verbunden sind.
    # Antwortet CK nicht, bleiben die der Visitors stehen, die nächste Share räumt sie auf.
    if here is None:
        await models.delete_room_models(room_id, host_id)
    else:
        await models.delete_room_models(room_id, except_owners=here - {host_id})
    await store.save(room_id, workpieceId=None, taskWorkpieceId=None, before=None, autoLocked=False)
