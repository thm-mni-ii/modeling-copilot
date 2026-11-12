"""Gruppenarbeit in Collab-Kit: Tutoren legen aus einer Teilnehmerliste Räume an.

Je Gruppe ein Raum und eine CK-Gruppe, in der alle dieselben Rechte haben, und je Aufgabe ein
Modell wie beim Teilen: feste CK-Aufgabe, Werkstück für Markierungen und Notizen, das Modell.
Räume und Gruppen tragen `groupWork` statt `share`, Teilen und Sweep sehen sie also nicht.
Ein Raum gehört zu einem Kurs; importiert man denselben Kurs noch einmal, bekommen vorhandene
Räume nur, was ihnen fehlt: neue Personen und Modelle für neue Aufgaben. Niemand wird entfernt.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from modeling_api.core.auth import User
from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services import models
from modeling_api.services.collab_kit import client
from modeling_api.services.collab_kit.share import TASK_FORMAT, create_model_workpiece
from modeling_api.services.fbs_users import users_uri
from modeling_api.services.submissions import is_moderator, require

KEY = "groupWork"
# Alle in der Gruppe sehen, kommentieren und bearbeiten; Aufgaben, Entscheidungen und Rechte bleiben bei den Tutoren.
MEMBER_RIGHTS = ["see", "speak", "edit"]


MODEL_UNITS = [{"path": ["cells"]}]


def model_contract(languages: list[dict[str, Any]]) -> dict[str, Any]:
    """Der Contract eines Modells, wie ihn der Browser baut (`newWorkpiece`), mit den Sprachen der Aufgabe als Start."""
    return {"tool": "modeling-copilot", "format": "copilot-cells", "version": 1, "languages": languages, "history": "none"}


async def fbs_ids(token: str | None) -> dict[str, str]:
    """Anmeldename → ID aller Konten im FBS, mit dem Token des Tutors; das FBS zeigt die Liste nur Admins, Moderatoren und Dozenten."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if not settings.fbs_users_uri and settings.oidc_token_host:
        headers["Host"] = settings.oidc_token_host
    try:
        async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=False) as http:
            response = await http.get(users_uri())
    except httpx.HTTPError as error:
        raise ApiError(502, "FBS_UNAVAILABLE", "The Feedbacksystem could not be reached.") from error
    if response.status_code in (401, 403):
        raise ApiError(403, "FBS_FORBIDDEN", "The Feedbacksystem does not list its users for you.")
    if response.status_code != 200:
        raise ApiError(502, "FBS_UNAVAILABLE", "The Feedbacksystem did not list its users.")
    return {
        str(user["username"]): str(user["id"])
        for user in response.json()
        if isinstance(user, dict) and user.get("username") and user.get("id") is not None
    }


def same(text: str) -> str:
    """Wie Kurs und Gruppe verglichen werden: Groß- und Kleinschreibung und Leerzeichen zählen nicht."""
    return " ".join(text.split()).casefold()


