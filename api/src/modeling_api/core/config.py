"""Einstellungen der API, gelesen aus Umgebungsvariablen bzw. der Datei .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # JWT (HS256 = symmetrischer Schlüssel, reicht für die lokale Entwicklung)
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_user_claim: str = "id"  # Numerische Nutzer-ID aus dem Token
    jwt_roles_claim: str = "roles"  # Feld im Token mit Rollen-Liste (später definiert)
    jwt_global_role_claim: str = "globalRole"  # globale Rolle des Feedback-Systems

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
