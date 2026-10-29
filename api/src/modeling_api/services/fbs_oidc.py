"""Token requests to the Feedbacksystem for signing in without it around the web app.

The browser only follows redirects to the Feedbacksystem.  This API exchanges
the authorization code and renews the tokens, so the browser makes no
cross-origin request there and the client secret never reaches it.
"""

from typing import Any

import httpx

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.schemas.auth import Tokens


def _client() -> dict[str, str]:
    """Client authentication as form fields; a public client sends no secret."""
    if settings.oidc_client_secret:
        return {"client_id": settings.oidc_client_id, "client_secret": settings.oidc_client_secret}
    return {"client_id": settings.oidc_client_id}


async def _request_tokens(form: dict[str, str]) -> Tokens:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {"Host": settings.oidc_token_host} if settings.oidc_token_host else {}
            response = await client.post(settings.oidc_token_uri, data={**form, **_client()}, headers=headers)
    except httpx.HTTPError as error:
        raise ApiError(503, "FBS_UNAVAILABLE", "The Feedbacksystem is currently unavailable.") from error
    # 400 is an invalid or expired code or refresh token, so the sign-in has ended.
    if response.status_code == 400:
        raise ApiError(401, "INVALID_GRANT", "The Feedbacksystem session has ended. Please sign in again.")
    # Without client authentication, e.g. a refresh without secret, it redirects to its login page.
    if response.status_code == 401 or response.is_redirect:
        raise ApiError(503, "FBS_UNAUTHORIZED", "The Feedbacksystem rejected the client credentials.")
    if response.status_code != 200:
        raise ApiError(503, "FBS_REQUEST_FAILED", "The Feedbacksystem could not issue a token.")
    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        payload = {}
    if not payload.get("access_token"):
        raise ApiError(503, "FBS_INVALID_RESPONSE", "The Feedbacksystem did not return an access token.")
    return Tokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
    )


async def exchange_code(code: str, code_verifier: str, redirect_uri: str) -> Tokens:
    return await _request_tokens(
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        }
    )


async def refresh(refresh_token: str) -> Tokens:
    return await _request_tokens({"grant_type": "refresh_token", "refresh_token": refresh_token})
