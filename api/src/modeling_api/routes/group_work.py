"""HTTP-Endpunkte für die Gruppenarbeit in Collab-Kit."""

from fastapi import APIRouter

from modeling_api.routes.deps import CurrentBearer, CurrentUser
from modeling_api.schemas.group_work import CreateGroupWork, GroupWorkPlan, GroupWorkResult
from modeling_api.services.collab_kit import group_work as service

router = APIRouter(prefix="/group-work", tags=["Group work"])


@router.post(
    "/preview",
    summary="Preview group work",
    description=(
        "Tells what creating the group work would do, without writing anything: per group "
        "whether its course already has a room of that name, and if so which members and tasks "
        "it lacks. Members are found by their login name in the Feedbacksystem with the caller's "
        "token. Only moderators may call it."
    ),
    response_description="What each group would get.",
)
async def preview_group_work(body: CreateGroupWork, user: CurrentUser, token: CurrentBearer) -> GroupWorkPlan:
    groups = [group.model_dump(mode="json", by_alias=True) for group in body.groups]
    planned = await service.plan(user, body.course, groups, token)
    # Gruppe und IDs der Mitglieder braucht nur das Anlegen; der Browser bekommt die Anmeldenamen.
    shown = ("name", "roomId", "newMembers", "newTasks", "missing")
    return GroupWorkPlan.model_validate({"rooms": [{key: entry[key] for key in shown} for entry in planned]})


@router.post(
    "",
    summary="Create rooms for group work",
    description=(
        "Creates one Collab-Kit room per group of the course, with a group in which every member "
        "may see, comment and edit, and one model per task as sharing creates it: the fixed task "
        "text, a workpiece for marks and notes, and the model. A group whose course already has a "
        "room of that name gets only what it lacks: new members, and models for new tasks; nobody "
        "is removed. Whoever has no account in the Feedbacksystem is left out and listed. Only "
        "moderators may call it."
    ),
    response_description="The rooms created or completed, and the login names not found.",
    status_code=201,
)
async def create_group_work(body: CreateGroupWork, user: CurrentUser, token: CurrentBearer) -> GroupWorkResult:
    groups = [group.model_dump(mode="json", by_alias=True) for group in body.groups]
    return GroupWorkResult.model_validate({"rooms": await service.create(user, body.course, groups, token)})
