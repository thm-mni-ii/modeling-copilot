"""Service token for Collab-Kit (CK).

The API mints its tokens itself and signs them with the private key; CK checks them with the
public one. With it the API creates rooms and groups without a user needing rights for that.
The token stays in the backend only.
"""

import time

import jwt

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError

# CK accepts service tokens at most 10 minutes ahead.
LIFETIME_SECONDS = 300
# A new one is minted this long before expiry, so that no call starts with an almost expired one.
RENEW_BEFORE_SECONDS = 60
# Name that CK shows when the service creates something.
LABEL = "Modeling Copilot"

# The most recently minted token with its expiry.
_token: str | None = None
_expires_at = 0


def _now() -> int:
    return int(time.time())


def _mint() -> tuple[str, int]:
    """Mints a new token; without complete settings sharing is switched off."""
    if not (
        settings.service_issuer
        and settings.service_algorithm
        and settings.service_actor
        and settings.service_private_key
    ):
        raise ApiError(503, "SHARING_DISABLED", "Sharing is not configured on this server.")
    issued_at = _now()
    expires_at = issued_at + LIFETIME_SECONDS
    token = jwt.encode(
        {
            "iss": settings.service_issuer,
            "sub": settings.service_actor,
            "name": LABEL,
            "iat": issued_at,
            "exp": expires_at,
        },
        # Secrets in environment variables often have their line breaks as \n.
        settings.service_private_key.replace("\\n", "\n"),
        algorithm=settings.service_algorithm,
    )
    return token, expires_at


def service_token() -> str:
    """A valid service token; it is renewed only shortly before expiry."""
    global _token, _expires_at
    if _token is None or _now() >= _expires_at - RENEW_BEFORE_SECONDS:
        _token, _expires_at = _mint()
    return _token
