"""Read-only staff analytics views."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from modeling_api.schemas.common import ApiSchema


class PathAnalytics(ApiSchema):
    id: UUID
    name: str
    visibility: Literal["published", "unlisted", "hidden"]
    revision: int
    participants: int = Field(ge=0)
    not_started: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    completed: int = Field(ge=0)
    stalled: int = Field(ge=0, description="In progress with no recorded activity for more than 7 days.")
    avg_progress: float = Field(ge=0, le=100)
    completion_rate: float = Field(ge=0, le=100)
    median_seconds_to_finish: float | None = None
    last_activity_at: datetime | None = None


class PathAnalyticsDetail(PathAnalytics):
    description: str
    hidden_staff_runs: int = Field(ge=0, description="Runs of staff users left out of all figures (0 when staff is included).")


class TourAnalytics(ApiSchema):
    id: str
    title: str
    version: int
    opened_users: int = Field(ge=0)
    started_users: int = Field(ge=0)
    completed_users: int = Field(ge=0)
    skipped_users: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=100, description="Completed users as a share of users who started the tour.")
    last_activity_at: datetime | None = None


class TourSummary(ApiSchema):
    tours: int = Field(ge=0)
    opened_users: int = Field(ge=0, description="Distinct users who opened the tour menu (any tour).")
    started_users: int = Field(ge=0)
    completed_users: int = Field(ge=0)
    skipped_users: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=100, description="Completed users as a share of users who started (any tour).")
    known_users: int = Field(ge=0, description="Known users in submission_users, without staff unless included.")
    coverage: float = Field(ge=0, le=100, description="Users who started any tour as a share of known users.")


class TourWeek(ApiSchema):
    week_start: datetime = Field(description="Monday 00:00 UTC of the calendar week.")
    starts: int = Field(ge=0, description="Distinct users who started a tour in the week.")
    completions: int = Field(ge=0, description="Distinct users who completed a tour in the week.")


class TourOverview(ApiSchema):
    summary: TourSummary
    weekly: list[TourWeek]
    tours: list[TourAnalytics]


class TourFunnelStep(ApiSchema):
    id: str
    title: str
    reached: int = Field(ge=0, description="Users whose furthest step is this one or a later one.")
    left_here: int = Field(ge=0, description="Users whose furthest step is this one and who did not complete the tour.")
    biggest_drop_off: bool


class TourParticipant(ApiSchema):
    user_id: str
    user_name: str
    status: Literal["opened", "in_progress", "completed", "skipped"]
    furthest_step_id: str | None = None
    opens: int = Field(ge=0)
    starts: int = Field(ge=0)
    first_event_at: datetime
    last_event_at: datetime


class TourAnalyticsDetail(TourAnalytics):
    steps: list[TourFunnelStep]
    participants: list[TourParticipant]


class TourTimelineEvent(ApiSchema):
    event: Literal["opened", "started", "step", "completed", "skipped"]
    step_id: str | None = None
    step_title: str | None = None
    at: datetime


class CountItem(ApiSchema):
    key: str
    count: int = Field(ge=0)


class WeekPoint(ApiSchema):
    week_start: datetime = Field(description="Monday 00:00 UTC of the calendar week.")
    count: int = Field(ge=0)


class HistogramBin(ApiSchema):
    label: str
    users: int = Field(ge=0)


class PlatformKpis(ApiSchema):
    known_users: int = Field(ge=0)
    new_users: int = Field(ge=0)
    active_users_week: int = Field(ge=0)
    active_users_month: int = Field(ge=0)
    users_with_models: int = Field(ge=0)
    models: int = Field(ge=0)
    models_archived: int = Field(ge=0)
    avg_models_per_user: float | None = None
    median_models_per_user: float | None = None
    checkpoints: int = Field(ge=0)
    releases: int = Field(ge=0)


class PlatformOverview(ApiSchema):
    period: Literal["7d", "30d", "semester", "all"]
    since: datetime | None = None
    kpis: PlatformKpis
    weekly_active_users: list[WeekPoint]
    weekly_new_models: list[WeekPoint]
    models_per_user: list[HistogramBin]


class PlatformTaskKpis(ApiSchema):
    tasks_published: int = Field(ge=0)
    tasks_hidden: int = Field(ge=0)
    tasks_archived: int = Field(ge=0)
    evaluations: int = Field(ge=0)
    evaluations_last_week: int = Field(ge=0)
    evaluations_by_state: list[CountItem]


class PlatformTask(ApiSchema):
    task_id: str
    task_name: str
    persons: int = Field(ge=0)
    models: int = Field(ge=0)
    evaluations: int = Field(ge=0)
    avg_score: float | None = None


class PlatformTasks(ApiSchema):
    period: Literal["7d", "30d", "semester", "all"]
    since: datetime | None = None
    kpis: PlatformTaskKpis
    tasks: list[PlatformTask]


class PlatformPerson(ApiSchema):
    user_id: str
    user_name: str
    last_seen_at: datetime | None = None
    models: int = Field(ge=0)
    tasks: int = Field(ge=0)
    evaluations: int = Field(ge=0)
    help_requests: int = Field(ge=0)
    session_seconds: float = Field(ge=0)


class CurvePoint(ApiSchema):
    attempt: int = Field(ge=1)
    avg_score: float | None = None
    scored: int = Field(ge=0, description="Attempts with a score at this attempt number.")


class SupportUse(ApiSchema):
    kind: str
    persons: int = Field(ge=0)
    requests: int = Field(ge=0)


class SupportLimit(ApiSchema):
    kind: str
    limit: int | None = Field(default=None, description="Per-person quota of this task; null means unlimited.")
    exhausted: int | None = Field(default=None, ge=0, description="Persons who received feedback up to the limit.")
    share: float | None = Field(default=None, description="Exhausted persons as a percentage of persons who started the task.")


class HelpFunnel(ApiSchema):
    requests: int = Field(ge=0)
    topic_done: int = Field(ge=0)
    reflection_done: int = Field(ge=0)
    completed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    open: int = Field(ge=0, description="Neither completed nor cancelled.")
    abort_rate: float | None = Field(default=None, description="Cancelled share of all help requests, in percent.")


class StepFeedback(ApiSchema):
    step_id: str
    title: str
    persons: int = Field(ge=0, description="Persons who started the task.")
    attempt_persons: int = Field(ge=0)
    attempts: int = Field(ge=0)
    avg_attempts: float | None = None
    attempt_distribution: list[HistogramBin]
    minimum_score_percent: float | None = None
    passed_persons: int | None = None
    passed_share: float | None = Field(default=None, description="Persons who met the completion gate, in percent of persons with an attempt.")
    scored_persons: int = Field(ge=0)
    avg_first_score: float | None = None
    avg_best_score: float | None = None
    score_bands: list[HistogramBin]
    score_curve: list[CurvePoint]
    support: list[SupportUse]
    limits: list[SupportLimit]
    help: HelpFunnel


class PulseSurveyUse(ApiSchema):
    survey_id: str
    name: str
    offered: int = Field(ge=0)
    answered: int = Field(ge=0)
    answer_rate: float | None = None


class PulseStats(ApiSchema):
    offers: int = Field(ge=0)
    opened: int = Field(ge=0)
    answered: int = Field(ge=0)
    dismissed: int = Field(ge=0)
    expired: int = Field(ge=0)
    pending: int = Field(ge=0, description="No reaction recorded yet.")
    open_rate: float | None = None
    answer_rate: float | None = None
    dismiss_rate: float | None = None
    expired_rate: float | None = None
    sessions: int = Field(ge=0, description="Distinct browser sessions that received an offer.")
    offers_per_session: float | None = None
    surveys: list[PulseSurveyUse]


class HelpAnswerQuestion(ApiSchema):
    name: str
    title: str
    responses: int = Field(ge=0)
    options: list[CountItem] = Field(description="Choice labels with their answer counts.")


class PathFeedback(ApiSchema):
    steps: list[StepFeedback]
    help: HelpFunnel
    pulse: PulseStats
    help_answers: list[HelpAnswerQuestion]


class AttemptEvent(ApiSchema):
    at: datetime
    type: Literal["evaluation", "help_request"]
    evaluation_id: UUID | None = Field(default=None, description="Set for evaluations; opens the submitted model.")
    state: str | None = None
    score_percent: float | None = None
    passed: bool | None = None
    support_kind: str | None = None
    help_stage: str | None = None


class StepAttempts(ApiSchema):
    step_id: str
    title: str
    events: list[AttemptEvent]


class AttemptModel(ApiSchema):
    evaluation_id: UUID
    step_id: str
    step_title: str
    started_at: datetime
    model_version_id: UUID | None = None
    xml: str = Field(description="Submitted model as stored in the evaluation snapshot.")
    feedback: dict[str, Any] | None = Field(default=None, description="Learner-facing feedback projection; null while the learner has not loaded it.")


class ActivityStats(ApiSchema):
    persons: int = Field(ge=0, description="Persons with at least one editor session.")
    sessions: int = Field(ge=0)
    open_sessions: int = Field(ge=0, description="Sessions without a received end; counted up to their last interaction.")
    avg_sessions_per_person: float | None = None
    session_distribution: list[HistogramBin]
    avg_gross_seconds: float | None = Field(default=None, description="Per person: sum of session durations.")
    median_gross_seconds: float | None = None
    avg_active_seconds: float | None = Field(default=None, description="Per person: gross time minus idle intervals.")
    median_active_seconds: float | None = None
    avg_session_seconds: float | None = None
    tab_hidden_per_person: float | None = None
    focus_lost_per_person: float | None = None
    tab_hidden_per_session: float | None = None
    focus_lost_per_session: float | None = None
    outside_share: float | None = Field(default=None, description="Share of session time with hidden tab or lost focus, in percent.")


class StepActivity(ActivityStats):
    step_id: str
    title: str


class ActivityTotals(ApiSchema):
    sessions: int = Field(ge=0)
    gross_seconds: float = Field(ge=0)
    active_seconds: float = Field(ge=0)
    tab_hidden: int = Field(ge=0)
    focus_lost: int = Field(ge=0)


class RunStepActivity(ActivityTotals):
    step_id: str


class RunActivity(ActivityTotals):
    run_id: UUID
    steps: list[RunStepActivity]


class PathActivity(ApiSchema):
    path: ActivityStats
    steps: list[StepActivity]
    runs: list[RunActivity] = Field(description="Aggregated activity per participant run; runs without sessions are absent.")


class SurveyStatusCounts(ApiSchema):
    responses: int = Field(ge=0, description="Sessions that were opened, excluding test responses.")
    submitted: int = Field(ge=0)
    skipped: int = Field(ge=0)
    draft: int = Field(ge=0)


class SurveyAnalytics(SurveyStatusCounts):
    id: UUID
    title: str
    kind: Literal["standard", "help"]
    active_release_version: int | None = None
    submitted_share: float | None = None
    skipped_share: float | None = None
    draft_share: float | None = None
    last_response_at: datetime | None = None


class SurveyReleaseInfo(ApiSchema):
    id: UUID
    version: int
    released_at: datetime | None = None
    active: bool
    submitted: int = Field(ge=0)


class SurveyOption(ApiSchema):
    key: str
    label: str
    count: int = Field(ge=0)


class SurveyTrendPoint(ApiSchema):
    week_start: datetime = Field(description="Monday 00:00 UTC of the calendar week.")
    responses: int = Field(ge=0)
    mean: float | None = Field(default=None, description="Mean rating of the week; ratings only.")


class SurveyQuestionStats(ApiSchema):
    name: str
    title: str
    type: str
    kind: Literal["choice", "rating", "text", "other"]
    responses: int = Field(ge=0, description="Submitted responses that answered this question.")
    mean: float | None = None
    median: float | None = None
    avg_length: float | None = Field(default=None, description="Average characters of free-text answers.")
    scale_min: int | None = None
    scale_max: int | None = None
    min_label: str | None = Field(default=None, description="Label of the lowest rating, when defined in the survey.")
    max_label: str | None = Field(default=None, description="Label of the highest rating, when defined in the survey.")
    options: list[SurveyOption] = Field(description="Answer counts: choices (boolean: keys true/false), or one entry per rating value over the full scale.")
    trend: list[SurveyTrendPoint]


class SurveyAnalyticsDetail(SurveyStatusCounts):
    submitted_last_week: int = Field(ge=0, description="Submitted responses in the last 7 days.")
    completion_share: float | None = Field(default=None, description="Submitted share of all opened sessions, percent.")
    last_response_at: datetime | None = None
    id: UUID
    title: str
    kind: Literal["standard", "help"]
    release: SurveyReleaseInfo | None = None
    releases: list[SurveyReleaseInfo]
    context: Literal["all", "path", "pulse", "help"]
    context_counts: list[CountItem] = Field(description="Submitted responses per usage context of the selected release.")
    questions: list[SurveyQuestionStats]


class PathSurveyRating(ApiSchema):
    name: str
    title: str
    responses: int = Field(ge=0, description="Submitted answers of the release.")
    responses_last_week: int = Field(ge=0)
    mean_overall: float | None = None
    mean_last_week: float | None = Field(default=None, description="Mean of the answers submitted in the last 7 days.")


class PathSurveyRelease(ApiSchema):
    id: UUID
    version: int
    released_at: datetime | None = None
    active: bool
    submitted: int = Field(ge=0, description="Submitted responses of this path's participants to this release.")
    ratings: list[PathSurveyRating]
    questions: list[SurveyQuestionStats]


class PathSurvey(SurveyStatusCounts):
    submitted_last_week: int = Field(ge=0, description="Submitted responses in the last 7 days.")
    submitted_previous_week: int = Field(ge=0, description="Submitted responses in the 7 days before the last 7 days.")
    completion_share: float | None = Field(default=None, description="Submitted share of all opened sessions, percent.")
    last_response_at: datetime | None = None
    id: UUID
    title: str
    usages: list[str] = Field(description="Where the template uses the survey; empty when it is no longer part of the path.")
    releases: list[PathSurveyRelease] = Field(description="Releases answered by this path's participants, newest first.")


class PathSurveys(ApiSchema):
    surveys: list[PathSurvey]
