import asyncio

import httpx
import pytest
from pydantic import ValidationError

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError
from modeling_api.schemas.group_work import MAX_GROUPS, MAX_MEMBERS, MAX_TASKS, CreateGroupWork
from modeling_api.services import models
from modeling_api.services.collab_kit import group_work, share, store

# Das CK im Speicher aus den Tests des Teilens.
from test_share import ck, deleted, presence, tasks  # noqa: F401

TUTOR = User(id="1", global_role="ADMIN")
COURSE = "Datenbanken WS 26/27"
LANGUAGES = [{"languageId": "serm", "versionId": "s1", "source": "required"}]


def task_of(reference):
    return {
        "title": f"F{reference['taskId']} – Case",
        "contentHtml": f"<p>Case {reference['taskId']}</p>",
        "taskVersion": reference,
        "settings": {"autonomyMode": "free", "connectionPreviewAllowed": None, "evaluationWorkflows": []},
        "workspaceLanguages": LANGUAGES,
    }


@pytest.fixture
def fbs(monkeypatch, ck):
    """Das FBS kennt zwei Konten; die Aufgaben kommen ohne Mongo; Räume und Werkstücke liest der Dienst aus dem CK im Speicher."""
    rooms, _, _, workpieces = ck
    loaded = []

    async def list_rooms():
        return list(rooms.values())

    async def list_workpieces():
        return list(workpieces)

    monkeypatch.setattr(group_work.client, "list_rooms", list_rooms)
    monkeypatch.setattr(group_work.client, "list_workpieces", list_workpieces)

    async def fbs_ids(token):
        return {"malb76": "2254", "bobb12": "17"}

    async def task_for_room(reference):
        loaded.append(reference)
        return task_of(reference)

    monkeypatch.setattr(group_work, "fbs_ids", fbs_ids)
    monkeypatch.setattr(models, "task_for_room", task_for_room)
    return loaded


def ref(number):
    return {"taskId": str(number), "versionId": f"v{number}"}


def test_each_group_gets_a_room_its_group_and_a_model_per_task(ck, fbs, tasks):
    rooms, groups, grants, workpieces = ck
    groups_in = [{"name": "Gruppe 01", "usernames": ["malb76", "bobb12"], "names": {"malb76": "Michael Albach", "bobb12": "Bob Bobby"}, "tasks": [ref(1), ref(2)]}]

    created = asyncio.run(group_work.create(TUTOR, COURSE, groups_in, "token"))

    room_id = created[0]["roomId"]
    assert created == [{"name": "Gruppe 01", "roomId": room_id, "created": True, "addedMembers": ["malb76", "bobb12"], "workpieceIds": ["W1", "W3"], "missing": []}]
    assert rooms[room_id]["name"] == "Gruppe 01"
    assert rooms[room_id]["settings"]["groupWork"]["importedBy"] == "1" and rooms[room_id]["settings"]["groupWork"]["course"] == COURSE
    (group,) = groups.values()
    assert group["members"] == ["2254", "17"]
    # Die Namen aus der Liste je FBS-ID, bis CK die Personen selbst kennt.
    assert group["settings"] == {"groupWork": {"roomId": room_id, "names": {"2254": "Michael Albach", "17": "Bob Bobby"}}}
    assert grants == [{"groupId": group["_id"], "rights": ["see", "speak", "edit"], "anonymous": False, "scope": {"kind": "room", "id": room_id}}]
    # Je Aufgabe wie beim Teilen: Werkstück für Markierungen und Notizen, feste CK-Aufgabe, Modell.
    assert [w["contract"]["format"] for w in workpieces] == [share.TASK_FORMAT, "copilot-cells", share.TASK_FORMAT, "copilot-cells"]
    model = workpieces[1]
    assert model["name"] == "F1 – Case" and model["units"] == group_work.MODEL_UNITS
    assert model["contract"]["languages"] == LANGUAGES
    assert model["contract"]["task"] == {"workpieceId": "W0", "taskId": "T0"}
    assert tasks[0]["detail"]["contentHtml"] == "<p>Case 1</p>" and "workspaceLanguages" not in tasks[0]["detail"]


