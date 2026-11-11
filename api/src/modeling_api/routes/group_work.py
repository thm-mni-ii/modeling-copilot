"""HTTP-Endpunkt für die Gruppenarbeit in Collab-Kit."""

from fastapi import APIRouter

from modeling_api.routes.deps import CurrentBearer, CurrentUser
from modeling_api.schemas.group_work import CreateGroupWork, GroupWorkResult
from modeling_api.services.collab_kit import group_work as service

router = APIRouter(prefix="/group-work", tags=["Group work"])


@router.post(
    "",
    summary="Create rooms for group work",
    description=(
        "Creates one Collab-Kit room per group, with a group in which every member may see, "
        "comment and edit, and one model per task as sharing creates it: the fixed task text, "
        "a workpiece for marks and notes, and the model. Members are found by their login name "
        "in the Feedbacksystem with the caller's token; whoever has no account there is left "
        "out and listed. Only moderators may call it."
    ),
    response_description="The rooms created and the login names not found.",
    status_code=201,
)
async def create_group_work(body: CreateGroupWork, user: CurrentUser, token: CurrentBearer) -> GroupWorkResult:
    groups = [group.model_dump(mode="json", by_alias=True) for group in body.groups]
    return GroupWorkResult.model_validate({"rooms": await service.create(user, groups, token)})
