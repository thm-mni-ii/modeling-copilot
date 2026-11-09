"""Shared route dependencies, pagination parameters, and response helpers."""

from typing import Annotated

from fastapi import Depends, Query, Response
from fastapi.security import HTTPAuthorizationCredentials

from modeling_api.core.auth import User, get_user, bearer
from modeling_api.db.store import Document

CurrentUser = Annotated[User, Depends(get_user)]


def forwarded_bearer(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str | None:
    return credentials.credentials if credentials else None


CurrentBearer = Annotated[str | None, Depends(forwarded_bearer)]
Skip = Annotated[int, Query(ge=0, description="Number of matching items to skip.")]
Limit = Annotated[
    int,
    Query(ge=1, le=100, description="Maximum number of items to return."),
]


def created_response(
    response: Response, result: Document, path: str, created: bool = True
) -> None:
    """Set creation status and Location, or HTTP 200 for an idempotent replay."""
    response.status_code = 201 if created else 200
    response.headers["Location"] = f"/v1/{path}/{result['id']}"
