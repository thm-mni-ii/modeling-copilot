import asyncio
import json

import httpx
import pytest

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client, store


def share_room(**extra):
    return {
        "_id": "R",
        "createdBy": "service-modeling-copilot",
        "settings": {
            "share": {"open": True, "groups": {"hosts": "G1", "visitors": "G2"}},
            **extra,
        },
    }


def share_group(group_id, role, room_id="R", created="2026-01-01T00:00:00Z", **share):
    return {
        "_id": group_id,
        "createdAt": created,
        "settings": {"share": {"role": role, "roomId": room_id, **share}},
    }


@pytest.fixture
def ck(monkeypatch):
    """Ein kleines CK im Speicher: Räume und Gruppen nach ID, dazu die gesendeten PATCH-Körper."""
    rooms = {"R": share_room()}
    groups = {
        "G1": share_group("G1", "hosts", ownerId="42"),
        "G2": share_group("G2", "visitors"),
        # Die Gruppe des Dienstes selbst trägt kein share-Feld.
        "S": {"_id": "S", "createdAt": "2025-01-01T00:00:00Z", "settings": {}},
    }
    patches: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/groups":
            return httpx.Response(200, json=list(groups.values()))
        if request.method == "GET" and path.startswith("/groups/"):
            return httpx.Response(200, json=groups[path.split("/")[2]])
        if request.method == "GET" and path.startswith("/rooms/"):
            return httpx.Response(200, json=rooms[path.split("/")[2]])
        if request.method == "PATCH" and path.startswith("/rooms/"):
            patches.append(json.loads(request.content))
            return httpx.Response(200, json=rooms["R"])
        return httpx.Response(404, json={"error": "unknown"})

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(handle))
    monkeypatch.setattr(client, "service_token", lambda: "token")
    monkeypatch.setattr(settings, "service_actor", "service-modeling-copilot")
    return rooms, groups, patches


def test_read_returns_the_share_when_the_groups_vouch_for_it(ck):
    share = asyncio.run(store.read("R"))
    assert share == {
        "roomId": "R",
        "open": True,
        "workpieceId": None,
        "groups": {"hosts": "G1", "visitors": "G2"},
        "before": None,
    }


@pytest.mark.parametrize(
    "visitors",
    [
        "S",  # die Gruppe des Dienstes, ohne share-Feld
        "G1",  # die falsche Rolle
    ],
)
def test_read_rejects_a_group_that_does_not_vouch_for_the_room(ck, visitors):
    rooms, _, _ = ck
    rooms["R"]["settings"]["share"]["groups"]["visitors"] = visitors
    with pytest.raises(ApiError) as error:
        asyncio.run(store.read("R"))
    assert error.value.code == "SHARE_INVALID"


def test_read_rejects_a_group_of_another_room(ck):
    _, groups, _ = ck
    groups["G2"] = share_group("G2", "visitors", room_id="OTHER")
    with pytest.raises(ApiError) as error:
        asyncio.run(store.read("R"))
    assert error.value.code == "SHARE_INVALID"


def test_read_rejects_a_room_without_share_or_not_made_by_the_service(ck):
    rooms, _, _ = ck
    rooms["R"]["createdBy"] = "42"
    with pytest.raises(ApiError) as error:
        asyncio.run(store.read("R"))
    assert error.value.status == 404


def test_save_keeps_foreign_settings(ck):
    rooms, _, patches = ck
    rooms["R"] = share_room(other=1)
    asyncio.run(store.save("R", open=False, workpieceId="W"))
    assert patches == [
        {
            "settings": {
                "other": 1,
                "share": {
                    "open": False,
                    "workpieceId": "W",
                    "groups": {"hosts": "G1", "visitors": "G2"},
                },
            }
        }
    ]


def test_find_by_owner_takes_the_older_of_two_rooms(ck):
    rooms, groups, _ = ck
    rooms["R2"] = {**share_room(), "_id": "R2"}
    groups["G3"] = share_group("G3", "hosts", room_id="R2", created="2026-02-01T00:00:00Z", ownerId="42")
    rooms["R2"]["settings"]["share"]["groups"] = {"hosts": "G3"}
    assert asyncio.run(store.find_by_owner("42"))["roomId"] == "R"
    assert asyncio.run(store.find_by_owner("43")) is None
