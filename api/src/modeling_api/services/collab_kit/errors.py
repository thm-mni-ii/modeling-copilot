"""Die Fehler des Collab-Teils, als `ApiError` wie im übrigen Backend ({code, message}).

| Code               | Status    | Wann                                                                  |
|--------------------|-----------|-----------------------------------------------------------------------|
| SHARING_DISABLED   | 503       | Die Service-Identität fehlt in der Konfiguration; die Jobs enden daran |
| CK_UNAVAILABLE     | 503       | Collab-Kit (CK) ist nicht erreichbar                                  |
| CK_REQUEST_FAILED  | 502       | CK lehnt eine Anfrage ab (außer 404)                                  |
| NOT_FOUND          | 404       | Raum, Gruppe oder Share fehlt (`core.errors.not_found`)               |
| SHARE_CLOSED       | 403 / 409 | Der Host teilt nicht (403 beim Beitreten, sonst 409) oder der Link    |
|                    |           | ist für neue Besucher zu (403)                                        |
| SHARE_INVALID      | 409       | Die Share eines Raums passt nicht zu ihren Gruppen                    |
| ARCHIVE_DISABLED   | 409       | Ein Kurs soll ins Archiv, das Archiv ist aber aus                     |
"""

from modeling_api.core.errors import ApiError

# Daran enden Sweep und Archiv-Job, wenn auf diesem Server nicht geteilt wird.
SHARING_DISABLED = "SHARING_DISABLED"


def sharing_disabled() -> ApiError:
    return ApiError(503, SHARING_DISABLED, "Sharing is not configured on this server.")


def ck_unavailable() -> ApiError:
    return ApiError(503, "CK_UNAVAILABLE", "Collab-Kit is currently unavailable.")


def ck_request_failed(status: int, reason: str) -> ApiError:
    return ApiError(502, "CK_REQUEST_FAILED", f"Collab-Kit refused the request ({status}): {reason}")


def not_sharing(status: int = 409) -> ApiError:
    """Der Host teilt gerade nicht; beim Beitreten ist das ein 403, bei Aktionen des Hosts ein 409."""
    return ApiError(status, "SHARE_CLOSED", "The host is not sharing in this room.")


def link_closed() -> ApiError:
    return ApiError(403, "SHARE_CLOSED", "The host has closed the link for new visitors.")


def share_invalid() -> ApiError:
    return ApiError(409, "SHARE_INVALID", "The share of this room is inconsistent.")


def archive_disabled() -> ApiError:
    return ApiError(409, "ARCHIVE_DISABLED", "The archive is turned off in the collab settings.")
