import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services import models
from modeling_api.services.collab_kit import archive, client, share, store, sweep

ARGS = dict(name="Model", contract={"tool": "x"}, units=[{"path": ["cells"]}])


@pytest.fixture
def tasks() -> list[dict]:
    """The tasks that the in-memory CK has created."""
    return []


@pytest.fixture
def presence() -> list[dict]:
    """Who the in-memory CK says is connected right now."""
    return []


@pytest.fixture
def deleted() -> list[tuple]:
    """Welche Arbeitskopien gelöscht wurden, als (Raum, Besitzer, ausgenommen, behaltenes Workpiece)."""
    return []


@pytest.fixture
def sharing() -> dict:
    """Was der Bereich sharing der Collab-Einstellungen in CK enthält; leer gelten die Standards."""
    return {}


@pytest.fixture
def archiving() -> dict:
    """Was der Bereich archive der Collab-Einstellungen in CK enthält; leer ist alles aus."""
    return {}


@pytest.fixture
def archived() -> list[dict]:
    """Was CK archiviert hat, wie ein Eintrag im Archiv: Werkstück, Grund und die Räume, in denen es lag."""
    return []


@pytest.fixture
def archive_answers() -> dict:
    """Was CK beim Archivieren eines Werkstücks statt Erfolg antwortet, als Status; None heißt, CK ist nicht erreichbar."""
    return {}


@pytest.fixture
def activity() -> dict:
    """Die Spuren je Werkstück, wie CK sie für die letzte Aktivität liefert; ohne Eintrag keine."""
    return {}


