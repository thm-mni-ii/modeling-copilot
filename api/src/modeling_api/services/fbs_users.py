"""Resolve display names through the FBS REST API using the caller's permissions."""

import asyncio
from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit

import httpx

from modeling_api.core.auth import User
from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError


def display_name(profile: dict, fallback: str) -> str:
    full = " ".join(
        str(profile.get(key) or "").strip() for key in ("prename", "surname")
    ).strip()
    return (
        full
        or str(
            profile.get("name")
            or profile.get("username")
            or profile.get("preferred_username")
            or fallback
        ).strip()
        or fallback
    )[:256]


def users_uri() -> str:
    if settings.fbs_users_uri:
        return settings.fbs_users_uri.rstrip("/")
    origin = urlsplit(settings.oidc_token_uri)
    return urlunsplit((origin.scheme, origin.netloc, "/api/v1/users", "", ""))


def _headers(token: str | None) -> dict[str, str]:
    """Bearer token of the caller; behind Docker also the public host."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if not settings.fbs_users_uri and settings.oidc_token_host:
        headers["Host"] = settings.oidc_token_host
    return headers


async def ids_by_username(token: str | None) -> dict[str, str]:
    """Username → ID of all FBS accounts, with the caller's token; the FBS lists them only for admins, moderators and lecturers."""
    try:
        async with httpx.AsyncClient(timeout=10, headers=_headers(token), follow_redirects=False) as http:
            response = await http.get(users_uri())
    except httpx.HTTPError as error:
        raise ApiError(502, "FBS_UNAVAILABLE", "The Feedbacksystem could not be reached.") from error
    if response.status_code in (401, 403):
        raise ApiError(403, "FBS_FORBIDDEN", "The Feedbacksystem does not list its users for you.")
    if response.status_code != 200:
        raise ApiError(502, "FBS_UNAVAILABLE", "The Feedbacksystem did not list its users.")
    return {
        str(user["username"]): str(user["id"])
        for user in response.json()
        if isinstance(user, dict) and user.get("username") and user.get("id") is not None
    }


async def resolve_names(
    identifiers: Iterable[str], user: User, token: str | None = None
) -> dict[str, str]:
    ids = set(identifiers)
    # Profiles exist only for this response, never in a database or shared cache.
    names = {identifier: identifier for identifier in ids}
    if not token or not user.is_admin:
        return names
    pending = sorted(identifier for identifier in ids if identifier.isdecimal())
    if not pending:
        return names
    semaphore = asyncio.Semaphore(6)
    unavailable = False
    async with httpx.AsyncClient(
        timeout=4, headers=_headers(token), follow_redirects=False
    ) as client:

        async def resolve(identifier: str) -> bool:
            nonlocal unavailable
            async with semaphore:
                if unavailable:
                    return False
                try:
                    response = await client.get(f"{users_uri()}/{identifier}")
                    if response.status_code == 404:
                        return True
                    if response.status_code != 200:
                        unavailable = True
                        return False
                    profile = response.json()
                    if (
                        not isinstance(profile, dict)
                        or str(profile.get("id")) != identifier
                    ):
                        return False
                    name = display_name(profile, identifier)
                except (httpx.HTTPError, ValueError, TypeError):
                    unavailable = True
                    return False
                names[identifier] = name
                return True

        # An unavailable or forbidden FBS should cost one request, not one timeout per user.
        if await resolve(pending[0]):
            await asyncio.gather(*(resolve(identifier) for identifier in pending[1:]))
    return names
