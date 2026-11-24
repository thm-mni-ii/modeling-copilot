"""Copilot workpieces in Collab-Kit (CK): their contracts and creating a model together with its task.

Used when sharing (share.py) and for group work (group_work.py). The web reads and builds the same values
in web/src/collab/converters/task/taskLink.ts and web/src/collab/storage/workpiece.ts.
"""

from typing import Any

from modeling_api.services.collab_kit import client

TOOL = "modeling-copilot"
# The workpiece of the task and the map of its marks, as the web reads them.
TASK_FORMAT = "copilot-task"
MARKS_MAP = "marks"
# A model keeps its cells in one map.
MODEL_UNITS = [{"path": ["cells"]}]


def model_contract(languages: list[dict[str, Any]]) -> dict[str, Any]:
    """The contract of a model as the browser builds it (`newWorkpiece`), with the languages of the task to start with."""
    return {"tool": TOOL, "format": "copilot-cells", "version": 1, "languages": languages, "history": "none"}


async def create_model_workpiece(
    room_id: str,
    name: str,
    contract: dict[str, Any],
    units: list[dict[str, Any]],
    task: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    """Creates a model in the room; with `task` (title, text, release) also a fixed CK task and
    a workpiece for marks and notes; returns the model and that workpiece."""
    task_workpiece_id = None
    if task is not None:
        # The task first, because the contract of the model cannot be changed once created.
        task_workpiece = await client.create_workpiece(
            {
                "name": f"{name} – Task",
                "roomId": room_id,
                "contract": {"tool": TOOL, "format": TASK_FORMAT, "version": 1, "taskVersion": task["taskVersion"]},
                "units": [{"path": [MARKS_MAP]}],
            }
        )
        task_workpiece_id = task_workpiece["_id"]
        ck_task = await client.create_task(
            {
                "kind": "assignment",
                "title": task["title"],
                "state": "open",
                "anchor": {"kind": "workpiece", "id": task_workpiece_id},
                "detail": {
                    "contentHtml": task["contentHtml"],
                    "taskVersion": task["taskVersion"],
                    **({"settings": task["settings"]} if "settings" in task else {}),
                },
            }
        )
        contract = {**contract, "task": {"workpieceId": task_workpiece_id, "taskId": ck_task["_id"]}}
    workpiece = await client.create_workpiece(
        {"name": name, "roomId": room_id, "contract": contract, "units": units}
    )
    return workpiece["_id"], task_workpiece_id
