"""Synonym glossary requests, responses and the validated signal exchange format."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modeling_api.schemas.common import ApiSchema
from modeling_api.schemas.evaluations import EvaluationDetail, TextEvidenceThresholds

ElementId = Annotated[str, Field(min_length=1, max_length=512)]
Term = Annotated[str, Field(min_length=1, max_length=256)]
EntryStatus = Literal["accepted", "rejected", "ignored"]
TargetKind = Literal["element", "connection"]


class GlossaryChange(ApiSchema):
    reference_element_id: ElementId
    term: Term
    status: EntryStatus | None = Field(description="New status; null removes the entry.")


class SaveGlossaryEntries(ApiSchema):
    base_revision: int = Field(ge=0)
    changes: list[GlossaryChange] = Field(min_length=1, max_length=500)


class ImportGlossaryEntries(ApiSchema):
    from_reference_version_id: UUID
    base_revision: int = Field(ge=0)


class SetMatchingSource(ApiSchema):
    base_revision: int = Field(ge=0)
    enabled: bool = Field(strict=True)


class RecalculateSignals(ApiSchema):
    scope: Literal["missing", "all"]


class GlossaryEntry(ApiSchema):
    id: str
    reference_element_id: str
    term: str
    term_key: str
    status: EntryStatus
    origin: Literal["manual", "suggestion"]
    updated_at: datetime
    matching_source: bool = False


class GlossaryElement(ApiSchema):
    id: str
    label: str
    target_kind: TargetKind
    type: str | None
    comparison_group: str | None


class SuggestionVariant(ApiSchema):
    text: str
    count: int


class SuggestionEvidence(ApiSchema):
    context_unique: int
    context_best: int
    text_only: int
    recognized: int = 0
    hint_accepted: int = 0


class TermComparison(ApiSchema):
    reference_text: str
    submission_text: str
    method: str
    minimum: float
    maximum: float
    acceptance: float | None = None
    floor: float | None = None
    reference_form: str | None = None
    submission_form: str | None = None


class AlsoSuggestedFor(ApiSchema):
    reference_element_id: str
    label: str
    persons: int


class Suggestion(ApiSchema):
    reference_element_id: str
    term: str
    term_key: str
    variants: list[SuggestionVariant]
    persons: int
    submissions: int
    evidence: SuggestionEvidence
    also_suggested_for: list[AlsoSuggestedFor]
    comparisons: list[TermComparison] = Field(default_factory=list)


class OutcomeCounts(ApiSchema):
    counted: int
    partial: int = 0
    not_counted: int
    counted_elsewhere: int
    counted_at_same_name: int = 0
    unknown: int
    used_for_learner_result: int


class OutcomeOccurrence(ApiSchema):
    evaluation_id: str
    model_version_id: str
    submission_element_id: str | None
    state: Literal["counted", "partial", "not_counted", "counted_elsewhere", "unknown"]
    used_for_learner_result: bool
    evidence_note: str | None = None
    reason: str | None = None


class ExplainOutcome(ApiSchema):
    evaluation_id: Annotated[str, Field(min_length=1, max_length=100)]
    reference_element_id: ElementId
    term_key: Term
    submission_element_id: ElementId | None = None
    replay_id: UUID | None = None


class OutcomeCheck(ApiSchema):
    method: str
    result: str
    role: str
    note: str


class OutcomeSimilarity(ApiSchema):
    method: str
    score: float | None
    thresholds: dict[str, float]
    confirmation_floors: dict[str, float]
    reference_text: str | None = None


class OutcomeAlternative(ApiSchema):
    reference_element_id: str
    reference_label: str
    submission_element_id: str
    submission_label: str
    counted: bool


class OutcomeExplanation(ApiSchema):
    submission_element_id: str | None
    submission_label: str
    reference_label: str
    state: Literal["counted", "partial", "not_counted", "counted_elsewhere", "unknown"]
    summary: str
    candidate_reason: str
    result_reason: str
    evidence_scope: Literal["pair", "submission", "suggestion"]
    checks: list[OutcomeCheck]
    similarities: list[OutcomeSimilarity]
    alternatives: list[OutcomeAlternative]
    limitations: list[str]


class OutcomeGroup(ApiSchema):
    key: str
    conditions: dict[str, str]
    cases: int
    comparisons: list[TermComparison]
    counts: OutcomeCounts
    reasons: dict[str, int]


class TermOutcome(ApiSchema):
    reference_element_id: str
    term: str
    term_key: str
    counts: OutcomeCounts
    reasons: dict[str, int] = Field(default_factory=dict)
    occurrences: list[OutcomeOccurrence]
    comparisons: list[TermComparison] = Field(default_factory=list)
    groups: list[OutcomeGroup] = Field(default_factory=list)


class StartReplay(ApiSchema):
    text_evidence: TextEvidenceThresholds | None = None
    evaluation_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=500)


class ReplayEvaluationDetail(EvaluationDetail):
    id: str = Field(pattern=r"^replay-[a-f0-9-]{36}-[0-9]+$")


class ReplayCandidate(ApiSchema):
    evaluation_id: str
    model_id: str
    model_version_id: str
    model_name: str
    started_at: datetime
    state: str
    staff: bool


class ReplayItem(ApiSchema):
    evaluation_id: str
    model_version_id: str
    run_id: str
    status: Literal["pending", "running", "done", "failed"]
    before_percent: float | None = None
    after_percent: float | None = None
    error: str | None = None


class ReplayBatch(ApiSchema):
    id: str
    state: Literal["running", "completed"]
    created_at: datetime
    expires_at: datetime
    workflow_name: str
    workflow_version: str | None
    text_evidence: TextEvidenceThresholds | None
    items: list[ReplayItem]
    outcomes: list[TermOutcome]
    unavailable: bool = False


class SignalJobStatus(ApiSchema):
    id: str
    scope: Literal["missing", "all"]
    state: Literal["running", "completed"]
    total: int
    done: int
    failed: int


class SignalStatus(ApiSchema):
    evaluated: int
    collected: int
    missing: int
    unavailable: bool = Field(description="True when the workflow service could not be reached.")
    job: SignalJobStatus | None


class GlossaryView(ApiSchema):
    revision: int
    elements: list[GlossaryElement]
    entries: list[GlossaryEntry]
    suggestions: list[Suggestion]
    signals: SignalStatus
    outcomes: list[TermOutcome]
    outcomes_unavailable: int
    matching_workload: "MatchingWorkload"


class MatchingWorkload(ApiSchema):
    basis: Literal["text_pairs", "reference_texts"]
    baseline: int
    additional: int
    total: int
    percent: float | None
    covered: int
    evaluated: int


class ImportResult(ApiSchema):
    imported: int
    skipped: list[str]
    glossary: GlossaryView


class EvaluableRelease(ApiSchema):
    id: str
    version_number: int
    sample_solutions: list[dict[str, str]]


class EvaluableTask(ApiSchema):
    id: str
    name: str
    releases: list[EvaluableRelease]


class _Signal(BaseModel):
    """Strict trust-boundary model: unknown fields would be submission data and are rejected."""

    model_config = ConfigDict(extra="forbid", strict=True)

    referenceElementId: ElementId
    targetKind: TargetKind
    comparisonKey: Annotated[str, Field(min_length=1, max_length=1024)]
    term: Term
    termKey: Term
    evidence: Literal["context_unique", "context_best", "text_only"]
    contextBasis: Literal["owner", "neighbors", "endpoints", "none"]
    scores: dict[str, float]


class _SignalReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    key: str
    modelId: str
    versionId: str


class _SignalProducer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    service: Literal["synonym-matching"]
    version: str
    resourceHash: str


class _SignalCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    openReferenceElements: int = Field(ge=0)
    openSubmissionTexts: int = Field(ge=0)
    signals: int = Field(ge=0)


class SynonymSignals(BaseModel):
    """`synonym-signals/v1`; any other schema or term normalization is discarded."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_: Literal["synonym-signals/v1"] = Field(alias="schema")
    evaluationId: str
    inputHash: str
    candidateHash: str
    comparisonHash: str
    reference: _SignalReference
    producer: _SignalProducer
    glossaryRevision: int = Field(ge=0)
    termNormalization: Literal["nfc-casefold-space-v1"]
    coverage: _SignalCoverage
    signals: list[_Signal] = Field(max_length=20_000)