def test_a_task_is_read_once_for_all_groups(ck, fbs):
    groups_in = [
        {"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]},
        {"name": "Gruppe 02", "usernames": ["bobb12"], "tasks": [ref(1), ref(3)]},
    ]

    created = asyncio.run(group_work.create(TUTOR, COURSE, groups_in, "token"))

    assert [room["name"] for room in created] == ["Gruppe 01", "Gruppe 02"]
    assert fbs == [ref(1), ref(3)]


def test_whoever_the_fbs_does_not_know_stays_out_and_is_listed(ck, fbs):
    _, groups, _, _ = ck
    groups_in = [{"name": "Gruppe 01", "usernames": ["malb76", "nobody", "malb76"], "tasks": [ref(1)]}]

    created = asyncio.run(group_work.create(TUTOR, COURSE, groups_in, "token"))

    assert created[0]["missing"] == ["nobody"]
    assert next(iter(groups.values()))["members"] == ["2254"]


def test_only_moderators_create_group_work(ck, fbs):
    rooms, _, _, _ = ck
    student = User(id="5", global_role="USER")

    with pytest.raises(ApiError) as error:
        asyncio.run(group_work.create(student, COURSE, [{"name": "G", "usernames": [], "tasks": [ref(1)]}], "token"))

    assert error.value.status == 403 and rooms == {}


def test_an_unknown_task_stops_before_anything_is_created(ck, fbs, monkeypatch):
    rooms, _, _, _ = ck

    async def missing(reference):
        raise ApiError(404, "NOT_FOUND", "Not found.")

    monkeypatch.setattr(models, "task_for_room", missing)

    with pytest.raises(ApiError):
        asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "G", "usernames": [], "tasks": [ref(9)]}], "token"))

    assert rooms == {}


def test_group_rooms_are_no_shares(ck, fbs):
    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))

    # Weder der Sweep noch die Suche nach der Share des Hosts finden den Raum.
    assert asyncio.run(store.open_rooms()) == []
    assert asyncio.run(store.find_by_owner("2254")) is None


def fbs_answering(monkeypatch, status, users):
    """Ein FBS, das auf die Nutzerliste mit `status` und `users` antwortet."""
    seen = []

    def handle(request):
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(status, json=users)

    real = httpx.AsyncClient
    monkeypatch.setattr(group_work.httpx, "AsyncClient", lambda **options: real(transport=httpx.MockTransport(handle), **options))
    return seen


def test_the_fbs_list_maps_login_names_to_ids_with_the_tutors_token(monkeypatch):
    seen = fbs_answering(monkeypatch, 200, [{"id": 2254, "username": "malb76"}, {"id": 3, "username": ""}, "broken"])

    assert asyncio.run(group_work.fbs_ids("secret")) == {"malb76": "2254"}
    assert seen == ["Bearer secret"]


def test_an_fbs_that_refuses_the_list_is_a_403(monkeypatch):
    fbs_answering(monkeypatch, 403, {})

    with pytest.raises(ApiError) as error:
        asyncio.run(group_work.fbs_ids("secret"))

    assert error.value.status == 403


def test_a_request_stays_small():
    task = {"taskId": "00000000-0000-0000-0000-000000000001", "versionId": "00000000-0000-0000-0000-000000000002"}
    group = {"name": "G", "usernames": ["a"], "tasks": [task]}
    CreateGroupWork.model_validate({"course": COURSE, "groups": [group] * MAX_GROUPS})

    for too_much in (
        {"course": COURSE, "groups": [group] * (MAX_GROUPS + 1)},
        {"course": COURSE, "groups": [{**group, "tasks": [task] * (MAX_TASKS + 1)}]},
        {"course": COURSE, "groups": [{**group, "usernames": ["a"] * (MAX_MEMBERS + 1)}]},
        {"course": COURSE, "groups": [{**group, "tasks": []}]},
        {"course": " ", "groups": [group]},
        {"groups": [group]},
    ):
        with pytest.raises(ValidationError):
            CreateGroupWork.model_validate(too_much)


