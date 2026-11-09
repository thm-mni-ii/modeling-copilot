"""Resolve display names through the FBS REST API using the caller's permissions."""

import asyncio
from collections.abc import Iterable
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

import httpx

from modeling_api.core.auth import User
from modeling_api.core.config import settings
from modeling_api.db.client import db
from modeling_api.db.store import utcnow


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


async def resolve_names(
    identifiers: Iterable[str], user: User, token: str | None = None
) -> dict[str, str]:
    ids = set(identifiers)
    cached = {
        item["_id"]: item
        for item in await db.submission_users.find({"_id": {"$in": list(ids)}}).to_list(
            None
        )
    }
    names = {
        identifier: cached.get(identifier, {}).get("fbsName")
        or cached.get(identifier, {}).get("name")
        or identifier
        for identifier in ids
    }
    if not token:
        return names
    privileged = (
        user.is_admin or user.global_role == "MODERATOR" or "MODERATOR" in user.roles
    )
    cutoff = utcnow() - timedelta(minutes=15)
    pending = sorted(
        identifier
        for identifier in ids
        if identifier.isdecimal()
        and (privileged or identifier == user.id)
        and (
            "email" not in cached.get(identifier, {})
            or not cached.get(identifier, {}).get("nameResolvedAt")
            or cached[identifier]["nameResolvedAt"] < cutoff
        )
    )
    if not pending:
        return names
    headers = {"Authorization": f"Bearer {token}"}
    if not settings.fbs_users_uri and settings.oidc_token_host:
        headers["Host"] = settings.oidc_token_host
    semaphore = asyncio.Semaphore(6)
    unavailable = False
    async with httpx.AsyncClient(
        timeout=4, headers=headers, follow_redirects=False
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
                    email = profile.get("email")
                    email = email.strip()[:320] if isinstance(email, str) else None
                except (httpx.HTTPError, ValueError, TypeError):
                    unavailable = True
                    return False
                if name == identifier and not email:
                    return False
                names[identifier] = name
                await db.submission_users.update_one(
                    {"_id": identifier},
                    {
                        "$set": {
                            "name": name,
                            "fbsName": name,
                            "email": email,
                            "nameResolvedAt": utcnow(),
                        }
                    },
                    upsert=True,
                )
                return True

        # An unavailable or forbidden FBS should cost one request, not one timeout per user.
        if await resolve(pending[0]):
            await asyncio.gather(*(resolve(identifier) for identifier in pending[1:]))
    return names
