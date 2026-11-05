from uuid import uuid4

import pytest
from pydantic import ValidationError

from modeling_api.schemas.learning_paths import SaveTemplate
from modeling_api.services.learning_path_store import step_document, template_meta
from modeling_api.services.learning_paths import unlock_status


def task_step(**extra):
    return {
        "id": str(uuid4()),
        "title": "Task",
        "taskVersion": {"taskId": str(uuid4()), "versionId": str(uuid4())},
        **extra,
    }


def test_default_unlock_is_sequence_and_documents_are_split():
    body = SaveTemplate.model_validate(
        {"name": "Path", "steps": [task_step(), task_step()], "published": True}
    )
    assert all(s.unlock.mode == "sequence" for s in body.steps)
    doc = step_document(body.steps[0], "template-1")
    assert doc["templateId"] == "template-1" and doc["kind"] == "task"
    ids = [str(s.id) for s in body.steps]
    assert template_meta(body, ids)["stepIds"] == ids


def test_explicit_condition_on_later_sequential_step_is_a_cycle():
    first, second = task_step(), task_step()
    first["unlock"] = {
        "mode": "all",
        "conditions": [{"type": "completed", "stepId": second["id"]}],
    }
    with pytest.raises(ValidationError):
        SaveTemplate.model_validate({"name": "Path", "steps": [first, second]})


def test_score_condition_is_rejected():
    first, second = task_step(), task_step()
    second["unlock"] = {
        "mode": "all",
        "conditions": [{"type": "score", "stepId": first["id"], "value": 50}],
    }
    with pytest.raises(ValidationError):
        SaveTemplate.model_validate({"name": "Path", "steps": [first, second]})


def test_sequence_skips_archived_and_optional_steps():
    def step(i, **extra):
        return {"id": i, "title": i, "kind": "task", **extra}

    template = {
        "steps": [
            step("a", unlock={"mode": "sequence", "conditions": []}),
            step("b", archivedAt=object(), unlock={"mode": "sequence", "conditions": []}),
            {
                "id": "c",
                "title": "c",
                "kind": "survey",
                "survey": {"required": False},
                "unlock": {"mode": "sequence", "conditions": []},
            },
            step("d", unlock={"mode": "sequence", "conditions": []}),
        ]
    }
    steps = {s["id"]: s for s in template["steps"]}
    assert not unlock_status(steps["d"], template, {}, {}, None)[0]
    done = {"a": {"completedAt": 1}}
    assert unlock_status(steps["d"], template, done, {}, None)[0]
