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
def fbs(monkeypatch):
    """Das FBS kennt zwei Konten; die Aufgaben kommen ohne Mongo."""
    loaded = []

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
    groups_in = [{"name": "Gruppe 01", "usernames": ["malb76", "bobb12"], "tasks": [ref(1), ref(2)]}]

    created = asyncio.run(group_work.create(TUTOR, groups_in, "token"))

    room_id = created[0]["roomId"]
    assert created == [{"name": "Gruppe 01", "roomId": room_id, "workpieceIds": ["W1", "W3"], "missing": []}]
    assert rooms[room_id]["name"] == "Gruppe 01" and rooms[room_id]["settings"]["groupWork"]["importedBy"] == "1"
    (group,) = groups.values()
    assert group["members"] == ["2254", "17"] and group["settings"] == {"groupWork": {"roomId": room_id}}
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

    created = asyncio.run(group_work.create(TUTOR, groups_in, "token"))

    assert [room["name"] for room in created] == ["Gruppe 01", "Gruppe 02"]
    assert fbs == [ref(1), ref(3)]


def test_whoever_the_fbs_does_not_know_stays_out_and_is_listed(ck, fbs):
    _, groups, _, _ = ck
    groups_in = [{"name": "Gruppe 01", "usernames": ["malb76", "nobody", "malb76"], "tasks": [ref(1)]}]

    created = asyncio.run(group_work.create(TUTOR, groups_in, "token"))

    assert created[0]["missing"] == ["nobody"]
    assert next(iter(groups.values()))["members"] == ["2254"]


def test_only_moderators_create_group_work(ck, fbs):
    rooms, _, _, _ = ck
    student = User(id="5", global_role="USER")

    with pytest.raises(ApiError) as error:
        asyncio.run(group_work.create(student, [{"name": "G", "usernames": [], "tasks": [ref(1)]}], "token"))

    assert error.value.status == 403 and rooms == {}


def test_an_unknown_task_stops_before_anything_is_created(ck, fbs, monkeypatch):
    rooms, _, _, _ = ck

    async def missing(reference):
        raise ApiError(404, "NOT_FOUND", "Not found.")

    monkeypatch.setattr(models, "task_for_room", missing)

    with pytest.raises(ApiError):
        asyncio.run(group_work.create(TUTOR, [{"name": "G", "usernames": [], "tasks": [ref(9)]}], "token"))

    assert rooms == {}


def test_group_rooms_are_no_shares(ck, fbs):
    asyncio.run(group_work.create(TUTOR, [{"name": "Gruppe 01", "usernames": ["malb76"], "tasks": [ref(1)]}], "token"))

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
    CreateGroupWork.model_validate({"groups": [group] * MAX_GROUPS})

    for too_much in (
        {"groups": [group] * (MAX_GROUPS + 1)},
        {"groups": [{**group, "tasks": [task] * (MAX_TASKS + 1)}]},
        {"groups": [{**group, "usernames": ["a"] * (MAX_MEMBERS + 1)}]},
        {"groups": [{**group, "tasks": []}]},
    ):
        with pytest.raises(ValidationError):
            CreateGroupWork.model_validate(too_much)