@pytest.fixture
def ck(monkeypatch, tasks, presence, deleted, sharing, archiving, archived, archive_answers, activity):
    """A small in-memory CK: creates, reads and changes the settings, remembers grants and workpieces."""
    rooms: dict[str, dict] = {}
    groups: dict[str, dict] = {}
    grants: list[dict] = []
    workpieces: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        body = json.loads(request.content) if request.content else {}
        if (method, path) == ("POST", "/tasks"):
            tasks.append({"_id": f"T{len(tasks)}", **body})
            return httpx.Response(201, json=tasks[-1])
        if (method, path) == ("POST", "/rooms"):
            room = {"_id": f"R{len(rooms)}", "createdBy": "service-modeling-copilot", "workpieces": [], **body}
            rooms[room["_id"]] = room
            return httpx.Response(201, json=room)
        if (method, path) == ("POST", "/groups"):
            group = {"_id": f"G{len(groups)}", "createdAt": f"2026-01-01T00:00:{len(groups):02d}Z", **body}
            groups[group["_id"]] = group
            return httpx.Response(201, json=group)
        if (method, path) == ("PUT", "/grants"):
            # As in CK: one grant per group and place, a new one replaces the old one.
            grants[:] = [g for g in grants if (g["groupId"], g.get("scope")) != (body["groupId"], body.get("scope"))]
            grants.append(body)
            return httpx.Response(200, json=body)
        if (method, path) == ("GET", "/grants"):
            at = request.url.params["scopeId"]
            return httpx.Response(200, json=[g for g in grants if g.get("scope", {}).get("id") == at])
        if (method, path) == ("POST", "/workpieces"):
            workpieces.append({"_id": f"W{len(workpieces)}", "createdBy": "service-modeling-copilot", "createdAt": "2026-01-01T00:00:00Z", **body})
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
        if (method, path) == ("GET", "/settings/sharing"):
            return httpx.Response(200, json=sharing)
        if (method, path) == ("GET", "/settings/archive"):
            return httpx.Response(200, json=archiving)
        if (method, path) == ("GET", "/me/rooms"):
            return httpx.Response(200, json=list(rooms.values()))
        if (method, path) == ("GET", "/workpieces"):
            # Archiviertes ist nicht mehr live.
            gone = {entry["_id"] for entry in archived}
            return httpx.Response(200, json=[workpiece for workpiece in workpieces if workpiece["_id"] not in gone])
        if method == "GET" and path.endswith("/activity"):
            return httpx.Response(200, json=activity.get(path.split("/")[2], []))
        if method == "POST" and path.endswith("/archive"):
            workpiece_id = path.split("/")[2]
            if workpiece_id in archive_answers:
                if archive_answers[workpiece_id] is None:
                    raise httpx.ConnectError("Collab-Kit is down.")
                return httpx.Response(archive_answers[workpiece_id], json={"error": "refused"})
            archived.append({"_id": workpiece_id, "reason": body.get("reason"), "rooms": [r for r, room in rooms.items() if workpiece_id in room["workpieces"]]})
            return httpx.Response(200, json={"_id": workpiece_id, "kind": "workpiece"})
        if method == "GET" and path.endswith("/presence"):
            return httpx.Response(200, json=presence)
        if (method, path) == ("GET", "/groups"):
            return httpx.Response(200, json=list(groups.values()))
        if method == "POST" and path.endswith("/members"):
            groups[path.split("/")[2]]["members"].append(body["actorId"])
            return httpx.Response(201, json=groups[path.split("/")[2]])
        if method == "GET" and path.startswith("/groups/") and path.split("/")[2] in groups:
            return httpx.Response(200, json=groups[path.split("/")[2]])
        if method == "GET" and path.startswith("/rooms/") and path.split("/")[2] in rooms:
            return httpx.Response(200, json=rooms[path.split("/")[2]])
        if method == "PATCH" and path.startswith("/groups/"):
            groups[path.split("/")[2]]["settings"] = body["settings"]
            return httpx.Response(200, json=groups[path.split("/")[2]])
        if method == "PATCH" and path.startswith("/rooms/"):
            rooms[path.split("/")[2]]["settings"] = body["settings"]
            return httpx.Response(200, json=rooms[path.split("/")[2]])
        return httpx.Response(404, json={"error": "unknown"})

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(handle))
    monkeypatch.setattr(client, "service_token", lambda: "token")

    # Die Tests laufen ohne Mongo: das Löschen der Arbeitskopien merkt sich nur, wonach es gefragt wurde.
    async def delete_room_models(room_id, owner_id=None, *, except_owners=(), keep_workpiece_id=None) -> None:
        deleted.append((room_id, owner_id, sorted(except_owners), keep_workpiece_id))

    monkeypatch.setattr(models, "delete_room_models", delete_room_models)
    sweep._missing.clear()
    sweep._host_missing.clear()
    monkeypatch.setattr(sweep, "_sleep_seconds", sweep.SWEEP_SECONDS)
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


TASK = {"title": "Orders", "contentHtml": "<p>Each order</p>", "taskVersion": {"taskId": "t", "versionId": "v"}}


def test_sharing_with_the_task_bundles_it_into_the_contract_of_the_model(ck, tasks):
    rooms, _, _, workpieces = ck
    room_id, workpiece_id, created = asyncio.run(
        share.share("42", anonymous=False, edit=True, comment=True, task=TASK, **ARGS)
    )

    task_workpiece, model = workpieces
    assert (workpiece_id, created) == (model["_id"], True)
    assert rooms[room_id]["workpieces"] == [task_workpiece["_id"], model["_id"]]
    assert task_workpiece["contract"]["format"] == share.TASK_FORMAT
    assert task_workpiece["units"] == [{"path": [share.MARKS_MAP]}]
    assert tasks[0]["anchor"] == {"kind": "workpiece", "id": task_workpiece["_id"]}
    assert tasks[0]["detail"] == {"contentHtml": "<p>Each order</p>", "taskVersion": TASK["taskVersion"]}
    assert model["contract"] == {"tool": "x", "task": {"workpieceId": task_workpiece["_id"], "taskId": "T0"}}
    assert rooms[room_id]["settings"]["share"]["taskWorkpieceId"] == task_workpiece["_id"]


