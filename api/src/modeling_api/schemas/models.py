"""Schemas for models, model versions, and task edits."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from modeling_api.schemas.common import (
    ApiSchema,
    Identity,
    JsonObject,
    LanguageVersionReference,
    Name,
    TaskVersionReference,
    VersionInfo,
    VersionKind,
)

ModelSortField = Literal["updatedAt", "createdAt", "name"]
SortOrder = Literal["asc", "desc"]


class TaskEditDocument(ApiSchema):
    """Current user-authored formatting and text additions for a model task."""

    schema_version: Literal[1] = Field(
        default=1,
        description="Task-edit document format version.",
    )
    revision: int = Field(
        ge=0,
        description="Monotonically increasing revision used for optimistic concurrency.",
    )
    updated_at: datetime = Field(description="UTC timestamp of the latest successful update.")
    document: JsonObject = Field(
        description="Tiptap JSON containing the immutable task text and user edits."
    )


class UpdateTaskEdit(ApiSchema):
    """Optimistic-concurrency request for replacing the current task-edit document."""

    base_revision: int = Field(
        ge=0,
        description="Revision edited by the client; a stale revision returns HTTP 409.",
    )
    document: JsonObject = Field(description="Complete replacement Tiptap JSON document.")


class Model(Identity):
    """Model identity and mutable metadata."""

    name: Name
    latest_version_id: UUID | None = Field(
        description="Identifier of the latest model version, if one exists."
    )
    task_version: TaskVersionReference | None = Field(
        default=None,
        description="Immutable task release assigned when the model is created.",
    )
    task_edit: TaskEditDocument | None = Field(
        default=None,
        description="Current task edits, independent from model-version restoration.",
    )
    preferences: JsonObject = Field(default_factory=dict)
    updated_at: datetime = Field(description="UTC timestamp of the latest model update.")
    archived_at: datetime | None = Field(
        default=None, description="UTC archive timestamp, or null for an active model."
    )


class CreateModel(ApiSchema):
    """Create a model identity before its first model version is saved."""

    name: Name
    task_version: TaskVersionReference | None = Field(
        default=None,
        description="Optional task release permanently assigned to the model.",
    )


class UpdateModel(ApiSchema):
    """Mutable model metadata; model-version snapshots remain immutable."""

    name: Name | None = Field(default=None, description="New model name.")
    archived: bool | None = Field(default=None, description="Archive or restore the model.")
    preferences: JsonObject | None = Field(
        default=None, description="Complete replacement model preferences."
    )

    @model_validator(mode="after")
    def has_change(self) -> "UpdateModel":
        if not self.model_fields_set:
            raise ValueError("At least one model property must be supplied.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name must not be null.")
        if "archived" in self.model_fields_set and self.archived is None:
            raise ValueError("archived must be true or false.")
        if "preferences" in self.model_fields_set and self.preferences is None:
            raise ValueError("preferences must be an object.")
        return self


class WorkspaceLanguageReference(LanguageVersionReference):
    """Directly selected language; transitive dependencies remain implicit."""

    source: Literal["required", "additional"] = Field(
        description="Whether the task requires the language or the model author added it."
    )


class ModelPatch(ApiSchema):
    created_at: datetime = Field(description="UTC timestamp at which the patch was created.")
    xml: str = Field(
        min_length=1,
        max_length=2_000_000,
        description="Validated XML operations for one local model change.",
    )


class ModelVersionInfo(VersionInfo):
    """Model-version metadata returned by version lists."""

    model_id: UUID = Field(description="Owning model identifier.")
    base_release_id: UUID | None = Field(
        default=None, description="Release on which this checkpoint is based."
    )
    patches: list[ModelPatch] = Field(
        default_factory=list, description="Ordered XML patches stored by a checkpoint."
    )
    workspace_languages: list[WorkspaceLanguageReference] = Field(
        default_factory=list, description="Direct language versions used by the workspace."
    )
    task_version: TaskVersionReference | None = Field(
        description="Immutable task release assigned to this model, if any."
    )
    kind: VersionKind = "checkpoint"
    release_name: Name | None = Field(
        default=None, description="Required display name for releases."
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Optional version description."
    )


class ModelVersion(ModelVersionInfo):
    """Complete, materialized model version."""

    data: JsonObject = Field(description="Complete materialized model and editor state.")
    task_edit_snapshot: TaskEditDocument | None = Field(
        default=None,
        description="Read-only copy of task edits captured with this model version.",
    )


class CreateModelVersion(ApiSchema):
    """Create the next model checkpoint or release."""

    base_version_id: UUID | None = Field(
        description="Current latest version for optimistic concurrency, or null initially."
    )
    base_release_id: UUID | None = Field(
        default=None, description="Release on which a checkpoint is based."
    )
    workspace_languages: list[WorkspaceLanguageReference] = Field(
        default_factory=list,
        max_length=32,
        description="Direct language versions used by the workspace.",
    )
    task_version: TaskVersionReference | None = Field(
        default=None, description="Immutable task release assigned to this model."
    )
    data: JsonObject = Field(description="Complete model state for a release or non-XML state for a checkpoint.")
    patches: list[ModelPatch] = Field(
        default_factory=list,
        max_length=10_000,
        description="Ordered XML patches for a checkpoint; releases must leave this empty.",
    )
    kind: VersionKind = "checkpoint"
    release_name: Name | None = Field(
        default=None, description="Required display name for releases."
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Optional version description."
    )

    @model_validator(mode="after")
    def validate_version(self) -> "CreateModelVersion":
        if self.kind == "release" and self.release_name is None:
            raise ValueError("A release requires releaseName.")
        if self.kind == "checkpoint" and self.release_name is not None:
            raise ValueError("releaseName is only allowed for releases.")
        if self.kind == "release":
            if self.base_release_id is not None or self.patches:
                raise ValueError("A release must not contain baseReleaseId or patches.")
            if not isinstance(self.data.get("xml"), str) or not self.data["xml"].strip():
                raise ValueError("A release requires complete data.xml content.")
        elif "xml" in self.data:
            raise ValueError("A checkpoint must not contain data.xml.")
        direct_refs = {
            (str(item.language_id), str(item.version_id))
            for item in self.workspace_languages
        }
        if len(direct_refs) != len(self.workspace_languages):
            raise ValueError("workspaceLanguages contains a duplicate language version.")
        return self
