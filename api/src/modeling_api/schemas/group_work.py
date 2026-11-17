"""Schemas for group work: rooms from a list of participants."""

from typing import Annotated

from pydantic import Field

from modeling_api.schemas.common import ApiSchema, Name, TaskVersionReference

Username = Annotated[str, Field(min_length=1, max_length=128, description="Login name in the Feedbacksystem.")]

# Each group costs three calls to CK and each task three more; this keeps a request short.
# The browser sends more groups in several requests, one after another.
MAX_GROUPS = 10
MAX_TASKS = 10
MAX_MEMBERS = 50


class GroupWorkGroup(ApiSchema):
    """One group of the list: it becomes a room with one model per task."""

    name: Name = Field(description="Name of the room and of its group.")
    usernames: list[Username] = Field(max_length=MAX_MEMBERS, description="Members by their login name.")
    names: dict[Username, Annotated[str, Field(max_length=256)]] = Field(
        default_factory=dict,
        max_length=MAX_MEMBERS,
        description="Display name per login name from the list; shown until CK knows the person itself.",
    )
    tasks: list[TaskVersionReference] = Field(min_length=1, max_length=MAX_TASKS, description="Released tasks, one model each.")


class CreateGroupWork(ApiSchema):
    """The groups of a course that a tutor creates or extends at once; more go in further requests."""

    course: Name = Field(
        description="Course and semester, e.g. 'Datenbanken WS 26/27'; a group of the same name in the same course is the same room."
    )
    groups: list[GroupWorkGroup] = Field(min_length=1, max_length=MAX_GROUPS)


class PlannedGroupRoom(ApiSchema):
    """What an import would do with a group: a new room, or what the existing one lacks."""

    name: str
    room_id: str | None = Field(description="The room of this group in the course, if there is one already.")
    new_members: list[str] = Field(description="Login names that would join the group.")
    new_tasks: list[TaskVersionReference] = Field(description="Tasks the room has no model for yet.")
    missing: list[str] = Field(description="Login names without an account in the Feedbacksystem; they stay out.")


class GroupWorkPlan(ApiSchema):
    rooms: list[PlannedGroupRoom]


class CreatedGroupRoom(ApiSchema):
    """A created or extended room, and who was not found in the Feedbacksystem."""

    name: str
    room_id: str
    created: bool = Field(description="Whether the room is new; otherwise it existed and got what it lacked.")
    added_members: list[str] = Field(description="Login names that joined the group.")
    workpiece_ids: list[str] = Field(description="The models created, one per new task.")
    missing: list[str] = Field(description="Login names without an account in the Feedbacksystem; they are not in the room.")


class GroupWorkResult(ApiSchema):
    rooms: list[CreatedGroupRoom]


class ArchiveGroupWork(ApiSchema):
    """A course whose rooms go into the archive with their groups and models."""

    course: Name = Field(description="The course as given at the import; compared without case and extra spaces.")


class GroupWorkArchived(ApiSchema):
    """What went into the archive and which rooms were left."""

    rooms: int = Field(description="Rooms archived.")
    groups: int = Field(description="Groups archived.")
    workpieces: int = Field(description="Models and tasks archived; one that also lies in a room outside the course stays.")
    failed: list[str] = Field(description="Rooms left live because Collab-Kit refused one of their parts; another call finishes them.")
