"""REST-Aufrufe an Collab-Kit (CK) mit dem Dienst-Token.

Nur die Aufrufe, die das Teilen braucht; was beim Teilen passiert, steht in share.py.
Antworten gibt der Client unverändert als JSON zurück.
"""

from typing import Any

import httpx

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit.token import service_token

# Nur für Tests: ein anderer Transport statt des Netzwerks.
_transport: httpx.AsyncBaseTransport | None = None


async def _request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(
            base_url=settings.ck_base_url, timeout=15, transport=_transport
        ) as client:
            response = await client.request(
                method, path, json=body, headers={"Authorization": f"Bearer {service_token()}"}
            )
    except httpx.HTTPError as error:
        raise ApiError(503, "CK_UNAVAILABLE", "Collab-Kit is currently unavailable.") from error
    if not response.is_success:
        # CK antwortet bei Fehlern mit {"error": "..."}.
        try:
            reason = response.json().get("error", "")
        except ValueError:
            reason = ""
        raise ApiError(
            502, "CK_REQUEST_FAILED", f"Collab-Kit refused the request ({response.status_code}): {reason}"
        )
    return response.json()


async def create_room(name: str, settings: dict[str, Any] | None = None) -> dict:
    return await _request("POST", "/rooms", {"name": name, "settings": settings or {}})


async def get_room(room_id: str) -> dict:
    return await _request("GET", f"/rooms/{room_id}")


async def update_room_settings(room_id: str, settings: dict[str, Any]) -> dict:
    """CK ersetzt die settings als Ganzes; fremde Schlüssel muss der Aufrufer mitschicken."""
    return await _request("PATCH", f"/rooms/{room_id}", {"settings": settings})


async def create_group(
    name: str, members: list[str] | None = None, settings: dict[str, Any] | None = None
) -> dict:
    return await _request(
        "POST", "/groups", {"name": name, "members": members or [], "settings": settings or {}}
    )


async def list_groups() -> list[dict]:
    return await _request("GET", "/groups")


async def get_group(group_id: str) -> dict:
    return await _request("GET", f"/groups/{group_id}")


async def add_member(group_id: str, actor_id: str) -> dict:
    return await _request("POST", f"/groups/{group_id}/members", {"actorId": actor_id})


async def remove_member(group_id: str, actor_id: str) -> dict:
    return await _request("DELETE", f"/groups/{group_id}/members/{actor_id}")


async def set_grant(
    group_id: str, rights: list[str], room_id: str | None = None, anonymous: bool = False
) -> dict:
    """Setzt, was die Gruppe am Raum darf, und ersetzt dabei den bisherigen Grant dort."""
    body: dict[str, Any] = {"groupId": group_id, "rights": rights, "anonymous": anonymous}
    if room_id is not None:
        body["scope"] = {"kind": "room", "id": room_id}
    return await _request("PUT", "/grants", body)


async def create_workpiece(workpiece: dict[str, Any]) -> dict:
    """Legt ein Werkstück an; `roomId` im Körper legt es gleich in den Raum."""
    return await _request("POST", "/workpieces", workpiece)


async def add_workpiece_to_room(room_id: str, workpiece_id: str) -> dict:
    return await _request("POST", f"/rooms/{room_id}/workpieces", {"workpieceId": workpiece_id})


async def remove_workpiece_from_room(room_id: str, workpiece_id: str) -> dict:
    return await _request("DELETE", f"/rooms/{room_id}/workpieces/{workpiece_id}")
