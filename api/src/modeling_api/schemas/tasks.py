"""Schemas für globale Aufgaben und ihre unveränderlichen Fassungen."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from modeling_api.schemas.common import (
    ApiSchema,
    Identity,
    ModelVersionReference,
    Name,
    TaskVersionReference,
    VersionInfo,
    VersionKind,
)
from modeling_api.schemas.models import WorkspaceLanguageReference

AutonomyMode = Literal["free", "informative", "validating", "preventive"]


class Task(Identity):
    name: Name
    parent: TaskVersionReference | None = None
    latest_version_id: UUID | None
    latest_release_id: UUID | None = None
    archived_at: datetime | None = None


class CreateTask(ApiSchema):
    name: Name
    parent: TaskVersionReference | None = None


class UpdateTask(ApiSchema):
    name: Name | None = None
    archived: bool | None = None

    @model_validator(mode="after")
    def has_change(self) -> "UpdateTask":
        if not self.model_fields_set:
            raise ValueError("At least one task property must be supplied.")
        return self


class TaskData(ApiSchema):
    content_html: str = Field(max_length=2_000_000)
    autonomy_mode: AutonomyMode = "free"
    sample_solutions: list[ModelVersionReference] = Field(default_factory=list, max_length=32)


class TaskVersionInfo(VersionInfo):
    task_id: UUID
    kind: VersionKind = "release"
    release_name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)
    workspace_languages: list[WorkspaceLanguageReference] = Field(default_factory=list, max_length=32)


class TaskVersion(TaskVersionInfo):
    data: TaskData


class CreateTaskVersion(ApiSchema):
    base_version_id: UUID | None
    kind: VersionKind = "checkpoint"
    release_name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)
    workspace_languages: list[WorkspaceLanguageReference] = Field(default_factory=list, max_length=32)
    data: TaskData

    @model_validator(mode="after")
    def valid_release_name(self) -> "CreateTaskVersion":
        if self.kind == "release" and self.release_name is None:
            raise ValueError("Ein Release benötigt einen releaseName.")
        if self.kind == "checkpoint" and self.release_name is not None:
            raise ValueError("releaseName ist nur für Releases erlaubt.")
        return self
