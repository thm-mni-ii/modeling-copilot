"""Schemas for sharing a model in a Collab-Kit room."""

from typing import Literal

from pydantic import Field

from modeling_api.schemas.common import ApiSchema, JsonObject, Name


class ShareModel(ApiSchema):
    """What the host shares and what the visitors may do; they always see."""

    name: Name = Field(description="Name of the room and of the workpiece in it.")
    contract: JsonObject = Field(description="Contract of the workpiece, as the web app builds it.")
    units: list[JsonObject] = Field(
        max_length=16, description="Units of the workpiece, as the web app builds them."
    )
    anonymous: bool = Field(description="Whether visitors appear anonymously.")
    edit: bool = Field(description="Whether visitors may edit.")
    comment: bool = Field(description="Whether visitors may comment.")


class JoinRoom(ApiSchema):
    """The room a link points to."""

    # Eine ObjectId von CK; sie geht in den Pfad der Anfrage an CK, daher keine andere Form.
    room_id: str = Field(pattern=r"^[0-9a-f]{24}$", description="ID of the room, as in the link.")


class JoinedRoom(ApiSchema):
    """The workpiece to open and how the user takes part."""

    room_id: str
    workpiece_id: str
    role: Literal["host", "visitor"] = Field(description="Whether the user is the host of the room.")
    host_id: str = Field(description="The ID of the host, so visitors can tell whose cursor is whose.")


class SetOpen(ApiSchema):
    """Whether the host's room takes part again or is locked."""

    open: bool = Field(
        description="False locks the room while the host leaves, true opens it again after a cancel."
    )


class SetJoinable(ApiSchema):
    """Whether new visitors may still join through the link."""

    joinable: bool = Field(
        description="False closes the link for new visitors; those already in stay."
    )


class SharedRoom(ApiSchema):
    """The room and the workpiece the host shares in."""

    room_id: str
    workpiece_id: str
    host_id: str = Field(description="The ID of the host, the user who shares.")
    created: bool = Field(
        description="False if the host was already sharing and this is the workpiece in use."
    )
