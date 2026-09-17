"""Public bearer-token inspection endpoints."""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials

from modeling_api.core.auth import bearer, get_claims, is_token_valid

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/validate",
    summary="Validate a bearer token",
    description=(
        "Returns `true` when the optional bearer token is valid and `false` otherwise. "
        "This endpoint never requires authentication."
    ),
    response_description="Whether the supplied token is valid.",
)
async def validate_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> bool:
    if credentials is None:
        return False
    return is_token_valid(credentials.credentials)


@router.get(
    "/me",
    summary="Get token claims",
    description="Validates the bearer token and returns all claims from its payload.",
    response_description="The authenticated token claims.",
)
async def get_me(claims: dict = Depends(get_claims)) -> dict:
    return claims
