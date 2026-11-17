"""The errors of the collab part, as `ApiError` like in the rest of the backend ({code, message}).

| Code               | Status    | When                                                                  |
|--------------------|-----------|-----------------------------------------------------------------------|
| SHARING_DISABLED   | 503       | The service identity is missing from the config; the jobs end on it   |
| CK_UNAVAILABLE     | 503       | Collab-Kit (CK) cannot be reached                                     |
| CK_REQUEST_FAILED  | 502       | CK refuses a request (except 404)                                     |
| NOT_FOUND          | 404       | Room, group or share is missing (`core.errors.not_found`)             |
| SHARE_CLOSED       | 403 / 409 | The host is not sharing (403 on join, 409 otherwise) or the link      |
|                    |           | is closed for new visitors (403)                                      |
| SHARE_INVALID      | 409       | The share of a room does not match its groups                         |
| ARCHIVE_DISABLED   | 409       | A course should be archived, but the archive is off                   |
"""

from modeling_api.core.errors import ApiError

# Sweep and archive job end on this when sharing is not configured on this server.
SHARING_DISABLED = "SHARING_DISABLED"


def sharing_disabled() -> ApiError:
    return ApiError(503, SHARING_DISABLED, "Sharing is not configured on this server.")


def ck_unavailable() -> ApiError:
    return ApiError(503, "CK_UNAVAILABLE", "Collab-Kit is currently unavailable.")


def ck_request_failed(status: int, reason: str) -> ApiError:
    return ApiError(502, "CK_REQUEST_FAILED", f"Collab-Kit refused the request ({status}): {reason}")


def not_sharing(status: int = 409) -> ApiError:
    """The host is not sharing right now; a 403 when joining, a 409 for actions of the host."""
    return ApiError(status, "SHARE_CLOSED", "The host is not sharing in this room.")


def link_closed() -> ApiError:
    return ApiError(403, "SHARE_CLOSED", "The host has closed the link for new visitors.")


def share_invalid() -> ApiError:
    return ApiError(409, "SHARE_INVALID", "The share of this room is inconsistent.")


def archive_disabled() -> ApiError:
    return ApiError(409, "ARCHIVE_DISABLED", "The archive is turned off in the collab settings.")
