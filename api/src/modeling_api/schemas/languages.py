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
        default=None, description="Optional display name for a release."
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


class ComparisonGroup(ApiSchema):
    """Direct pairwise candidate permissions within each type category."""

    id: Name
    name: Name
    element_types: list[str] = Field(default_factory=list)
    connection_types: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_types(self) -> "ComparisonGroup":
        if not self.element_types and not self.connection_types:
            raise ValueError("Comparison groups need at least two element or connection types.")
        for category, members in (("element", self.element_types), ("connection", self.connection_types)):
            if members and len(members) < 2:
                raise ValueError(f"Comparison groups need at least two {category} types per category.")
            if len(set(members)) != len(members):
                raise ValueError(f"Comparison group {category} types must be distinct.")
        return self


class LanguageEvaluationConfig(ApiSchema):
    """Versioned, language-independent model comparison configuration."""

    comparison_groups: list[ComparisonGroup]

    @model_validator(mode="after")
    def unique_group_ids(self) -> "LanguageEvaluationConfig":
        ids = [group.id for group in self.comparison_groups]
        if len(set(ids)) != len(ids):
            raise ValueError("Comparison group identifiers must be unique.")
        return self


class CreateLanguageVersion(ApiSchema):
    """Request to append a checkpoint or release to a language."""

    base_version_id: UUID | None = Field(
        description="Current latest version for optimistic concurrency, or null initially."
    )
    kind: VersionKind = "release"
    release_name: Name | None = Field(
        default=None, description="Optional display name for releases only."
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
        if self.kind == "checkpoint" and self.release_name is not None:
            raise ValueError("releaseName is only allowed for releases.")
        return self

    @model_validator(mode="after")
    def valid_evaluation(self) -> "CreateLanguageVersion":
        if "evaluation" not in self.data:
            return self
        config = LanguageEvaluationConfig.model_validate(self.data["evaluation"])
        element_types: set[str] = set()

        def collect(elements):
            if not isinstance(elements, list):
                raise ValueError("Element declarations must be a list.")
            for element in elements:
                if not isinstance(element, dict) or not isinstance(element.get("type"), str):
                    raise ValueError("Element declarations must have a type identifier.")
                element_types.add(element["type"])
                collect(element.get("children", []))

        collect(self.data.get("elements", []))
        connections = self.data.get("connections", [])
        if not isinstance(connections, list) or any(
            not isinstance(connection, dict) or not isinstance(connection.get("type"), str)
            for connection in connections
        ):
            raise ValueError("Connection declarations must be a list with type identifiers.")
        connection_types = {connection["type"] for connection in connections}
        for group in config.comparison_groups:
            if not set(group.element_types) <= element_types:
                raise ValueError("Comparison groups must reference declared element types, including child types.")
            if not set(group.connection_types) <= connection_types:
                raise ValueError("Comparison groups must reference declared connection types.")
        return self
