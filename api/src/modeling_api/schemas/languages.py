"""Schemas for modeling languages and their immutable versions."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from modeling_api.schemas.common import (
    ApiSchema,
    Identity,
    JsonObject,
    LanguageVersionReference,
    Name,
    VersionInfo,
    VersionKind,
)


class Language(Identity):
    """Modeling-language identity and latest-version metadata."""

    name: Name
    parent: LanguageVersionReference | None = Field(
        description="Language version from which this language was branched, if any."
    )
    latest_version_id: UUID | None = Field(
        description="Identifier of the latest language version, if one exists."
    )
    archived_at: datetime | None = Field(
        default=None, description="UTC archive timestamp, or null for an active language."
    )


class LanguageOverview(ApiSchema):
    """Compact language metadata for catalog listings."""

    id: UUID = Field(description="Stable language identifier.")
    name: Name
    owner_id: str = Field(description="Identifier of the language owner.")
    latest_version_id: UUID | None = Field(
        description="Identifier of the latest language version, if one exists."
    )
    latest_release_name: Name | None = Field(
        description="Name of the latest release, if one exists."
    )
    version_number: str | None = Field(
        description="Version number of the latest language version."
    )
    archived_at: datetime | None = Field(
        default=None, description="UTC archive timestamp, or null for an active language."
    )


class CreateLanguage(ApiSchema):
    """Request for a new language identity or language branch."""

    name: Name
    parent: LanguageVersionReference | None = Field(
        default=None, description="Optional source version for a language branch."
    )


class UpdateLanguage(ApiSchema):
    """Mutable language metadata; at least one field is required."""

    name: Name | None = Field(default=None, description="New language name.")
    owner_id: Name | None = Field(default=None, description="New owner identifier.")
    archived: bool | None = Field(
        default=None, description="Archive or restore the language."
    )

    @model_validator(mode="after")
    def has_change(self) -> "UpdateLanguage":
        if not self.model_fields_set:
            raise ValueError("At least one language property must be supplied.")
        return self


class LanguageVersionInfo(VersionInfo):
    """Language-version metadata without the large definition payload."""

    language_id: UUID = Field(description="Owning language identifier.")
    kind: VersionKind = "release"
    release_name: Name | None = Field(
        default=None, description="Required display name for a release."
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Optional version description."
    )
    included_language_versions: list[LanguageVersionReference] = Field(
        description="Immutable language versions included by this definition."
    )


class LanguageVersion(LanguageVersionInfo):
    """Complete immutable language version."""

    data: JsonObject = Field(description="Complete modeling-language definition.")


class CreateLanguageVersion(ApiSchema):
    """Request to append a checkpoint or release to a language."""

    base_version_id: UUID | None = Field(
        description="Current latest version for optimistic concurrency, or null initially."
    )
    kind: VersionKind = "release"
    release_name: Name | None = Field(
        default=None, description="Required display name for releases only."
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Optional version description."
    )
    included_language_versions: list[LanguageVersionReference] = Field(
        default_factory=list,
        max_length=32,
        description="Immutable language versions included by this definition.",
    )
    data: JsonObject = Field(description="Complete modeling-language definition.")

    @model_validator(mode="after")
    def valid_release_name(self) -> "CreateLanguageVersion":
        if self.kind == "release" and self.release_name is None:
            raise ValueError("A release requires releaseName.")
        if self.kind == "checkpoint" and self.release_name is not None:
            raise ValueError("releaseName is only allowed for releases.")
        return self