def test_sharing_without_the_task_leaves_the_model_alone(ck, tasks):
    rooms, _, _, workpieces = ck
    asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, **ARGS))
    assert tasks == [] and len(workpieces) == 1 and "task" not in workpieces[0]["contract"]
    assert rooms["R0"]["settings"]["share"]["taskWorkpieceId"] is None


def members_of(groups, role):
    return next(g for g in groups.values() if g["settings"]["share"]["role"] == role)["members"]


def test_a_visitor_joins_once_and_the_host_stays_out_of_the_visitors(ck):
    _, groups, _, _ = ck
    room_id, workpiece_id, _ = asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, **ARGS))

    assert asyncio.run(share.join("99", room_id)) == (workpiece_id, "visitor", "42")
    assert asyncio.run(share.join("99", room_id)) == (workpiece_id, "visitor", "42")
    assert asyncio.run(share.join("42", room_id)) == (workpiece_id, "host", "42")
    assert members_of(groups, "visitors") == ["99"]


def test_a_visitor_can_leave_at_any_time_and_leaving_again_or_from_a_missing_room_changes_nothing(ck, deleted):
    _, groups, _, _ = ck
    room_id = start()
    asyncio.run(share.join("99", room_id))
    asyncio.run(share.join("98", room_id))

    asyncio.run(share.leave("99", room_id))
    asyncio.run(share.leave("99", room_id))
    asyncio.run(share.leave("42", room_id))
    asyncio.run(share.leave("99", "does-not-exist"))
    assert members_of(groups, "visitors") == ["98"] and members_of(groups, "hosts") == ["42"]
    # Die Share räumt Kopien älterer Workpieces auf; danach geht die des Visitors jedes Mal, auch ohne Raum,
    # die des Hosts bleibt bis zum Schließen.
    assert deleted == [(room_id, None, [], "W0"), (room_id, "99", [], None), (room_id, "99", [], None), ("does-not-exist", "99", [], None)]

    # Also when the host has locked and closed the room, the visitor can still go.
    asyncio.run(share.set_open("42", False))
    asyncio.run(share.leave("98", room_id))
    assert members_of(groups, "visitors") == []


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


def test_closing_takes_visitors_and_workpiece_out_but_keeps_room_and_groups(ck, presence, deleted):
    rooms, groups, _, _ = ck
    room_id = start()
    asyncio.run(share.join("99", room_id))
    asyncio.run(share.join("98", room_id))
    asyncio.run(share.set_open("42", False))
    # Der Host und 99 sind noch verbunden, 98 ist schon weg.
    presence[:] = [{"workpieceId": "W0", "actorId": actor, "connections": 1} for actor in ("42", "99")]

    asyncio.run(share.close("42"))

    assert members_of(groups, "visitors") == [] and members_of(groups, "hosts") == ["42"]
    assert rooms[room_id]["workpieces"] == []
    shared = rooms[room_id]["settings"]["share"]
    assert (shared["open"], shared["workpieceId"], shared["before"]) == (False, None, None)
    assert len(rooms) == 1 and len(groups) == 2
    # Die Kopien gehen mit, außer der von 99, der sie noch offen hat und sie mit seinem `leave` löscht.
    assert deleted[1:] == [(room_id, None, ["99"], None)]
    with pytest.raises(ApiError):
        asyncio.run(share.join("99", room_id))


def test_closing_takes_the_task_out_of_the_room_as_well(ck):
    rooms, _, _, _ = ck
    asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, task=TASK, **ARGS))

    asyncio.run(share.close("42"))

    shared = rooms["R0"]["settings"]["share"]
    assert rooms["R0"]["workpieces"] == [] and (shared["workpieceId"], shared["taskWorkpieceId"]) == (None, None)


def test_closing_again_changes_nothing_and_a_new_share_reuses_the_room(ck):
    rooms, _, _, _ = ck
    start()
    asyncio.run(share.close("42"))
    asyncio.run(share.close("42"))
    assert start() == "R0" and len(rooms) == 1


# Beide Schalter des Bereichs archive an.
ARCHIVE_ON = dict(enabled=True, archiveOnShareClose=True)


