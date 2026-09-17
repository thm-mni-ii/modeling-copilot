"""HTTP endpoints for modeling languages and their immutable versions."""

from uuid import UUID

from fastapi import APIRouter, Query, Response

from modeling_api.routes.deps import CurrentUser, Limit, Skip, created_response
from modeling_api.schemas.common import Page
from modeling_api.schemas.languages import (
    CreateLanguage,
    CreateLanguageVersion,
    Language,
    LanguageOverview,
    LanguageVersion,
    LanguageVersionInfo,
    UpdateLanguage,
)
from modeling_api.services import languages as service

router = APIRouter(prefix="/languages", tags=["Languages"])


@router.get(
    "",
    summary="List modeling languages",
    description=(
        "Returns the global language catalog. Archived languages are excluded by default, "
        "and large version data is not embedded in this overview."
    ),
    response_description="A paginated language overview.",
)
async def list_languages(
    user: CurrentUser,
    skip: Skip = 0,
    limit: Limit = 20,
    q: str | None = Query(
        default=None, max_length=256, description="Case-insensitive language-name search."
    ),
    archived: bool = Query(default=False, description="Return archived languages."),
) -> Page[LanguageOverview]:
    return Page[LanguageOverview].model_validate(
        await service.list_languages(skip, limit, q, archived)
    )


@router.post(
    "",
    status_code=201,
    summary="Create a modeling language",
    description=(
        "Creates the language identity. Use the versions endpoint to add its first immutable definition."
    ),
    response_description="The created language identity.",
)
async def create_language(
    body: CreateLanguage, response: Response, user: CurrentUser
) -> Language:
    result = await service.create_language(body, user)
    created_response(response, result, "languages")
    return Language.model_validate(result)


@router.get(
    "/{language_id}",
    summary="Get a modeling language",
    description="Returns one language identity and its latest-version metadata.",
    response_description="The requested language.",
)
async def get_language(language_id: UUID, user: CurrentUser) -> Language:
    return Language.model_validate(await service.get_language(language_id))


@router.patch(
    "/{language_id}",
    summary="Update language metadata",
    description="Updates mutable language metadata. Immutable versions are never modified.",
    response_description="The updated language.",
)
async def update_language(
    language_id: UUID, body: UpdateLanguage, user: CurrentUser
) -> Language:
    return Language.model_validate(await service.update_language(language_id, body, user))


@router.get(
    "/{language_id}/versions",
    summary="List language versions",
    description="Returns immutable version metadata without the large language definition.",
    response_description="A paginated list of language-version metadata.",
)
async def list_versions(
    language_id: UUID, user: CurrentUser, skip: Skip = 0, limit: Limit = 20
) -> Page[LanguageVersionInfo]:
    return Page[LanguageVersionInfo].model_validate(
        await service.list_versions(language_id, skip, limit)
    )


@router.post(
    "/{language_id}/versions",
    status_code=201,
    summary="Create a language version",
    description=(
        "Appends an immutable checkpoint or release to a language using optimistic base-version concurrency."
    ),
    response_description="The created language version, including its definition.",
)
async def create_version(
    language_id: UUID, body: CreateLanguageVersion, user: CurrentUser
) -> LanguageVersion:
    result = await service.create_version(language_id, body, user)
    return LanguageVersion.model_validate(result)


@router.get(
    "/{language_id}/versions/{version_id}",
    summary="Get a language version",
    description="Returns one immutable language version including its complete definition.",
    response_description="The requested language version.",
)
async def get_version(
    language_id: UUID, version_id: UUID, user: CurrentUser
) -> LanguageVersion:
    return LanguageVersion.model_validate(
        await service.get_version(language_id, version_id)
    )
