"""Staff-only analytics endpoints (administrators and moderators)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from modeling_api.routes.deps import CurrentBearer, CurrentUser, Limit, Skip
from modeling_api.schemas.analytics import (
    AttemptModel,
    PathActivity,
    PathFeedback,
    PathAnalytics,
    PathAnalyticsDetail,
    PathSurveys,
    PlatformOverview,
    PlatformPerson,
    PlatformTasks,
    StepAttempts,
    SurveyAnalytics,
    SurveyAnalyticsDetail,
    TourAnalyticsDetail,
    TourOverview,
    TourTimelineEvent,
)
from modeling_api.schemas.common import Page
from modeling_api.services import analytics_activity, analytics_feedback, analytics_path_surveys, analytics_paths, analytics_platform, analytics_surveys, analytics_tours

router = APIRouter(prefix="/analytics", tags=["Analytics"])

Period = Literal["7d", "30d", "semester", "all"]
PersonSort = Literal["name", "lastSeenAt", "models", "tasks", "evaluations", "helpRequests", "sessionSeconds"]
PeriodQuery = Query(default="30d", description="Counting period; a semester is the last 180 days.")
IncludeStaff = Query(default=False, alias="includeStaff", description="Include administrators and moderators.")


@router.get("/platform", response_model=PlatformOverview)
async def platform(user: CurrentUser, period: Period = PeriodQuery, include_staff: bool = IncludeStaff):
    return await analytics_platform.platform_overview(period, include_staff, user)


@router.get("/platform/tasks", response_model=PlatformTasks)
async def platform_tasks(user: CurrentUser, period: Period = PeriodQuery, include_staff: bool = IncludeStaff):
    return await analytics_platform.platform_tasks(period, include_staff, user)


@router.get("/platform/persons", response_model=Page[PlatformPerson])
async def platform_persons(
    user: CurrentUser,
    token: CurrentBearer,
    period: Period = PeriodQuery,
    include_staff: bool = IncludeStaff,
    sort_by: PersonSort = Query(default="lastSeenAt", alias="sortBy"),
    sort_desc: bool = Query(default=True, alias="sortDesc"),
    skip: Skip = 0,
    limit: Limit = 25,
):
    return await analytics_platform.platform_persons(
        period, include_staff, sort_by, sort_desc, skip, limit, user, token
    )


@router.get("/learning-paths", response_model=list[PathAnalytics])
async def learning_paths(user: CurrentUser):
    return await analytics_paths.path_overview(user)


@router.get("/learning-paths/{template_id}", response_model=PathAnalyticsDetail)
async def learning_path(template_id: UUID, user: CurrentUser, include_staff: bool = IncludeStaff):
    return await analytics_paths.path_detail(template_id, include_staff, user)


@router.get("/learning-paths/{template_id}/feedback", response_model=PathFeedback)
async def learning_path_feedback(template_id: UUID, user: CurrentUser, include_staff: bool = IncludeStaff):
    return await analytics_feedback.path_feedback(template_id, include_staff, user)


@router.get("/learning-paths/{template_id}/activity", response_model=PathActivity)
async def learning_path_activity(template_id: UUID, user: CurrentUser, include_staff: bool = IncludeStaff):
    return await analytics_activity.path_activity(template_id, include_staff, user)


@router.get("/learning-paths/{template_id}/surveys", response_model=PathSurveys)
async def learning_path_surveys(template_id: UUID, user: CurrentUser, include_staff: bool = IncludeStaff):
    return await analytics_path_surveys.path_surveys(template_id, include_staff, user)


@router.get("/learning-paths/{template_id}/participants/{run_id}/attempts", response_model=list[StepAttempts])
async def participant_attempts(template_id: UUID, run_id: UUID, user: CurrentUser):
    return await analytics_feedback.participant_attempts(template_id, run_id, user)


@router.get(
    "/learning-paths/{template_id}/participants/{run_id}/attempts/{evaluation_id}/model",
    response_model=AttemptModel,
    summary="Open the model of one attempt read-only (every call is logged in analytics_access_log).",
)
async def attempt_model(template_id: UUID, run_id: UUID, evaluation_id: UUID, user: CurrentUser):
    return await analytics_feedback.attempt_model(template_id, run_id, evaluation_id, user)


@router.get("/tours", response_model=TourOverview)
async def tours(user: CurrentUser, include_staff: bool = IncludeStaff):
    return await analytics_tours.tour_overview(include_staff, user)


@router.get("/tours/{tour_id}", response_model=TourAnalyticsDetail)
async def tour(tour_id: str, user: CurrentUser, token: CurrentBearer):
    return await analytics_tours.tour_detail(tour_id, user, token=token)


@router.get("/tours/{tour_id}/participants/{user_id}/events", response_model=list[TourTimelineEvent])
async def tour_timeline(tour_id: str, user_id: str, user: CurrentUser):
    return await analytics_tours.tour_timeline(tour_id, user_id, user)


@router.get("/surveys", response_model=list[SurveyAnalytics])
async def surveys(user: CurrentUser):
    return await analytics_surveys.survey_overview(user)


@router.get("/surveys/{survey_id}", response_model=SurveyAnalyticsDetail)
async def survey(
    survey_id: UUID,
    user: CurrentUser,
    release: UUID | None = Query(default=None, description="Release id; defaults to the active release."),
    context: Literal["all", "path", "pulse", "help"] = Query(default="all", description="Usage context of the responses."),
):
    return await analytics_surveys.survey_detail(survey_id, release, context, user)
