"""Administrator endpoints for the per-solution synonym glossary."""

from uuid import UUID

from fastapi import APIRouter, Response

from modeling_api.routes.deps import CurrentUser
from modeling_api.schemas.synonym_glossary import (
    EvaluableTask,
    GlossaryView,
    ImportGlossaryEntries,
    ImportResult,
    RecalculateSignals,
    SaveGlossaryEntries,
    SignalStatus,
    ReplayBatch,
    StartReplay,
    ExplainOutcome,
    OutcomeExplanation,
    SetMatchingSource,
)
from modeling_api.services import synonym_glossary as service
from modeling_api.services import synonym_signals as signals
from modeling_api.services import evaluation_replays as replays
from modeling_api.services import synonym_outcome_evidence as evidence
from modeling_api.services.tasks import get_sample_solution

router = APIRouter(prefix="/synonym-glossary", tags=["Synonym glossary"])
SOLUTION = "/tasks/{task_id}/versions/{version_id}/solutions/{model_id}/{model_version_id}"


@router.get("/tasks", response_model=list[EvaluableTask])
async def list_tasks(user: CurrentUser):
    service.require_admin(user)
    return await service.list_tasks()


@router.get(SOLUTION, response_model=GlossaryView)
async def get_solution(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID, user: CurrentUser,
                       exclude_own: bool = False, exclude_staff: bool = True):
    service.require_admin(user)
    return await signals.solution_view(task_id, version_id, model_id, model_version_id, user,
                                       exclude_own=exclude_own, exclude_staff=exclude_staff)


@router.post(SOLUTION + "/entries", response_model=GlossaryView)
async def save_entries(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                       body: SaveGlossaryEntries, user: CurrentUser):
    service.require_admin(user)
    await service.save_entries(task_id, version_id, model_id, model_version_id, body, user)
    return await signals.solution_view(task_id, version_id, model_id, model_version_id, user)


@router.post(SOLUTION + "/entries/{entry_id}/matching-source", response_model=GlossaryView)
async def set_matching_source(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                               entry_id: UUID, body: SetMatchingSource, user: CurrentUser):
    service.require_admin(user)
    await service.set_matching_source(task_id, version_id, model_id, model_version_id, entry_id, body, user)
    return await signals.solution_view(task_id, version_id, model_id, model_version_id, user)


@router.post(SOLUTION + "/entries/import", response_model=ImportResult)
async def import_entries(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                         body: ImportGlossaryEntries, user: CurrentUser):
    service.require_admin(user)
    imported, skipped = await service.import_entries(task_id, version_id, model_id, model_version_id, body, user)
    glossary = await signals.solution_view(task_id, version_id, model_id, model_version_id, user)
    return {"imported": imported, "skipped": skipped, "glossary": glossary}


@router.post("/tasks/{task_id}/versions/{version_id}/signals/recalculate", response_model=SignalStatus)
async def recalculate(task_id: UUID, version_id: UUID, body: RecalculateSignals, user: CurrentUser):
    service.require_admin(user)
    return await signals.recalculate(task_id, version_id, body.scope, user)


@router.get("/tasks/{task_id}/versions/{version_id}/signals/status", response_model=SignalStatus)
async def signal_status(task_id: UUID, version_id: UUID, user: CurrentUser):
    service.require_admin(user)
    return await signals.status(task_id, version_id, user)


@router.post(SOLUTION + "/outcomes/explain", response_model=list[OutcomeExplanation])
async def explain_outcome(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                          body: ExplainOutcome, user: CurrentUser):
    service.require_admin(user)
    await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    return await evidence.explain(task_id, version_id, model_version_id, body)


@router.get(SOLUTION + "/replays", response_model=list[ReplayBatch])
async def list_replays(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID, user: CurrentUser):
    service.require_admin(user)
    await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    return await replays.list_batches(task_id, version_id, model_version_id)


@router.post(SOLUTION + "/replays", response_model=ReplayBatch)
async def start_replay(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                       body: StartReplay, user: CurrentUser):
    service.require_admin(user)
    await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    return await replays.start(task_id, version_id, model_version_id, user,
                               body.text_evidence.model_dump(by_alias=True) if body.text_evidence else None)


@router.get(SOLUTION + "/replays/{batch_id}", response_model=ReplayBatch)
async def replay_detail(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                        batch_id: UUID, user: CurrentUser):
    service.require_admin(user)
    await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    return await replays.detail(task_id, version_id, batch_id, model_version_id)


@router.delete(SOLUTION + "/replays/{batch_id}", status_code=204)
async def delete_replay(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                        batch_id: UUID, user: CurrentUser):
    service.require_admin(user)
    await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    await replays.delete(task_id, version_id, batch_id)
    return Response(status_code=204)