def test_closing_archives_model_and_task_once_they_are_out_of_the_room_when_the_collab_settings_say_so(ck, archiving, archived):
    rooms, _, _, _ = ck
    archiving.update(ARCHIVE_ON)
    asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, task=TASK, **ARGS))

    asyncio.run(share.close("42"))

    # W1 ist das Modell, W0 die Aufgabe; ohne Raum archiviert, kommen sie zurückgeholt nicht in den Raum des Hosts.
    assert archived == [{"_id": workpiece_id, "reason": "share closed", "rooms": []} for workpiece_id in ("W1", "W0")]
    assert rooms["R0"]["workpieces"] == [] and rooms["R0"]["settings"]["share"]["workpieceId"] is None


def test_closing_archives_nothing_by_default_or_with_only_one_switch(ck, archiving, archived):
    # Nie gesetzt, nur einer der beiden Schalter, ein Text statt eines Wahrheitswerts.
    for values in ({}, dict(enabled=True), dict(archiveOnShareClose=True), dict(enabled="true", archiveOnShareClose=True)):
        archiving.clear()
        archiving.update(values)
        start()
        asyncio.run(share.close("42"))
    assert archived == []


@pytest.mark.parametrize("answer", [409, 500, None])
def test_closing_ends_the_share_even_when_collab_kit_refuses_fails_or_is_down_while_archiving(ck, archiving, archived, archive_answers, answer):
    rooms, groups, _, _ = ck
    archiving.update(ARCHIVE_ON)
    room_id = asyncio.run(share.share("42", anonymous=False, edit=True, comment=True, task=TASK, **ARGS))[0]
    asyncio.run(share.join("99", room_id))
    # 409, solange CK das Modell verschiebt, 500 für einen Fehler in CK, None für ein CK, das nicht antwortet.
    archive_answers["W1"] = answer

    asyncio.run(share.close("42"))

    shared = rooms[room_id]["settings"]["share"]
    assert (shared["open"], shared["workpieceId"], shared["taskWorkpieceId"]) == (False, None, None)
    assert rooms[room_id]["workpieces"] == [] and members_of(groups, "visitors") == []
    # Das Modell bleibt ohne Raum liegen, die Aufgabe geht trotzdem ins Archiv.
    assert [entry["_id"] for entry in archived] == ["W0"]


def test_unreadable_archive_settings_count_as_off(ck, monkeypatch, archiving, archived):
    archiving.update(ARCHIVE_ON, archiveUnusedAfterDays=30)
    start()

    async def failing(key):
        raise ApiError(503, "CK_UNAVAILABLE", "Collab-Kit is currently unavailable.")

    monkeypatch.setattr(client, "get_settings", failing)
    asyncio.run(share.close("42"))
    assert asyncio.run(archive.archive_unused(now=LATER)) == 0
    assert archived == []


# Archiv an, Frist 30 Tage; „jetzt“ liegt 40 Tage nach dem 1. Januar, an dem die CK im Speicher alles anlegt.
UNUSED_ON = dict(enabled=True, archiveUnusedAfterDays=30)
LATER = datetime(2026, 2, 10, tzinfo=timezone.utc)


def test_unused_workpieces_of_ended_shares_go_to_the_archive_and_the_rest_stays(ck, archiving, archived, activity):
    _, _, _, workpieces = ck
    archiving.update(UNUSED_ON)
    # W0 und W1 aus beendeten Shares ohne Raum, W1 vor zehn Tagen noch benutzt; W2 gehört zur laufenden Share im Raum.
    for _ in range(2):
        start()
        asyncio.run(share.close("42"))
    activity["W1"] = [{"actorId": "42", "at": "2026-01-31T12:00:00Z", "kind": "updated"}]
    start()
    # W3 hat eine Person ohne Raum angelegt.
    workpieces.append({"_id": "W3", "createdBy": "42", "createdAt": "2026-01-01T00:00:00Z"})

    assert asyncio.run(archive.archive_unused(now=LATER)) == 1
    assert archived == [{"_id": "W0", "reason": "unused for 30 days", "rooms": []}]


