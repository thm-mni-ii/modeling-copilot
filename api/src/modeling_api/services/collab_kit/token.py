"""Dienst-Token für Collab-Kit (CK).

Die API prägt ihre Tokens selbst und signiert sie mit dem privaten Schlüssel; CK prüft sie
mit dem öffentlichen. Damit legt sie Räume und Gruppen an, ohne dass ein Nutzer dafür
Rechte braucht. Das Token liegt nur im Backend.
"""

import time

import jwt

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError

# CK nimmt Dienst-Tokens nur höchstens 10 Minuten im Voraus an.
LIFETIME_SECONDS = 300
# So lange vor Ablauf wird ein neues geprägt, damit kein Aufruf mit einem fast abgelaufenen startet.
RENEW_BEFORE_SECONDS = 60
# Name, den CK anzeigt, wenn der Dienst etwas anlegt.
LABEL = "Modeling Copilot"

# Das zuletzt geprägte Token mit seinem Ablauf.
_token: str | None = None
_expires_at = 0


def _now() -> int:
    return int(time.time())


def _mint() -> tuple[str, int]:
    """Prägt ein neues Token; ohne vollständige Einstellungen ist das Teilen ausgeschaltet."""
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
        # Secrets in Umgebungsvariablen haben die Zeilenumbrüche oft als \n.
        settings.service_private_key.replace("\\n", "\n"),
        algorithm=settings.service_algorithm,
    )
    return token, expires_at


def service_token() -> str:
    """Ein gültiges Dienst-Token; es wird erst kurz vor Ablauf erneuert."""
    global _token, _expires_at
    if _token is None or _now() >= _expires_at - RENEW_BEFORE_SECONDS:
        _token, _expires_at = _mint()
    return _token
