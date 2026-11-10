"""HTTP endpoints for sharing a model in a Collab-Kit room."""

from fastapi import APIRouter, Response

from modeling_api.core.errors import ApiError
from modeling_api.routes.deps import CurrentUser
from modeling_api.schemas.share import JoinedRoom, JoinRoom, SetJoinable, SetOpen, ShareModel, SharedRoom, ShareState
from modeling_api.services import models
from modeling_api.services.collab_kit import share as service, sweep

router = APIRouter(prefix="/share", tags=["Share"])


@router.post(
    "",
    summary="Share a model in a room",
    description=(
        "Opens a room for the current user as host and puts a new workpiece into it. The room "
        "and its groups are created on the first call and reused afterwards. Visitors always "
        "see; what else they may do is set here. With `task`, the task of the model comes "
        "along: its fixed text as a Collab-Kit task, and a second workpiece for marks and notes. "
        "If the host is already sharing, nothing changes and the workpiece in use is returned."
    ),
    response_description="The room and the workpiece the host shares in.",
    status_code=201,
)
async def share_model(body: ShareModel, user: CurrentUser, response: Response) -> SharedRoom:
    task = None
    if body.task:
        # The text comes from the DB, never from the browser; get_model checks that the model belongs to the user.
        if body.model_id is None:
            raise ApiError(422, "MODEL_MISSING", "Sharing the task needs the model it belongs to.")
        task = await models.get_shared_task(body.model_id, user)
    room_id, workpiece_id, created = await service.share(
        user.id, body.name, body.contract, body.units, body.anonymous, body.edit, body.comment, task
    )
    response.status_code = 201 if created else 200
    if created:
        # From now on someone looks that no visitor stays behind and that the host is not gone for long.
        sweep.ensure_running()
    return SharedRoom(room_id=room_id, workpiece_id=workpiece_id, host_id=user.id, created=created)


@router.get(
    "",
    summary="The share of the host as it stands",
    description=(
        "The share the current user hosts, with whether its room is locked and whether the sweep "
        "locked it because the host was gone. Asking also makes sure that the sweep looks after "
        "the share again, which is how a host who comes back wakes it. No share is a 404."
    ),
)
async def own_share(user: CurrentUser) -> ShareState:
    current = await service.own_share(user.id)
    if current["workpieceId"]:
        sweep.ensure_running()
    return ShareState(
        room_id=current["roomId"],
        workpiece_id=current["workpieceId"],
        open=current["open"],
        auto_locked=current["autoLocked"],
    )


@router.post(
    "/join",
    summary="Join a shared room",
    description=(
        "Takes the current user into the room of a link as visitor, as long as the host is "
        "sharing. Whoever is already in the room, the host included, passes without a change. "
        "A room that is not shared, or does not exist, is not found."
    ),
    response_description="The workpiece to open and the role of the user.",
)
async def join_room(body: JoinRoom, user: CurrentUser) -> JoinedRoom:
    workpiece_id, role, host_id = await service.join(user.id, body.room_id)
    return JoinedRoom(room_id=body.room_id, workpiece_id=workpiece_id, role=role, host_id=host_id)


@router.post(
    "/leave",
    summary="Leave a shared room as visitor",
    description=(
        "Takes the current user out of the visitors of the room, so they can go at any time, "
        "and deletes their working copy of the room model. "
        "A room that is closed or gone, or a user who is no visitor, changes nothing; "
        "repeating the call is harmless."
    ),
    status_code=204,
)
async def leave_room(body: JoinRoom, user: CurrentUser) -> None:
    await service.leave(user.id, body.room_id)


@router.put(
    "/open",
    summary="Lock or reopen the room of the host",
    description=(
        "Locking, while the host decides how to save, refuses new visitors and takes away their "
        "right to edit, so everyone keeps the same state. Opening again, after a cancel, gives "
        "back what they had. Only the host of the room may call this."
    ),
    status_code=204,
)
async def set_open(body: SetOpen, user: CurrentUser) -> None:
    await service.set_open(user.id, body.open)
    if body.open:
        # The room is open again, so the sweep has to look after it again.
        sweep.ensure_running()


@router.put(
    "/joinable",
    summary="Close or open the link for new visitors",
    description=(
        "Closed, no one new can join through the link. Visitors already in stay, and so do their "
        "rights. Only the host of the room may call this."
    ),
    status_code=204,
)
async def set_joinable(body: SetJoinable, user: CurrentUser) -> None:
    await service.set_joinable(user.id, body.joinable)


@router.post(
    "/close",
    summary="Stop sharing",
    description=(
        "Takes all visitors out and the workpiece out of the room and deletes the working copies "
        "of the room model, except those of visitors still connected, which go when they leave. "
        "The room and its groups stay "
        "for the next time. Repeating the call finishes what an interrupted one left. Only the "
        "host of the room may call this."
    ),
    status_code=204,
)
async def close_room(user: CurrentUser) -> None:
    await service.close(user.id)