def test_nothing_unused_is_archived_by_default_without_the_archive_or_with_a_period_out_of_bounds(ck, archiving, archived):
    start()
    asyncio.run(share.close("42"))
    # Nie gesetzt, ohne Archiv, ohne Frist, 0 für nie, zu lang, ein Wahrheitswert statt einer Zahl.
    for values in ({}, dict(archiveUnusedAfterDays=30), dict(enabled=True), dict(enabled=True, archiveUnusedAfterDays=0), dict(enabled=True, archiveUnusedAfterDays=400), dict(enabled=True, archiveUnusedAfterDays=True)):
        archiving.clear()
        archiving.update(values)
        assert asyncio.run(archive.archive_unused(now=LATER)) == 0
    assert archived == []


def test_a_refused_workpiece_waits_for_the_next_round_and_the_others_still_go(ck, archiving, archived, archive_answers):
    archiving.update(UNUSED_ON)
    for _ in range(2):
        start()
        asyncio.run(share.close("42"))
    archive_answers["W0"] = 409

    assert asyncio.run(archive.archive_unused(now=LATER)) == 1
    del archive_answers["W0"]
    # W1 ist schon im Archiv und kommt nicht noch einmal.
    assert asyncio.run(archive.archive_unused(now=LATER)) == 1
    assert [entry["_id"] for entry in archived] == ["W1", "W0"]


def test_without_sharing_on_the_server_the_job_ends(monkeypatch):
    async def disabled(key):
        raise ApiError(503, "SHARING_DISABLED", "Sharing is not configured on this server.")

    monkeypatch.setattr(client, "get_settings", disabled)
    asyncio.run(archive._run())
    assert archive._task is None


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


def test_a_visitor_who_stays_away_is_taken_out_after_the_grace_period_and_one_who_returns_keeps_the_place(ck, presence, deleted):
    _, groups, _, _ = ck
    room_id = start()
    asyncio.run(share.join("99", room_id))
    asyncio.run(share.join("98", room_id))
    # The host is there throughout; this test is about the visitors.
    here = lambda *actors: presence.__init__([{"workpieceId": "W0", "actorId": a, "connections": 1} for a in ("42", *actors)])

    # Only the host is connected yet: the time starts, nobody is taken out.
    here()
    assert asyncio.run(sweep.sweep_once(now=0)) == 1
    assert members_of(groups, "visitors") == ["99", "98"]

    # 98 comes back in time and loses the time; 99 stays away.
    here("98")
    asyncio.run(sweep.sweep_once(now=sweep.VISITOR_GRACE_SECONDS - 1))
    assert members_of(groups, "visitors") == ["99", "98"]
    asyncio.run(sweep.sweep_once(now=sweep.VISITOR_GRACE_SECONDS))
    assert members_of(groups, "visitors") == ["98"]
    assert deleted[1:] == [(room_id, "99", [], None)]

    # The host is no visitor and is never touched; 98 may be gone for a shorter time again.
    here()
    asyncio.run(sweep.sweep_once(now=sweep.VISITOR_GRACE_SECONDS + 10))
    asyncio.run(sweep.sweep_once(now=sweep.VISITOR_GRACE_SECONDS + 10 + sweep.VISITOR_GRACE_SECONDS - 1))
    assert members_of(groups, "visitors") == ["98"] and members_of(groups, "hosts") == ["42"]


def test_the_grace_period_of_a_visitor_comes_from_the_collab_settings(ck, presence, sharing):
    _, groups, _, _ = ck
    room_id = start()
    asyncio.run(share.join("99", room_id))
    # Nur der Host ist da; 99 bleibt weg und fliegt nach 60 s statt nach dem Standard von 120 s.
    presence[:] = [{"workpieceId": "W0", "actorId": "42", "connections": 1}]
    sharing["visitorGraceSeconds"] = 60
    asyncio.run(sweep.sweep_once(now=0))
    asyncio.run(sweep.sweep_once(now=59))
    assert members_of(groups, "visitors") == ["99"]
    asyncio.run(sweep.sweep_once(now=60))
    assert members_of(groups, "visitors") == []


