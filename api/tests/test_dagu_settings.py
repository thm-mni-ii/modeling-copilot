import asyncio
from datetime import UTC, datetime
import json

from modeling_api.schemas.evaluations import Evaluation
from modeling_api.services import evaluations
from modeling_api.services import dagu


def test_dagu_api_key_is_optional(monkeypatch) -> None:
    monkeypatch.setattr(dagu.settings, "dagu_api_key", "")

    assert dagu._headers() == {}


def test_dagu_api_key_is_sent_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(dagu.settings, "dagu_api_key", "production-secret")

    assert dagu._headers() == {"Authorization": "Bearer production-secret"}


def test_start_workflow_sends_json_encoded_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def request(method: str, path: str, **kwargs: object) -> dict[str, str]:
        captured.update({"method": method, "path": path, **kwargs})
        return {"dagRunId": "run-123"}

    monkeypatch.setattr(dagu, "_request", request)

    run_id = asyncio.run(
        dagu.start_workflow("evaluation", {"task": {"title": "Test"}, "enabled": True})
    )

    assert run_id == "run-123"
    assert captured["method"] == "POST"
    assert captured["path"] == "/dags/evaluation/start"
    assert captured["json"] == {
        "params": json.dumps(
            {"task": '{"title":"Test"}', "enabled": True},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    }


def test_public_evaluation_excludes_persistence_fields() -> None:
    evaluation = evaluations._public_evaluation({
        "_id": "00000000-0000-0000-0000-000000000001",
        "ownerId": "user-1",
        "createdAt": datetime.now(UTC),
        "taskId": "00000000-0000-0000-0000-000000000002",
        "taskVersionId": "00000000-0000-0000-0000-000000000003",
        "modelId": "00000000-0000-0000-0000-000000000004",
        "modelVersionId": "00000000-0000-0000-0000-000000000005",
        "task": {"taskId": "00000000-0000-0000-0000-000000000002", "versionId": "00000000-0000-0000-0000-000000000003"},
        "submission": {"modelId": "00000000-0000-0000-0000-000000000004", "versionId": "00000000-0000-0000-0000-000000000005"},
        "submissionSnapshot": {"data": {}},
        "dagName": "evaluation",
        "dagRunId": "run-1",
        "startedAt": datetime.now(UTC),
        "state": "queued",
        "workflow": {"name": "evaluation"},
    })

    assert "createdAt" not in evaluation
    assert "submissionSnapshot" not in evaluation
    Evaluation.model_validate(evaluation)


def test_dagu_status_labels_and_wrapped_runs_are_normalized() -> None:
    run = evaluations._dag_run({"dagRunDetails": {"statusLabel": "succeeded"}})
    steps = evaluations._run_steps(
        {"nodes": [{"step": {"name": "parse"}, "statusLabel": "running"}]},
        {"steps": [{"id": "parse", "label": "Parse", "status": "pending"}]},
    )

    assert evaluations._state(run["statusLabel"]) == "succeeded"
    assert steps[0]["status"] == "running"
