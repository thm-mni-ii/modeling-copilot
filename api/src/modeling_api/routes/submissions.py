"""Authenticated routes for global feedback, assignments, runs and reviews."""

from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from modeling_api.routes.deps import CurrentBearer, CurrentUser, Limit, Skip
from modeling_api.schemas.submissions import (
    PublishReviews,
    SaveAssignment,
    SaveGlobalFeedback,
    SaveReview,
    SaveRun,
    SetResolved,
    StartRun,
    SubmitModel,
)
from modeling_api.services import submissions as service

router = APIRouter(tags=["Submissions"])


@router.get("/submission-access")
async def access(user: CurrentUser):
    return await service.submission_access(user)


@router.get("/submission-courses")
async def courses(user: CurrentUser):
    return await service.courses(user)


@router.get("/submission-courses/{assignment_id}")
async def course(assignment_id: UUID, user: CurrentUser):
    return await service.course_detail(assignment_id, user)


@router.post("/submission-runs/{run_id}/enrollment")
async def enroll(run_id: UUID, user: CurrentUser):
    return await service.enroll(run_id, user)


@router.get("/global-feedback-settings")
async def global_feedback(
    user: CurrentUser, revision: int | None = Query(default=None, ge=0)
):
    return await service.global_feedback(revision)


@router.put("/global-feedback-settings")
async def save_global_feedback(body: SaveGlobalFeedback, user: CurrentUser):
    return await service.save_global_feedback(body, user)


@router.get("/submission-users")
async def users(
    user: CurrentUser,
    token: CurrentBearer,
    q: str = Query(default="", max_length=256),
    run_id: UUID | None = Query(default=None, alias="runId"),
):
    return await service.users(user, q, run_id, token)


@router.get("/submission-assignments")
async def assignments(
    user: CurrentUser, skip: Skip = 0, limit: Limit = 20, archived: bool = False
):
    return await service.assignments(user, skip, limit, archived)


@router.post("/submission-assignments", status_code=201)
async def create_assignment(body: SaveAssignment, user: CurrentUser):
    return await service.save_assignment(None, body, user)


@router.get("/submission-assignments/{assignment_id}")
async def assignment(assignment_id: UUID, user: CurrentUser):
    return await service.assignment_detail(assignment_id, user)


@router.put("/submission-assignments/{assignment_id}")
async def save_assignment(assignment_id: UUID, body: SaveAssignment, user: CurrentUser):
    return await service.save_assignment(assignment_id, body, user)


@router.post("/submission-assignments/{assignment_id}/runs", status_code=201)
async def start_run(assignment_id: UUID, body: StartRun, user: CurrentUser):
    return await service.start_run(assignment_id, body, user)


@router.get("/submission-runs/{run_id}")
async def run(
    run_id: UUID,
    user: CurrentUser,
    view: Literal["participant", "management"] | None = None,
):
    return await service.run_detail(run_id, user, view)


@router.put("/submission-runs/{run_id}")
async def save_run(run_id: UUID, body: SaveRun, user: CurrentUser):
    return await service.save_run(run_id, body, user)


@router.get("/submission-runs/{run_id}/submissions")
async def submissions(
    run_id: UUID,
    user: CurrentUser,
    token: CurrentBearer,
    skip: Skip = 0,
    limit: Limit = 20,
    history: bool = False,
    view: Literal["participant", "management"] | None = None,
):
    return await service.submission_list(
        run_id, user, skip, limit, history, view, token
    )


@router.get("/submission-runs/{run_id}/submissions.csv", response_class=Response)
async def export_submissions(run_id: UUID, user: CurrentUser, token: CurrentBearer):
    content = await service.export_submissions_csv(run_id, user, token)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="submissions-{run_id}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/submission-runs/{run_id}/submissions", status_code=201)
async def submit(run_id: UUID, body: SubmitModel, user: CurrentUser):
    return await service.submit(run_id, body, user)


@router.post("/submission-runs/{run_id}/publish")
async def publish(run_id: UUID, body: PublishReviews, user: CurrentUser):
    return await service.publish(run_id, body, user)


@router.get("/submissions/{submission_id}")
async def submission(
    submission_id: UUID,
    user: CurrentUser,
    token: CurrentBearer,
    view: Literal["participant", "management"] | None = None,
):
    return await service.submission_detail(submission_id, user, view, token)


@router.put("/submissions/{submission_id}/reviews/staff")
async def save_review(
    submission_id: UUID,
    body: SaveReview,
    user: CurrentUser,
    view: Literal["participant", "management"] | None = None,
):
    return await service.save_review(submission_id, body, user, "staff", view)


@router.put("/submissions/{submission_id}/resolved")
async def resolve(submission_id: UUID, body: SetResolved, user: CurrentUser):
    return await service.resolve(submission_id, body, user)
