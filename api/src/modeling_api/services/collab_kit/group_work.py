"""Gruppenarbeit in Collab-Kit: Tutoren legen aus einer Teilnehmerliste Räume an.

Je Gruppe ein Raum und eine CK-Gruppe, in der alle dieselben Rechte haben, und je Aufgabe ein
Modell wie beim Teilen: feste CK-Aufgabe, Werkstück für Markierungen und Notizen, das Modell.
Räume und Gruppen tragen `groupWork` statt `share`, Teilen und Sweep sehen sie also nicht.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from modeling_api.core.auth import User
from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services import models
from modeling_api.services.collab_kit import client
from modeling_api.services.collab_kit.share import create_model_workpiece
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


async def create(user: User, groups: list[dict[str, Any]], token: str | None) -> list[dict[str, Any]]:
    """Legt je Gruppe Raum, CK-Gruppe und je Aufgabe ein Modell an; wer im FBS fehlt, kommt nicht hinein und steht in `missing`."""
    require(is_moderator(user))
    ids = await fbs_ids(token)
    # Jede Aufgabe einmal aus der DB, auch wenn mehrere Gruppen sie bearbeiten; ein unbekanntes Release ist ein 404, bevor etwas entsteht.
    references = {(task["taskId"], task["versionId"]): task for group in groups for task in group["tasks"]}
    tasks = {key: await models.task_for_room(reference) for key, reference in references.items()}
    marker = {"importedBy": user.id, "importedAt": datetime.now(timezone.utc).isoformat()}

    created = []
    for group in groups:
        members = [ids[name] for name in group["usernames"] if name in ids]
        room_id = (await client.create_room(group["name"], {KEY: marker}))["_id"]
        ck_group = await client.create_group(group["name"], list(dict.fromkeys(members)), {KEY: {"roomId": room_id}})
        await client.set_grant(ck_group["_id"], MEMBER_RIGHTS, room_id)
        workpiece_ids = []
        for reference in group["tasks"]:
            # Die Sprachen gehen in den Contract des Modells, der Rest wie beim Teilen in die CK-Aufgabe.
            room_task = dict(tasks[(reference["taskId"], reference["versionId"])])
            languages = room_task.pop("workspaceLanguages")
            workpiece_id, _ = await create_model_workpiece(room_id, room_task["title"], model_contract(languages), MODEL_UNITS, room_task)
            workpiece_ids.append(workpiece_id)
        created.append(
            {
                "name": group["name"],
                "roomId": room_id,
                "workpieceIds": workpiece_ids,
                "missing": [name for name in group["usernames"] if name not in ids],
            }
        )
    return created
