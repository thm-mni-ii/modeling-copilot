"""Shared API schema building blocks.

JSON fields use camelCase while Python fields use snake_case. Pydantic applies
the conversion through the shared alias generator.
"""

from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiSchema(BaseModel):
    """Base schema that rejects unknown request fields with HTTP 422."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


Name = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        pattern=r"\S",
        description="A non-empty name with at most 256 characters.",
    ),
]
VersionKind = Annotated[
    Literal["checkpoint", "release"],
    Field(description="Whether a version is an intermediate checkpoint or a release."),
]


def _check_json_object(value: Any) -> Any:
    """Limit free-form JSON objects to 32 levels and 10,000 array entries."""
    if not isinstance(value, dict):
        raise ValueError("A JSON object is required.")
    pending = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if depth > 32:
            raise ValueError("JSON must not be nested more than 32 levels.")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > 10000:
                raise ValueError("JSON arrays must not contain more than 10,000 entries.")
            pending.extend((child, depth + 1) for child in item)
    return value


JsonObject = Annotated[
    dict[str, Any],
    BeforeValidator(_check_json_object),
    Field(description="A bounded free-form JSON object."),
]


class Identity(ApiSchema):
    """Common identity fields for languages, tasks, and models."""

    id: UUID = Field(description="Stable object identifier.")
    owner_id: str = Field(description="Identifier of the user who owns the object.")
    created_at: datetime = Field(description="UTC creation timestamp.")


class VersionInfo(ApiSchema):
    """Common version metadata without the potentially large data payload."""

    id: UUID = Field(description="Stable version identifier.")
    version_number: Annotated[
        str,
        BeforeValidator(str),
        Field(description="Human-readable semantic version number."),
    ]
    created_at: datetime = Field(description="UTC creation timestamp.")
    created_by: str = Field(description="Identifier of the user who created the version.")


class LanguageVersionReference(ApiSchema):
    """Reference to one immutable modeling-language version."""

    language_id: UUID = Field(description="Modeling-language identifier.")
    version_id: UUID = Field(description="Immutable language-version identifier.")


class TaskVersionReference(ApiSchema):
    """Reference to one immutable task release."""

    task_id: UUID = Field(description="Task identifier.")
    version_id: UUID = Field(description="Immutable task-version identifier.")


class ModelVersionReference(ApiSchema):
    """Reference to one immutable model version."""

    model_id: UUID = Field(description="Model identifier.")
    version_id: UUID = Field(description="Immutable model-version identifier.")


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T] = Field(description="Items in the requested page.")
    total: int = Field(ge=0, description="Total number of matching items.")