def test_importing_the_course_again_adds_only_what_a_room_lacks(ck, fbs):
    rooms, groups, _, workpieces = ck
    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))
    room_id = next(iter(rooms))

    again = asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76", "bobb12"], "tasks": [ref(1), ref(2)]}], "token"))

    assert len(rooms) == 1 and len(groups) == 1
    assert again == [{"name": "Gruppe 01", "roomId": room_id, "created": False, "addedMembers": ["bobb12"], "workpieceIds": ["W3"], "missing": []}]
    assert next(iter(groups.values()))["members"] == ["2254", "17"]
    # Ein Modell für F2 kam dazu, F1 bekam keines mehr.
    assert [w["name"] for w in workpieces if w["contract"]["format"] == "copilot-cells"] == ["F1 – Case", "F2 – Case"]


def test_importing_again_adds_the_names_of_new_members_and_keeps_the_rest(ck, fbs):
    _, groups, _, _ = ck
    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))
    group = next(iter(groups.values()))
    group["settings"]["other"] = {"kept": True}

    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76", "bobb12"], "names": {"bobb12": "Bob Bobby"}, "tasks": [ref(1)]}], "token"))

    assert group["settings"]["groupWork"]["names"] == {"17": "Bob Bobby"}
    assert group["settings"]["other"] == {"kept": True} and group["settings"]["groupWork"]["roomId"] == next(iter(ck[0]))


def test_another_release_of_a_task_gets_no_second_model(ck, fbs):
    _, _, _, workpieces = ck
    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))

    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [{"taskId": "1", "versionId": "v2"}]}], "token"))

    assert len(workpieces) == 2


def test_the_same_group_name_in_another_course_is_another_room(ck, fbs):
    rooms, groups, _, _ = ck
    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))

    again = asyncio.run(group_work.create(TUTOR, "Datenbanken SS 27", [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))

    assert again[0]["created"] is True and len(rooms) == 2 and len(groups) == 2


def test_course_and_group_compare_without_case_and_spaces(ck, fbs):
    rooms, _, _, _ = ck
    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))

    again = asyncio.run(group_work.create(TUTOR, "  datenbanken   ws 26/27 ", [{"name": "gruppe  01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))

    assert again[0]["created"] is False and len(rooms) == 1


def test_the_preview_tells_what_would_happen_and_writes_nothing(ck, fbs):
    rooms, groups, grants, workpieces = ck
    asyncio.run(group_work.create(TUTOR, COURSE, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))
    seen = (len(rooms), len(groups), len(grants), len(workpieces))
    room_id = next(iter(rooms))

    planned = asyncio.run(
        group_work.plan(
            TUTOR,
            COURSE,
            [
                {"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]},
                {"name": "Gruppe 02", "usernames": ["bobb12", "nobody"], "tasks": [ref(2)]},
            ],
            "token",
        )
    )

    assert (len(rooms), len(groups), len(grants), len(workpieces)) == seen
    up_to_date, new = planned
    assert (up_to_date["roomId"], up_to_date["newMembers"], up_to_date["newTasks"]) == (room_id, [], [])
    assert (new["roomId"], new["newMembers"], new["newTasks"], new["missing"]) == (None, ["bobb12"], [ref(2)], ["nobody"])


def test_the_preview_route_answers_with_the_plan(ck, fbs, monkeypatch):
    from fastapi.testclient import TestClient

    from modeling_api.core.auth import get_user
    from modeling_api.main import app

    monkeypatch.setitem(app.dependency_overrides, get_user, lambda: TUTOR)
    body = {"course": COURSE, "groups": [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [{"taskId": "00000000-0000-0000-0000-000000000001", "versionId": "00000000-0000-0000-0000-000000000002"}]}]}

    response = TestClient(app).post("/v1/group-work/preview", json=body, headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json() == {"rooms": [{"name": "Gruppe 01", "roomId": None, "newMembers": ["malb76"], "newTasks": body["groups"][0]["tasks"], "missing": []}]}