async def existing_rooms(course: str) -> dict[str, dict[str, Any]]:
    """Die Räume früherer Importe dieses Kurses je Gruppenname: Raum, CK-Gruppe, Mitglieder und die Aufgaben, die schon ein Modell haben."""
    rooms = [
        room
        for room in await client.list_rooms()
        if isinstance(room.get("settings", {}).get(KEY), dict) and same(str(room["settings"][KEY].get("course", ""))) == same(course)
    ]
    if not rooms:
        return {}
    groups = {
        group["settings"][KEY]["roomId"]: group
        for group in await client.list_groups()
        if isinstance((group.get("settings") or {}).get(KEY), dict) and "roomId" in group["settings"][KEY]
    }
    workpieces = {workpiece["_id"]: workpiece for workpiece in await client.list_workpieces()}
    found: dict[str, dict[str, Any]] = {}
    for room in rooms:
        group = groups.get(room["_id"])
        # Welche Aufgaben ein Raum hat, steht im Contract seiner Aufgaben-Werkstücke; ein anderes Release derselben Aufgabe zählt mit.
        task_ids = {
            str(contract["taskVersion"]["taskId"])
            for workpiece_id in room.get("workpieces", [])
            if (contract := workpieces.get(workpiece_id, {}).get("contract", {})).get("format") == TASK_FORMAT and contract.get("taskVersion")
        }
        # Gibt es denselben Namen doppelt, etwa aus der Zeit vor dieser Prüfung, gilt der erste.
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
    """Was ein Import täte, ohne etwas zu schreiben: je Gruppe ein neuer Raum, oder nur die neuen Personen und fehlenden Aufgaben des vorhandenen."""
    require(is_moderator(user))
    ids = await fbs_ids(token)
    rooms = await existing_rooms(course)
    planned = []
    for group in groups:
        room = rooms.get(same(group["name"]))
        members = room["members"] if room else set()
        tasks = room["taskIds"] if room else set()
        planned.append(
            {
                "name": group["name"],
                "roomId": room["roomId"] if room else None,
                "groupId": room["groupId"] if room else None,
                "newMembers": list(dict.fromkeys(name for name in group["usernames"] if name in ids and ids[name] not in members)),
                "newMemberIds": list(dict.fromkeys(ids[name] for name in group["usernames"] if name in ids and ids[name] not in members)),
                "newTasks": [task for task in group["tasks"] if str(task["taskId"]) not in tasks],
                "missing": [name for name in group["usernames"] if name not in ids],
                # Je FBS-ID der Name aus der Liste; CK kennt Namen erst nach dem ersten Besuch, bis dahin zeigt der Reiter diesen.
                "names": {ids[name]: label for name, label in group.get("names", {}).items() if name in ids and label},
                "settings": room["settings"] if room else {},
            }
        )
    return planned


async def create(user: User, course: str, groups: list[dict[str, Any]], token: str | None) -> list[dict[str, Any]]:
    """Führt den Plan aus: neue Räume mit Gruppe, Rechten und je Aufgabe einem Modell; vorhandene bekommen nur, was ihnen fehlt.
    Wer im FBS fehlt, kommt nicht hinein und steht in `missing`; wer in der Liste fehlt, bleibt, wo er ist."""
    planned = await plan(user, course, groups, token)
    # Jede neue Aufgabe einmal aus der DB, auch wenn mehrere Gruppen sie bearbeiten; ein unbekanntes Release ist ein 404, bevor etwas entsteht.
    references = {(task["taskId"], task["versionId"]): task for entry in planned for task in entry["newTasks"]}
    tasks = {key: await models.task_for_room(reference) for key, reference in references.items()}
    marker = {"course": course, "importedBy": user.id, "importedAt": datetime.now(timezone.utc).isoformat()}

    created = []
    for entry in planned:
        room_id = entry["roomId"] or (await client.create_room(entry["name"], {KEY: marker}))["_id"]
        # Ein neuer Raum bekommt seine Gruppe; ebenso ein vorhandener, dessen Gruppe jemand von Hand gelöscht hat.
        if entry["groupId"] is None:
            ck_group = await client.create_group(entry["name"], entry["newMemberIds"], {KEY: {"roomId": room_id, "names": entry["names"]}})
            await client.set_grant(ck_group["_id"], MEMBER_RIGHTS, room_id)
        else:
            for member in entry["newMemberIds"]:
                await client.add_member(entry["groupId"], member)
            # Neue Namen kommen zu den alten; CK ersetzt die Einstellungen als Ganzes, also gehen fremde Schlüssel mit.
            mark = entry["settings"].get(KEY, {})
            names = {**mark.get("names", {}), **entry["names"]}
            if names != mark.get("names", {}):
                await client.update_group_settings(entry["groupId"], {**entry["settings"], KEY: {**mark, "names": names}})
        workpiece_ids = []
        for reference in entry["newTasks"]:
            # Die Sprachen gehen in den Contract des Modells, der Rest wie beim Teilen in die CK-Aufgabe.
            room_task = dict(tasks[(reference["taskId"], reference["versionId"])])
            languages = room_task.pop("workspaceLanguages")
            workpiece_id, _ = await create_model_workpiece(room_id, room_task["title"], model_contract(languages), MODEL_UNITS, room_task)
            workpiece_ids.append(workpiece_id)
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
