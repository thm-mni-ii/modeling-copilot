"""Group work in Collab-Kit: tutors create rooms from a list of participants.

Per group one room and one CK group in which everyone has the same rights, and per task one
model as when sharing: fixed CK task, workpiece for marks and notes, the model.
Rooms and groups carry `groupWork` instead of `share`, so sharing and the sweep do not see them.
A room belongs to a course; importing the same course again gives existing rooms only what
they lack: new people and models for new tasks. Nobody is removed.
When a course is over, it goes into the CK archive with all its rooms (`archive_course`).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError
from modeling_api.services import fbs_users, models
from modeling_api.services.collab_kit import archive, client
from modeling_api.services.collab_kit.errors import archive_disabled
from modeling_api.services.collab_kit.workpieces import MODEL_UNITS, TASK_FORMAT, create_model_workpiece, model_contract
from modeling_api.services.submissions import is_moderator, require

logger = logging.getLogger(__name__)

KEY = "groupWork"
# Everyone in the group sees, comments and edits; tasks, decisions and rights stay with the tutors.
MEMBER_RIGHTS = ["see", "speak", "edit"]


def _mark(item: dict[str, Any]) -> dict[str, Any]:
    """The import mark of a room or group, otherwise {}."""
    mark = (item.get("settings") or {}).get(KEY)
    return mark if isinstance(mark, dict) else {}


def same(text: str) -> str:
    """How course and group names are compared: case and whitespace do not matter."""
    return " ".join(text.split()).casefold()


def in_course(room: dict[str, Any], course: str) -> bool:
    """Whether an import created this room for the course."""
    return bool(_mark(room)) and same(str(_mark(room).get("course", ""))) == same(course)


async def existing_rooms(course: str) -> dict[str, dict[str, Any]]:
    """The rooms of earlier imports of this course per group name: room, CK group, members and the tasks that already have a model."""
    rooms = [room for room in await client.list_rooms() if in_course(room, course)]
    if not rooms:
        return {}
    groups = {_mark(group)["roomId"]: group for group in await client.list_groups() if "roomId" in _mark(group)}
    workpieces = {workpiece["_id"]: workpiece for workpiece in await client.list_workpieces()}
    found: dict[str, dict[str, Any]] = {}
    for room in rooms:
        group = groups.get(room["_id"])
        # Which tasks a room has is in the contract of its task workpieces; another release of the same task counts too.
        task_ids = {
            str(contract["taskVersion"]["taskId"])
            for workpiece_id in room.get("workpieces", [])
            if (contract := workpieces.get(workpiece_id, {}).get("contract", {})).get("format") == TASK_FORMAT and contract.get("taskVersion")
        }
        # If the same name exists twice, e.g. from before this check existed, the first one wins.
        found.setdefault(
            same(room["name"]),
            {
                "roomId": room["_id"],
                "groupId": group["_id"] if group else None,
                "members": set(group["members"]) if group else set(),
                "taskIds": task_ids,
                "settings": group["settings"] if group else {},
            },
        )
    return found


async def plan(user: User, course: str, groups: list[dict[str, Any]], token: str | None) -> list[dict[str, Any]]:
    """What an import would do, without writing anything: per group a new room, or only the new people and missing tasks of the existing one."""
    require(is_moderator(user))
    ids = await fbs_users.ids_by_username(token)
    rooms = await existing_rooms(course)
    planned = []
    for group in groups:
        room = rooms.get(same(group["name"]))
        members = room["members"] if room else set()
        tasks = room["taskIds"] if room else set()
        # New people as username → FBS ID, without duplicates and without those already in.
        new = {name: ids[name] for name in group["usernames"] if name in ids and ids[name] not in members}
        planned.append(
            {
                "name": group["name"],
                "roomId": room["roomId"] if room else None,
                "groupId": room["groupId"] if room else None,
                "newMembers": list(new),
                "newMemberIds": list(new.values()),
                "newTasks": [task for task in group["tasks"] if str(task["taskId"]) not in tasks],
                "missing": [name for name in group["usernames"] if name not in ids],
                # Per FBS ID the name from the list; CK knows names only after the first visit, until then the tab shows this one.
                "names": {ids[name]: label for name, label in group.get("names", {}).items() if name in ids and label},
                "settings": room["settings"] if room else {},
            }
        )
    return planned


async def _ensure_group(entry: dict[str, Any], room_id: str) -> None:
    """Creates the group with its rights, or adds new people and names to the existing one."""
    # A new room gets its group; so does an existing one whose group someone deleted by hand.
    if entry["groupId"] is None:
        ck_group = await client.create_group(entry["name"], entry["newMemberIds"], {KEY: {"roomId": room_id, "names": entry["names"]}})
        await client.set_grant(ck_group["_id"], MEMBER_RIGHTS, room_id)
        return
    for member in entry["newMemberIds"]:
        await client.add_member(entry["groupId"], member)
    # New names are added to the old ones; CK replaces the settings as a whole, so foreign keys are sent along.
    mark = entry["settings"].get(KEY, {})
    names = {**mark.get("names", {}), **entry["names"]}
    if names != mark.get("names", {}):
        await client.update_group_settings(entry["groupId"], {**entry["settings"], KEY: {**mark, "names": names}})


async def _add_models(room_id: str, references: list[dict[str, Any]], tasks: dict[tuple, dict[str, Any]]) -> list[str]:
    """Creates one model in the room per new task; returns the new models."""
    workpiece_ids = []
    for reference in references:
        # The languages go into the contract of the model, the rest into the CK task as when sharing.
        room_task = dict(tasks[(reference["taskId"], reference["versionId"])])
        languages = room_task.pop("workspaceLanguages")
        workpiece_id, _ = await create_model_workpiece(room_id, room_task["title"], model_contract(languages), MODEL_UNITS, room_task)
        workpiece_ids.append(workpiece_id)
    return workpiece_ids


async def create(user: User, course: str, groups: list[dict[str, Any]], token: str | None) -> list[dict[str, Any]]:
    """Carries out the plan: new rooms with group, rights and one model per task; existing ones get only what they lack.
    Whoever is missing in the FBS is not added and is listed in `missing`; whoever is missing from the list stays where they are."""
    planned = await plan(user, course, groups, token)
    # Each new task is loaded from the DB once, even if several groups work on it; an unknown release is a 404 before anything is created.
    references = {(task["taskId"], task["versionId"]): task for entry in planned for task in entry["newTasks"]}
    tasks = {key: await models.task_for_room(reference) for key, reference in references.items()}
    marker = {"course": course, "importedBy": user.id, "importedAt": datetime.now(timezone.utc).isoformat()}

    created = []
    for entry in planned:
        room_id = entry["roomId"] or (await client.create_room(entry["name"], {KEY: marker}))["_id"]
        await _ensure_group(entry, room_id)
        workpiece_ids = await _add_models(room_id, entry["newTasks"], tasks)
        created.append(
            {
                "name": entry["name"],
                "roomId": room_id,
                "created": entry["roomId"] is None,
                "addedMembers": entry["newMembers"],
                "workpieceIds": workpiece_ids,
                "missing": entry["missing"],
            }
        )
    return created


async def archive_course(user: User, course: str) -> dict[str, Any]:
    """Puts all rooms of a course into the CK archive: per room its workpieces, its group, then the room.

    Workpieces first, since an archived room would leave them live without a room; CK remembers their room and
    puts them back on restore, whatever the order of restoring. A workpiece that also lies in a room outside
    the course stays live there. If one fails, group and room stay;
    a new call finishes the rest, since it no longer finds archived rooms.
    """
    require(is_moderator(user))
    if not await archive.enabled():
        raise archive_disabled()
    reason = f"course archived: {course}"
    rooms = await client.list_rooms()
    ours = [room for room in rooms if in_course(room, course)]
    ids = {room["_id"] for room in ours}
    elsewhere = {workpiece_id for room in rooms if room["_id"] not in ids for workpiece_id in room.get("workpieces", [])}
    groups = [group for group in await client.list_groups() if _mark(group).get("roomId") in ids]
    done = {"rooms": 0, "groups": 0, "workpieces": 0, "failed": []}
    for room in ours:
        try:
            for workpiece_id in room.get("workpieces", []):
                if workpiece_id not in elsewhere:
                    await client.archive_workpiece(workpiece_id, reason)
                    done["workpieces"] += 1
            for group in groups:
                if _mark(group)["roomId"] == room["_id"]:
                    await client.archive_group(group["_id"], reason)
                    done["groups"] += 1
            await client.archive_room(room["_id"], reason)
            done["rooms"] += 1
        except ApiError:
            # 409 while CK is moving part of it, or CK does not answer: the room stays for a new call.
            logger.warning("Room %s of course %s could not be archived.", room["_id"], course, exc_info=True)
            done["failed"].append(room["name"])
    return done
