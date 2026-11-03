import asyncio
import json

import httpx
import pytest

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import client, share, store

ARGS = dict(name="Model", contract={"tool": "x"}, units=[{"path": ["cells"]}])


@pytest.fixture
def ck(monkeypatch):
    """Ein kleines CK im Speicher: legt an, liest und ändert die settings, merkt sich Grants und Werkstücke."""
    rooms: dict[str, dict] = {}
    groups: dict[str, dict] = {}
    grants: list[dict] = []
    workpieces: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        body = json.loads(request.content) if request.content else {}
        if (method, path) == ("POST", "/rooms"):
            room = {"_id": f"R{len(rooms)}", "createdBy": "service-modeling-copilot", "workpieces": [], **body}
            rooms[room["_id"]] = room
            return httpx.Response(201, json=room)
        if (method, path) == ("POST", "/groups"):
            group = {"_id": f"G{len(groups)}", "createdAt": f"2026-01-01T00:00:{len(groups):02d}Z", **body}
            groups[group["_id"]] = group
            return httpx.Response(201, json=group)
        if (method, path) == ("PUT", "/grants"):
            # Wie in CK: Ein Grant je Gruppe und Ort, ein neuer ersetzt den alten.
            grants[:] = [g for g in grants if (g["groupId"], g.get("scope")) != (body["groupId"], body.get("scope"))]
            grants.append(body)
            return httpx.Response(200, json=body)
        if (method, path) == ("GET", "/grants"):
            at = request.url.params["scopeId"]
            return httpx.Response(200, json=[g for g in grants if g.get("scope", {}).get("id") == at])
        if (method, path) == ("POST", "/workpieces"):
            workpieces.append({"_id": f"W{len(workpieces)}", **body})
            rooms[body["roomId"]]["workpieces"].append(workpieces[-1]["_id"])
            return httpx.Response(201, json=workpieces[-1])
        if method == "DELETE" and "/members/" in path:
            _, _, group_id, _, actor = path.split("/")
            groups[group_id]["members"].remove(actor)
            return httpx.Response(200, json=groups[group_id])
        if method == "DELETE" and "/workpieces/" in path:
            _, _, room_id, _, workpiece_id = path.split("/")
            rooms[room_id]["workpieces"].remove(workpiece_id)
            return httpx.Response(200, json=rooms[room_id])
        if (method, path) == ("GET", "/groups"):
            return httpx.Response(200, json=list(groups.values()))
        if method == "POST" and path.endswith("/members"):
            groups[path.split("/")[2]]["members"].append(body["actorId"])
            return httpx.Response(201, json=groups[path.split("/")[2]])
        if method == "GET" and path.startswith("/groups/") and path.split("/")[2] in groups:
            return httpx.Response(200, json=groups[path.split("/")[2]])
        if method == "GET" and path.startswith("/rooms/") and path.split("/")[2] in rooms:
            return httpx.Response(200, json=rooms[path.split("/")[2]])
        if method == "PATCH" and path.startswith("/rooms/"):
            rooms[path.split("/")[2]]["settings"] = body["settings"]
            return httpx.Response(200, json=rooms[path.split("/")[2]])
        return httpx.Response(404, json={"error": "unknown"})

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(handle))
    monkeypatch.setattr(client, "service_token", lambda: "token")
    monkeypatch.setattr(settings, "service_actor", "service-modeling-copilot")
    return rooms, groups, grants, workpieces


def visitor_grant(grants, groups):
    visitors = next(g for g in groups.values() if g["settings"]["share"]["role"] == "visitors")
    return next(g for g in grants if g["groupId"] == visitors["_id"])


def test_visitors_always_see_and_the_rest_follows_the_answers():
    assert share.visitor_rights(edit=False, comment=False) == ["see"]
    assert share.visitor_rights(edit=True, comment=True) == ["see", "speak", "edit"]


