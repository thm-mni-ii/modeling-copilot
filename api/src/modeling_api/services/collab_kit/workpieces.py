"""Werkstücke des Copilots in Collab-Kit (CK): ihre Contracts und das Anlegen eines Modells samt Aufgabe.

Genutzt beim Teilen (share.py) und bei der Gruppenarbeit (group_work.py). Dieselben Werte liest und baut
das Web in web/src/collab/converters/task/taskLink.ts und web/src/collab/storage/workpiece.ts.
"""

from typing import Any

from modeling_api.services.collab_kit import client

TOOL = "modeling-copilot"
# Das Werkstück der Aufgabe und die Map seiner Markierungen, wie das Web sie liest.
TASK_FORMAT = "copilot-task"
MARKS_MAP = "marks"
# Ein Modell hält seine Zellen in einer Map.
MODEL_UNITS = [{"path": ["cells"]}]


def model_contract(languages: list[dict[str, Any]]) -> dict[str, Any]:
    """Der Contract eines Modells, wie ihn der Browser baut (`newWorkpiece`), mit den Sprachen der Aufgabe als Start."""
    return {"tool": TOOL, "format": "copilot-cells", "version": 1, "languages": languages, "history": "none"}


async def create_model_workpiece(
    room_id: str,
    name: str,
    contract: dict[str, Any],
    units: list[dict[str, Any]],
    task: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    """Legt ein Modell im Raum an, mit `task` (Titel, Text, Release) samt fester CK-Aufgabe und
    einem Werkstück für Markierungen und Notizen; gibt das Modell und dieses Werkstück zurück."""
    task_workpiece_id = None
    if task is not None:
        # Die Aufgabe zuerst, denn der Contract des Modells lässt sich nach dem Anlegen nicht mehr ändern.
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
