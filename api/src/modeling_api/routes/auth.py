"""Public endpoints to inspect bearer tokens and to sign in without the Feedbacksystem."""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials

from modeling_api.core.auth import bearer, get_claims, is_token_valid
from modeling_api.schemas.auth import CodeExchange, TokenRefresh, Tokens
from modeling_api.services import fbs_oidc

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
# Sync on purpose: FastAPI runs it in a worker thread, so fetching the issuer's
# keys on a cache miss does not block the event loop.
def validate_token(
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


@router.post(
    "/token",
    summary="Exchange a sign-in code",
    description=(
        "Exchanges the authorization code of a sign-in without the Feedbacksystem around "
        "the web app for tokens at the Feedbacksystem. This endpoint never requires authentication."
    ),
    response_description="The access token and, for a confidential client, a refresh token.",
)
async def exchange_code(body: CodeExchange) -> Tokens:
    return await fbs_oidc.exchange_code(body.code, body.code_verifier, body.redirect_uri)


@router.post(
    "/refresh",
    summary="Renew the tokens",
    description=(
        "Renews the tokens at the Feedbacksystem with the refresh token of an earlier "
        "exchange. This endpoint never requires authentication."
    ),
    response_description="The new tokens.",
)
async def refresh_tokens(body: TokenRefresh) -> Tokens:
    return await fbs_oidc.refresh(body.refresh_token)