def test_a_time_out_of_bounds_of_another_type_or_unreadable_counts_as_its_default(ck, monkeypatch, sharing):
    defaults = {"sweepSeconds": 30, "visitorGraceSeconds": 120, "hostGraceSeconds": 120, "hostEndSeconds": 300}
    # Zu kurz, ein Wahrheitswert statt einer Zahl, eine Zahl als Text und zu lang.
    sharing.update(visitorGraceSeconds=5, hostGraceSeconds=True, hostEndSeconds="600", sweepSeconds=500)
    assert asyncio.run(sweep._times()) == defaults

    async def failing(key):
        raise ApiError(503, "CK_UNAVAILABLE", "Collab-Kit is currently unavailable.")

    monkeypatch.setattr(client, "get_settings", failing)
    assert asyncio.run(sweep._times()) == defaults


def test_the_sweep_sleeps_between_two_rounds_as_long_as_the_collab_settings_say(ck, sharing):
    asyncio.run(share.join("99", start()))
    sharing["sweepSeconds"] = 15
    asyncio.run(sweep.sweep_once(now=0))
    assert sweep._sleep_seconds == 15


def test_no_visitor_is_taken_out_while_collab_kit_does_not_answer_and_a_room_without_share_is_no_work(ck):
    _, groups, _, _ = ck
    assert asyncio.run(sweep.sweep_once(now=0)) == 0
    room_id = start()
    asyncio.run(share.join("99", room_id))
    asyncio.run(sweep.sweep_once(now=0))
    assert sweep._missing == {(room_id, "99"): 0}

    async def failing(room_id):
        raise ApiError(503, "CK_UNAVAILABLE", "Collab-Kit is currently unavailable.")

    client.room_presence, original = failing, client.room_presence
    try:
        asyncio.run(sweep.sweep_once(now=sweep.VISITOR_GRACE_SECONDS * 5))
    finally:
        client.room_presence = original
    assert members_of(groups, "visitors") == ["99"] and sweep._missing == {}


def test_a_host_who_stays_away_locks_the_room_and_is_never_locked_out_again_when_back(ck, presence):
    rooms, groups, grants, _ = ck
    room_id = start()
    asyncio.run(share.join("99", room_id))
    presence.append({"workpieceId": "W0", "actorId": "99", "connections": 1})
    shared = lambda: rooms[room_id]["settings"]["share"]

    # The host is missing: the time starts, nothing happens before the grace period is over.
    asyncio.run(sweep.sweep_once(now=0))
    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS - 1))
    assert shared()["open"] is True and not shared().get("autoLocked")

    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS))
    assert (shared()["open"], shared()["autoLocked"]) == (False, True)
    assert visitor_grant(grants, groups)["rights"] == ["see", "speak"]
    with pytest.raises(ApiError):
        asyncio.run(share.join("98", room_id))

    # The host is back: the room opens again and the visitors get what they had.
    presence.append({"workpieceId": "W0", "actorId": "42", "connections": 1})
    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS + 30))
    assert (shared()["open"], shared()["autoLocked"], shared()["before"]) == (True, False, None)
    assert visitor_grant(grants, groups)["rights"] == ["see", "speak", "edit"]


def test_the_sweep_never_opens_a_lock_of_the_host_and_never_locks_a_locked_room_again(ck, presence):
    rooms, groups, grants, _ = ck
    room_id = start()
    asyncio.run(share.set_open("42", False))
    shared = lambda: rooms[room_id]["settings"]["share"]
    before = shared()["before"]

    # Host away past the grace period in a room the host has locked: nothing changes.
    asyncio.run(sweep.sweep_once(now=0))
    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS * 3))
    assert (shared()["open"], shared().get("autoLocked"), shared()["before"]) == (False, False, before)

    # Host back, still in their own dialog: the sweep leaves the room locked.
    presence.append({"workpieceId": "W0", "actorId": "42", "connections": 1})
    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS * 3 + 30))
    assert shared()["open"] is False

    # A lock of the host replaces one of the sweep, so the sweep does not open it either.
    presence.clear()
    asyncio.run(sweep.sweep_once(now=1000))
    asyncio.run(sweep.sweep_once(now=1000 + sweep.HOST_GRACE_SECONDS))
    assert shared()["open"] is False