def test_first_share_creates_the_room_with_both_groups(ck):
    rooms, groups, grants, workpieces = ck
    room_id, workpiece_id, created = asyncio.run(
        share.share("42", anonymous=True, edit=True, comment=False, **ARGS)
    )

    assert (room_id, workpiece_id, created) == ("R0", "W0", True)
    assert len(rooms) == 1 and len(groups) == 2
    hosts = next(g for g in groups.values() if g["settings"]["share"]["role"] == "hosts")
    assert hosts["members"] == ["42"] and hosts["settings"]["share"]["ownerId"] == "42"
    assert {g["groupId"]: g for g in grants}[hosts["_id"]]["rights"] == share.HOST_RIGHTS
    visitors = visitor_grant(grants, groups)
    assert visitors["rights"] == ["see", "edit"] and visitors["anonymous"] is True
    assert workpieces[0]["roomId"] == "R0" and rooms["R0"]["settings"]["share"]["open"] is True


def test_sharing_again_while_open_changes_nothing(ck):
    rooms, groups, grants, workpieces = ck
    asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, **ARGS))
    seen = (len(grants), len(workpieces))

    result = asyncio.run(share.share("42", anonymous=True, edit=False, comment=False, **ARGS))

    assert result == ("R0", "W0", False)
    assert (len(grants), len(workpieces), len(rooms), len(groups)) == (*seen, 1, 2)


def test_sharing_after_a_close_reuses_room_and_groups_with_the_new_answers(ck):
    rooms, groups, grants, workpieces = ck
    asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, **ARGS))
    asyncio.run(store.save("R0", open=False, workpieceId=None))

    result = asyncio.run(share.share("42", anonymous=True, edit=False, comment=False, **ARGS))

    assert result == ("R0", "W1", True)
    assert (len(rooms), len(groups)) == (1, 2)
    assert visitor_grant(grants, groups)["rights"] == ["see"]
    assert visitor_grant(grants, groups)["anonymous"] is True


def test_another_host_gets_a_room_of_their_own(ck):
    rooms, _, _, _ = ck
    asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, **ARGS))
    result = asyncio.run(share.share("43", anonymous=False, edit=True, comment=True, **ARGS))
    assert result[0] == "R1" and len(rooms) == 2


def members_of(groups, role):
    return next(g for g in groups.values() if g["settings"]["share"]["role"] == role)["members"]


def test_a_visitor_joins_once_and_the_host_stays_out_of_the_visitors(ck):
    _, groups, _, _ = ck
    room_id, workpiece_id, _ = asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, **ARGS))

    assert asyncio.run(share.join("99", room_id)) == (workpiece_id, "visitor")
    assert asyncio.run(share.join("99", room_id)) == (workpiece_id, "visitor")
    assert asyncio.run(share.join("42", room_id)) == (workpiece_id, "host")
    assert members_of(groups, "visitors") == ["99"]


def test_nobody_joins_a_room_the_host_has_closed(ck):
    _, groups, _, _ = ck
    room_id, _, _ = asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, **ARGS))
    asyncio.run(store.save(room_id, open=False, workpieceId=None))

    with pytest.raises(ApiError) as error:
        asyncio.run(share.join("99", room_id))
    assert error.value.code == "SHARE_CLOSED" and members_of(groups, "visitors") == []


def test_a_room_that_is_no_share_or_unknown_is_not_found(ck):
    rooms, _, _, _ = ck
    rooms["P"] = {"_id": "P", "createdBy": "service-modeling-copilot", "settings": {}}
    for room_id in ("P", "nope"):
        with pytest.raises(ApiError) as error:
            asyncio.run(share.join("99", room_id))
        assert error.value.status == 404


def start(answers=dict(anonymous=True, edit=True, comment=True)):
    return asyncio.run(share.share("42", **answers, **ARGS))[0]


def test_locking_stops_joins_and_takes_edit_away_while_remembering_what_there_was(ck):
    rooms, groups, grants, _ = ck
    room_id = start()

    asyncio.run(share.set_open("42", False))

    grant = visitor_grant(grants, groups)
    assert grant["rights"] == ["see", "speak"] and grant["anonymous"] is True
    assert rooms[room_id]["settings"]["share"]["open"] is False
    assert rooms[room_id]["settings"]["share"]["before"] == {"rights": ["see", "speak", "edit"], "anonymous": True}
    with pytest.raises(ApiError):
        asyncio.run(share.join("99", room_id))


