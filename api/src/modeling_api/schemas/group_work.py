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
    names: dict[Username, Annotated[str, Field(max_length=256)]] = Field(
        default_factory=dict,
        max_length=MAX_MEMBERS,
        description="Display name per login name from the list; shown until CK knows the person itself.",
    )
    tasks: list[TaskVersionReference] = Field(min_length=1, max_length=MAX_TASKS, description="Released tasks, one model each.")


class CreateGroupWork(ApiSchema):
    """Die Gruppen eines Kurses, die ein Tutor auf einmal anlegt oder ergänzt; mehr gehen in weiteren Anfragen."""

    course: Name = Field(
        description="Course and semester, e.g. 'Datenbanken WS 26/27'; a group of the same name in the same course is the same room."
    )
    groups: list[GroupWorkGroup] = Field(min_length=1, max_length=MAX_GROUPS)


class PlannedGroupRoom(ApiSchema):
    """Was ein Import mit einer Gruppe täte: neuer Raum, oder was dem vorhandenen fehlt."""

    name: str
    room_id: str | None = Field(description="The room of this group in the course, if there is one already.")
    new_members: list[str] = Field(description="Login names that would join the group.")
    new_tasks: list[TaskVersionReference] = Field(description="Tasks the room has no model for yet.")
    missing: list[str] = Field(description="Login names without an account in the Feedbacksystem; they stay out.")


class GroupWorkPlan(ApiSchema):
    rooms: list[PlannedGroupRoom]


class CreatedGroupRoom(ApiSchema):
    """Ein angelegter oder ergänzter Raum und wer im Feedbacksystem nicht gefunden wurde."""

    name: str
    room_id: str
    created: bool = Field(description="Whether the room is new; otherwise it existed and got what it lacked.")
    added_members: list[str] = Field(description="Login names that joined the group.")
    workpiece_ids: list[str] = Field(description="The models created, one per new task.")
    missing: list[str] = Field(description="Login names without an account in the Feedbacksystem; they are not in the room.")


class GroupWorkResult(ApiSchema):
    rooms: list[CreatedGroupRoom]