def test_after_the_end_period_the_visitors_go_but_the_share_stays_for_the_host_and_the_sweep_has_nothing_left_to_do(ck, presence):
    rooms, groups, _, _ = ck
    room_id = start()
    asyncio.run(share.join("99", room_id))
    presence.append({"workpieceId": "W0", "actorId": "99", "connections": 1})
    shared = lambda: rooms[room_id]["settings"]["share"]

    # The host is gone, a visitor is still there: the sweep keeps looking after the share.
    assert asyncio.run(sweep.sweep_once(now=0)) == 1
    assert asyncio.run(sweep.sweep_once(now=sweep.HOST_END_SECONDS - 1)) == 1
    assert members_of(groups, "visitors") == ["99"]

    # Past the end period the visitors are out; the share and its workpiece stay, locked by the sweep.
    assert asyncio.run(sweep.sweep_once(now=sweep.HOST_END_SECONDS)) == 0
    assert members_of(groups, "visitors") == []
    assert (shared()["open"], shared()["autoLocked"], shared()["workpieceId"]) == (False, True, "W0")
    assert rooms[room_id]["workpieces"] == ["W0"]


def test_the_orderly_end_of_the_host_clears_every_mark_of_the_sweep_and_the_sweep_never_touches_what_has_ended(ck, presence):
    rooms, _, grants, _ = ck
    room_id = start()
    shared = lambda: rooms[room_id]["settings"]["share"]
    asyncio.run(sweep.sweep_once(now=0))
    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS))
    assert shared()["autoLocked"] is True

    # The host takes over while the sweep's lock is on: the lock is theirs now and stays theirs.
    asyncio.run(share.set_open("42", False))
    assert shared()["autoLocked"] is False
    presence.append({"workpieceId": "W0", "actorId": "42", "connections": 1})
    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS + 30))
    assert shared()["open"] is False

    # Ending the share clears everything; the sweep has nothing to look at, and an old picture of the room does not bring anything back.
    stale = asyncio.run(store.read(room_id)) | {"autoLocked": True, "open": True}
    asyncio.run(share.close("42"))
    assert (shared()["workpieceId"], shared()["before"], shared()["autoLocked"]) == (None, None, False)
    assert asyncio.run(sweep.sweep_once(now=5000)) == 0
    presence.clear()
    times = asyncio.run(sweep._times())
    asyncio.run(sweep._sweep_host(stale, {"42"}, 6000, times))
    asyncio.run(sweep._sweep_host(stale, set(), 6000, times))
    asyncio.run(sweep._sweep_host(stale, set(), 6000 + sweep.HOST_GRACE_SECONDS, times))
    assert (shared()["workpieceId"], shared()["before"], shared()["autoLocked"]) == (None, None, False)
    assert shared()["open"] is False


def test_a_new_share_starts_clean_after_one_the_sweep_had_locked(ck):
    rooms, groups, grants, _ = ck
    room_id = start()
    shared = lambda: rooms[room_id]["settings"]["share"]
    asyncio.run(sweep.sweep_once(now=0))
    asyncio.run(sweep.sweep_once(now=sweep.HOST_GRACE_SECONDS))
    assert (shared()["autoLocked"], shared()["before"] is not None) == (True, True)

    asyncio.run(share.close("42"))
    start(dict(anonymous=False, edit=False, comment=False))
    assert (shared()["open"], shared()["autoLocked"], shared()["before"]) == (True, False, None)
    assert visitor_grant(grants, groups)["rights"] == ["see"]
