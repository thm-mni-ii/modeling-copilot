import asyncio
import json

import httpx
import pytest

from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client


@pytest.fixture
def ck(monkeypatch):
    """Intercepts the requests to CK; the test sets the answer through `answer`."""
    seen: list[httpx.Request] = []
    answer = {"status": 200, "json": {"_id": "1"}}

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(answer["status"], json=answer["json"])

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(handle))
    monkeypatch.setattr(client, "service_token", lambda: "token")
    return seen, answer


def test_calls_carry_the_service_token_and_the_ck_paths(ck):
    seen, _ = ck

    async def calls():
        await client.create_room("Room")
        await client.add_member("g1", "42")
        await client.set_grant("g1", ["see"], room_id="r1", anonymous=True)
        await client.add_workpiece_to_room("r1", "w1")

    asyncio.run(calls())

    assert [(r.method, r.url.path) for r in seen] == [
        ("POST", "/rooms"),
        ("POST", "/groups/g1/members"),
        ("PUT", "/grants"),
        ("POST", "/rooms/r1/workpieces"),
    ]
    assert json.loads(seen[3].content) == {"workpieceId": "w1"}
    assert all(r.headers["Authorization"] == "Bearer token" for r in seen)
    assert json.loads(seen[1].content) == {"actorId": "42"}
    assert json.loads(seen[2].content) == {
        "groupId": "g1",
        "rights": ["see"],
        "anonymous": True,
        "scope": {"kind": "room", "id": "r1"},
    }


def test_refusal_of_ck_becomes_an_api_error(ck):
    _, answer = ck
    answer.update(status=403, json={"error": "not allowed to create a room"})
    with pytest.raises(ApiError) as error:
        asyncio.run(client.create_room("Room"))
    assert error.value.code == "CK_REQUEST_FAILED" and "403" in error.value.message
