"""Schemas for shared tasks and their immutable versions."""

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
TaskVisibility = Literal["private", "published"]


class Task(Identity):
    """Task identity and publication metadata."""

    name: Name
    parent: TaskVersionReference | None = Field(
        default=None,
        description="Task version from which this task was branched.",
    )
    latest_version_id: UUID | None = Field(description="Latest checkpoint or release identifier.")
    latest_release_id: UUID | None = Field(
        default=None,
        description="Latest released task version available to model authors.",
    )
    latest_release_created_by: str | None = Field(
        default=None,
        description="User identifier of the latest release author.",
    )
    visibility: TaskVisibility = Field(
        default="private",
        description="Whether the task is private to administrators or published.",
    )
    archived_at: datetime | None = Field(
        default=None,
        description="UTC archive timestamp, or null for active tasks.",
    )


class CreateTask(ApiSchema):
    """Create an empty task or branch from an existing task version."""

    name: Name
    parent: TaskVersionReference | None = Field(
        default=None,
        description="Optional task version copied into the new task as its first checkpoint.",
    )


class UpdateTask(ApiSchema):
    """Update mutable task metadata."""

    name: Name | None = Field(default=None, description="New task name.")
    archived: bool | None = Field(default=None, description="Archive or restore the task.")
    visibility: TaskVisibility | None = Field(
        default=None, description="New catalog visibility."
    )

    @model_validator(mode="after")
    def has_change(self) -> "UpdateTask":
        if not self.model_fields_set:
            raise ValueError("At least one task property must be supplied.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name must not be null.")
        if "archived" in self.model_fields_set and self.archived is None:
            raise ValueError("archived must be true or false.")
        if "visibility" in self.model_fields_set and self.visibility is None:
            raise ValueError("visibility must not be null.")
        return self


class TaskData(ApiSchema):
    """Versioned task content and modeling constraints."""

    content_html: str = Field(
        max_length=2_000_000,
        description="Task text serialized as Tiptap-compatible HTML.",
    )
    autonomy_mode: AutonomyMode = Field(
        default="free",
        description="Modeling assistance mode enforced for models created from the task.",
    )
    sample_solutions: list[ModelVersionReference] = Field(
        default_factory=list,
        max_length=32,
        description="Released model versions exposed as sample solutions.",
    )


class TaskVersionInfo(VersionInfo):
    """Task-version metadata returned by version lists."""

    task_id: UUID = Field(description="Task identity owning this version.")
    kind: VersionKind = "release"
    release_name: Name | None = Field(
        default=None,
        description="Required display name for releases.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional release notes.",
    )
    workspace_languages: list[WorkspaceLanguageReference] = Field(
        default_factory=list,
        max_length=32,
        description="Modeling-language versions required by this task version.",
    )


class TaskVersion(TaskVersionInfo):
    """Complete immutable task version."""

    data: TaskData = Field(description="Versioned task content and modeling constraints.")


class CreateTaskVersion(ApiSchema):
    """Create the next checkpoint or release of a task."""

    base_version_id: UUID | None = Field(
        description="Current latest version identifier, or null for the first version."
    )
    kind: VersionKind = "checkpoint"
    release_name: Name | None = Field(
        default=None,
        description="Required for releases and omitted for checkpoints.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional release notes.",
    )
    workspace_languages: list[WorkspaceLanguageReference] = Field(
        default_factory=list,
        max_length=32,
        description="Modeling-language versions required by the task.",
    )
    data: TaskData = Field(description="Versioned task content and modeling constraints.")

    @model_validator(mode="after")
    def valid_release_name(self) -> "CreateTaskVersion":
        if self.kind == "release" and self.release_name is None:
            raise ValueError("A release requires releaseName.")
        if self.kind == "checkpoint" and self.release_name is not None:
            raise ValueError("releaseName is only allowed for releases.")
        return self