def test_locking_twice_keeps_the_rights_from_before_the_first_lock(ck):
    rooms, _, _, _ = ck
    room_id = start()
    asyncio.run(share.set_open("42", False))
    asyncio.run(share.set_open("42", False))
    assert rooms[room_id]["settings"]["share"]["before"]["rights"] == ["see", "speak", "edit"]


def test_opening_again_gives_back_the_rights_and_the_room(ck):
    rooms, groups, grants, _ = ck
    room_id = start()
    asyncio.run(share.set_open("42", False))

    asyncio.run(share.set_open("42", True))

    assert visitor_grant(grants, groups)["rights"] == ["see", "speak", "edit"]
    assert rooms[room_id]["settings"]["share"]["open"] is True
    assert rooms[room_id]["settings"]["share"]["before"] is None


def test_opening_is_refused_once_the_workpiece_has_left_the_room(ck):
    start()
    asyncio.run(share.close("42"))
    with pytest.raises(ApiError) as error:
        asyncio.run(share.set_open("42", True))
    assert error.value.code == "SHARE_CLOSED"


def test_closing_takes_visitors_and_workpiece_out_but_keeps_room_and_groups(ck):
    rooms, groups, _, _ = ck
    room_id = start()
    asyncio.run(share.join("99", room_id))
    asyncio.run(share.set_open("42", False))

    asyncio.run(share.close("42"))

    assert members_of(groups, "visitors") == [] and members_of(groups, "hosts") == ["42"]
    assert rooms[room_id]["workpieces"] == []
    shared = rooms[room_id]["settings"]["share"]
    assert (shared["open"], shared["workpieceId"], shared["before"]) == (False, None, None)
    assert len(rooms) == 1 and len(groups) == 2
    with pytest.raises(ApiError):
        asyncio.run(share.join("99", room_id))


def test_closing_again_changes_nothing_and_a_new_share_reuses_the_room(ck):
    rooms, _, _, _ = ck
    start()
    asyncio.run(share.close("42"))
    asyncio.run(share.close("42"))
    assert start() == "R0" and len(rooms) == 1


def test_only_the_host_may_lock_open_or_close(ck):
    room_id = start()
    asyncio.run(share.join("99", room_id))
    for user in ("99", "stranger"):
        for call in (lambda u: share.set_open(u, False), share.close):
            with pytest.raises(ApiError) as error:
                asyncio.run(call(user))
            assert error.value.status == 404


def test_nobody_new_joins_while_the_link_is_closed(ck):
    _, groups, _, _ = ck
    room_id = start()
    asyncio.run(share.set_joinable("42", False))

    with pytest.raises(ApiError) as error:
        asyncio.run(share.join("99", room_id))
    assert error.value.code == "SHARE_CLOSED" and members_of(groups, "visitors") == []


def test_members_and_the_host_still_pass_while_the_link_is_closed(ck):
    room_id = start()
    asyncio.run(share.join("99", room_id))
    asyncio.run(share.set_joinable("42", False))

    assert asyncio.run(share.join("99", room_id))[1] == "visitor"
    assert asyncio.run(share.join("42", room_id))[1] == "host"


def test_closing_the_link_changes_no_rights_and_only_the_host_may_do_it(ck):
    rooms, groups, grants, _ = ck
    room_id = start()
    before = dict(visitor_grant(grants, groups))

    asyncio.run(share.set_joinable("42", False))

    shared = rooms[room_id]["settings"]["share"]
    assert shared["joinable"] is False and shared["open"] is True and shared.get("before") is None
    assert visitor_grant(grants, groups) == before
    for user in ("99", "stranger"):
        with pytest.raises(ApiError) as error:
            asyncio.run(share.set_joinable(user, True))
        assert error.value.status == 404
    asyncio.run(share.close("42"))
    with pytest.raises(ApiError) as error:
        asyncio.run(share.set_joinable("42", True))
    assert error.value.status == 409


def test_a_new_share_opens_the_link_again(ck):
    rooms, _, _, _ = ck
    room_id = start()
    asyncio.run(share.set_joinable("42", False))
    asyncio.run(share.close("42"))

    start()

    assert rooms[room_id]["settings"]["share"]["joinable"] is True
