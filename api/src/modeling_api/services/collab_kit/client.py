"""REST calls to Collab-Kit (CK) with the service token.

Only the calls that sharing needs; what happens while sharing is in share.py.
The client returns answers unchanged as JSON.
"""

from typing import Any
from urllib.parse import quote

import httpx

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError, not_found
from modeling_api.services.collab_kit.token import service_token

# For tests only: another transport instead of the network.
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
    # An unknown object (room, group) is just as unknown to the caller.
    if response.status_code == 404:
        raise not_found()
    if not response.is_success:
        # On errors CK answers with {"error": "..."}.
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
    """CK replaces the settings as a whole; the caller must send foreign keys along."""
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
    # The ID comes from tokens; encoded so that no character changes the path.
    return await _request("DELETE", f"/groups/{group_id}/members/{quote(actor_id, safe='')}")


async def set_grant(
    group_id: str, rights: list[str], room_id: str | None = None, anonymous: bool = False
) -> dict:
    """Sets what the group may do in the room and replaces the previous grant there."""
    body: dict[str, Any] = {"groupId": group_id, "rights": rights, "anonymous": anonymous}
    if room_id is not None:
        body["scope"] = {"kind": "room", "id": room_id}
    return await _request("PUT", "/grants", body)


async def list_grants(room_id: str) -> list[dict]:
    """The grants that sit on exactly this room."""
    return await _request("GET", f"/grants?scopeKind=room&scopeId={room_id}")


async def create_workpiece(workpiece: dict[str, Any]) -> dict:
    """Creates a workpiece; `roomId` in the body puts it into the room right away."""
    return await _request("POST", "/workpieces", workpiece)


async def create_task(task: dict[str, Any]) -> dict:
    """Creates a task; `detail` stays fixed afterwards, CK only changes the state."""
    return await _request("POST", "/tasks", task)


async def add_workpiece_to_room(room_id: str, workpiece_id: str) -> dict:
    return await _request("POST", f"/rooms/{room_id}/workpieces", {"workpieceId": workpiece_id})


async def remove_workpiece_from_room(room_id: str, workpiece_id: str) -> dict:
    return await _request("DELETE", f"/rooms/{room_id}/workpieces/{workpiece_id}")
