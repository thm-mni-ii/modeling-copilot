"""Gemeinsame Bausteine aller Schnittstellen.

Namen in JSON sind camelCase (z. B. createdAt), im Python-Code snake_case
(created_at) - pydantic wandeln dank alias_generator automatisch um.
"""

from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiSchema(BaseModel):
    """Grundlage aller Schemas: unbekannte Felder werden abgelehnt (422)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


# Kurze, nicht leere Texte (Namen, externe IDs, ...)
Name = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]
VersionKind = Literal["checkpoint", "release"]


def _check_json_object(value: Any) -> Any:
    """Begrenzt freie JSON-Objekte (data/annotations): max. 32 Ebenen tief,
    Arrays max. 10.000 Einträge. Der Inhalt selbst bleibt ungeprüft."""
    if not isinstance(value, dict):
        raise ValueError("Ein JSON-Objekt wird erwartet.")
    pending = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if depth > 32:
            raise ValueError("JSON ist tiefer als 32 Ebenen verschachtelt.")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > 10000:
                raise ValueError("Ein Array hat mehr als 10.000 Einträge.")
            pending.extend((child, depth + 1) for child in item)
    return value


JsonObject = Annotated[dict[str, Any], BeforeValidator(_check_json_object)]


class Identity(ApiSchema):
    """Felder eines Stammsatzes (Sprache, Aufgabe, Modell)."""

    id: UUID
    owner_id: str
    created_at: datetime


class VersionInfo(ApiSchema):
    """Felder einer Version, ohne den großen Inhaltsblock data."""

    id: UUID
    version_number: Annotated[str, BeforeValidator(str)]
    created_at: datetime
    created_by: str


class LanguageVersionReference(ApiSchema):
    """Verweist exakt auf eine Sprachversion - nie nur auf 'latest'."""

    language_id: UUID
    version_id: UUID


class TaskVersionReference(ApiSchema):
    task_id: UUID
    version_id: UUID


class ModelVersionReference(ApiSchema):
    model_id: UUID
    version_id: UUID


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Antwortform aller Listen: Treffer plus Gesamtanzahl (für skip/limit)."""

    items: list[T]
    total: int
