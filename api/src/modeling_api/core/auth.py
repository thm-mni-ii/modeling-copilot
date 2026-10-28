"""JWT authentication for protected API endpoints.

Tokens are issued by an external identity system. This API validates their
signature against the issuer's published keys (or a shared secret for HS
algorithms), their expiry and optionally issuer and audience, then reads the
configured user and role claims.
"""

from dataclasses import dataclass, field
from functools import cache

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError

bearer = HTTPBearer(
    auto_error=False,
    description="JWT issued by the configured external identity system.",
)


@dataclass(frozen=True)
class User:
    """Authenticated actor with the user identifier and optional roles."""

    id: str
    roles: list[str] = field(default_factory=list)
    global_role: str | None = None

    @property
    def is_admin(self) -> bool:
        """Whether the user is a global Modeling Copilot administrator."""
        return self.global_role == "ADMIN"


@cache
def _jwks_client() -> jwt.PyJWKClient:
    """Shared client that fetches the issuer's keys on first use and caches them."""
    return jwt.PyJWKClient(settings.jwt_jwks_uri)


def _signing_key(token: str) -> object:
    """Return the shared secret for HS algorithms, else the issuer key named by the token."""
    if settings.jwt_algorithm.startswith("HS"):
        return settings.jwt_secret
    # Refused before the lookup, so a token signed otherwise never triggers a key fetch.
    if jwt.get_unverified_header(token).get("alg") != settings.jwt_algorithm:
        raise jwt.InvalidAlgorithmError("The token is signed with another algorithm.")
    return _jwks_client().get_signing_key_from_jwt(token).key


def _decode_claims(token: str) -> dict:
    """Validate signature, expiry, issuer and audience, raising PyJWTError on failure."""
    audience = [value.strip() for value in settings.jwt_audience.split(",") if value.strip()]
    return jwt.decode(
        token,
        _signing_key(token),
        # Pinned from the configuration, never taken from the token header.
        algorithms=[settings.jwt_algorithm],
        audience=audience or None,
        issuer=settings.jwt_issuer or None,
        leeway=settings.jwt_leeway_seconds,
        # PyJWT rejects any token carrying aud unless the check is switched off.
        options={"require": ["exp", settings.jwt_user_claim], "verify_aud": bool(audience)},
    )


def is_token_valid(token: str) -> bool:
    """Return whether a token can be decoded and validated."""
    try:
        _decode_claims(token)
    except jwt.PyJWTError:
        return False
    return True


def get_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    """Validate the request token and return the authenticated user."""
    if credentials is None:
        raise ApiError(401, "INVALID_TOKEN", "A valid bearer token is required.")
    try:
        claims = _decode_claims(credentials.credentials)
    except jwt.PyJWTError:
        raise ApiError(401, "INVALID_TOKEN", "A valid bearer token is required.") from None
    roles = claims.get(settings.jwt_roles_claim) or []
    global_role = claims.get(settings.jwt_global_role_claim)
    return User(
        id=str(claims[settings.jwt_user_claim]),
        roles=list(roles),
        global_role=str(global_role) if global_role is not None else None,
    )


def get_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """Validate the request token and return all unchanged token claims."""
    if credentials is None:
        raise ApiError(401, "INVALID_TOKEN", "A valid bearer token is required.")
    try:
        return _decode_claims(credentials.credentials)
    except jwt.PyJWTError:
        raise ApiError(401, "INVALID_TOKEN", "A valid bearer token is required.") from None
