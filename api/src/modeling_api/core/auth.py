"""JWT authentication for protected API endpoints.

Tokens are issued by an external identity system. This API validates their
signature and expiry, then reads the configured user and role claims.
"""

from dataclasses import dataclass, field

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


def _decode_claims(token: str) -> dict:
    """Validate signature and expiry, raising PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        options={"require": ["exp", settings.jwt_user_claim]},
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
