"""Schemas für die Gruppenarbeit: Räume aus einer Teilnehmerliste."""

from typing import Annotated

from pydantic import Field

from modeling_api.schemas.common import ApiSchema, Name, TaskVersionReference

Username = Annotated[str, Field(min_length=1, max_length=128, description="Login name in the Feedbacksystem.")]

# Jede Gruppe kostet drei Aufrufe an CK und jede Aufgabe drei weitere; so bleibt eine Anfrage kurz.
# Mehr Gruppen schickt der Browser in mehreren Anfragen nacheinander.
MAX_GROUPS = 10
MAX_TASKS = 10
MAX_MEMBERS = 50


class GroupWorkGroup(ApiSchema):
    """Eine Gruppe der Liste: daraus wird ein Raum mit einem Modell je Aufgabe."""

    name: Name = Field(description="Name of the room and of its group.")
    usernames: list[Username] = Field(max_length=MAX_MEMBERS, description="Members by their login name.")
    tasks: list[TaskVersionReference] = Field(min_length=1, max_length=MAX_TASKS, description="Released tasks, one model each.")


class CreateGroupWork(ApiSchema):
    """Die Gruppen, die ein Tutor auf einmal anlegt; mehr gehen in weiteren Anfragen."""

    groups: list[GroupWorkGroup] = Field(min_length=1, max_length=MAX_GROUPS)


class CreatedGroupRoom(ApiSchema):
    """Ein angelegter Raum und wer im Feedbacksystem nicht gefunden wurde."""

    name: str
    room_id: str
    workpiece_ids: list[str] = Field(description="The model of each task, in the order of the request.")
    missing: list[str] = Field(description="Login names without an account in the Feedbacksystem; they are not in the room.")


class GroupWorkResult(ApiSchema):
    rooms: list[CreatedGroupRoom]
