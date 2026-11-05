"""Einstellungen der API, gelesen aus Umgebungsvariablen bzw. der Datei .env."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Erlaubte Signaturverfahren; "none" fehlt bewusst, sonst gälten unsignierte Token.
JwtAlgorithm = Literal[
    "HS256", "HS384", "HS512",
    "RS256", "RS384", "RS512",
    "PS256", "PS384", "PS512",
    "ES256", "ES384", "ES512",
]

# .env liegt im Projektroot (eine Ebene über api/); beim lokalen Start aus
# api/ heraus wird sie so trotzdem gefunden. Umgebungsvariablen gewinnen immer.
PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    # Unbekannte Einträge ignorieren; .env im Root und (falls vorhanden) im CWD lesen
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "modeling"

    # JWT. Das Feedbacksystem 2.0 signiert mit RS256; geprüft wird gegen die
    # öffentlichen Schlüssel, die es als JWKS veröffentlicht. HS…-Verfahren prüfen
    # stattdessen gegen jwt_secret (z. B. für selbst signierte Testtoken).
    jwt_algorithm: JwtAlgorithm = "RS256"
    jwt_jwks_uri: str = "http://localhost:8080/oauth2/jwks"  # Identity-Service des FBS
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"  # nur für HS…
    jwt_issuer: str = ""  # erwarteter Aussteller (iss); leer = nicht geprüft
    jwt_audience: str = ""  # erwartete Client-IDs (aud), kommagetrennt; leer = nicht geprüft
    jwt_leeway_seconds: int = 5  # Toleranz für Uhrenabweichungen beim Ablauf
    jwt_user_claim: str = "id"  # Numerische Nutzer-ID aus dem Token
    jwt_roles_claim: str = "roles"  # Feld im Token mit Rollen-Liste (später definiert)
    jwt_global_role_claim: str = "globalRole"  # globale Rolle des Feedback-Systems

    # Anmeldung ohne FBS: Den Code tauscht und das Token erneuert die API beim
    # Identity-Service des FBS, so fragt der Browser dort nichts an und das Secret
    # der App bleibt hier. Ohne Secret (PUBLIC) gibt das FBS kein Refresh-Token.
    # Use the same shell origin as VITE_FBS_HOST_ORIGIN to preserve the issuer.
    oidc_token_uri: str = "http://localhost:8083/oauth2/token"
    oidc_token_host: str = ""  # Public Host header when Docker uses an internal address
    oidc_client_id: str = "modeling-copilot"  # Provider-ID der App im FBS
    oidc_client_secret: str = ""  # Secret der App (CONFIDENTIAL)

    # Sonstiges
    docs_enabled: bool = True  # Swagger unter /docs anzeigen
    cors_origins: str = "http://localhost:5173"  # kommagetrennte Liste

    # Dagu is accessed only by this API.  DAGU_API_KEY is supplied through a
    # deployment secret and must never be exposed to the web client.
    dagu_base_url: str = "http://dagu:8080"
    dagu_api_key: str = ""
    dagu_request_timeout_seconds: float = 15


# Einmalig beim Start gelesen; alle Module importieren diese Instanz.
settings = Settings()
