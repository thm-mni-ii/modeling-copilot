"""Schemas für Modelle und ihre Speicherstände (Versionen)."""

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
class Model(Identity):
    name: Name
    latest_version_id: UUID | None
    task_version: TaskVersionReference | None = None
    preferences: JsonObject = Field(default_factory=dict)
    updated_at: datetime
    archived_at: datetime | None = None


class CreateModel(ApiSchema):
    name: Name
    task_version: TaskVersionReference | None = None


class UpdateModel(ApiSchema):
    """Mutable metadata of a model. Snapshots themselves stay immutable."""

    name: Name | None = None
    archived: bool | None = None
    preferences: JsonObject | None = None

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
    """A directly selected language; transitive dependencies stay implicit here."""

    source: Literal["required", "additional"]


class ModelPatch(ApiSchema):
    created_at: datetime
    xml: str = Field(min_length=1, max_length=2_000_000)


class ModelVersionInfo(VersionInfo):
    model_id: UUID
    base_release_id: UUID | None = None
    patches: list[ModelPatch] = Field(default_factory=list)
    workspace_languages: list[WorkspaceLanguageReference] = Field(default_factory=list)
    task_version: TaskVersionReference | None
    kind: VersionKind = "checkpoint"
    release_name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)


class ModelVersion(ModelVersionInfo):
    data: JsonObject  # vollständiger Modellinhalt, ggf. inkl. Editor-Einstellungen
    annotations: JsonObject | None  # persönliche Markierungen/Notizen zur Aufgabe


class CreateModelVersion(ApiSchema):
    base_version_id: UUID | None
    base_release_id: UUID | None = None
    workspace_languages: list[WorkspaceLanguageReference] = Field(default_factory=list, max_length=32)
    task_version: TaskVersionReference | None = None
    data: JsonObject
    patches: list[ModelPatch] = Field(default_factory=list, max_length=10_000)
    annotations: JsonObject | None = None
    kind: VersionKind = "checkpoint"
    release_name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def annotations_only_with_task(self) -> "CreateModelVersion":
        # Ohne Aufgabenbezug gibt es nichts, worauf sich Anmerkungen beziehen könnten.
        if self.task_version is None and self.annotations is not None:
            raise ValueError("annotations erfordert eine taskVersion.")
        if self.kind == "release" and self.release_name is None:
            raise ValueError("Ein Release benötigt einen releaseName.")
        if self.kind == "checkpoint" and self.release_name is not None:
            raise ValueError("releaseName ist nur für Releases erlaubt.")
        if self.kind == "release":
            if self.base_release_id is not None or self.patches:
                raise ValueError("Ein Release darf weder baseReleaseId noch Patches enthalten.")
            if not isinstance(self.data.get("xml"), str) or not self.data["xml"].strip():
                raise ValueError("Ein Release benötigt vollständiges data.xml.")
        elif "xml" in self.data:
            raise ValueError("Ein Checkpoint darf kein data.xml enthalten.")
        direct_refs = {(str(item.language_id), str(item.version_id)) for item in self.workspace_languages}
        if len(direct_refs) != len(self.workspace_languages):
            raise ValueError("workspaceLanguages enthält eine Sprachversion mehrfach.")
        return self
