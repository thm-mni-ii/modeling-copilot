"""Einstellungen der API, gelesen aus Umgebungsvariablen bzw. der Datei .env."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Allowed signature algorithms; "none" is missing on purpose, otherwise unsigned tokens would count.
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

    # JWT. The Feedbacksystem 2.0 signs with RS256; tokens are checked against the
    # public keys it publishes as JWKS. HS… algorithms check against jwt_secret
    # instead (e.g. for self-signed test tokens).
    jwt_algorithm: JwtAlgorithm = "RS256"
    jwt_jwks_uri: str = "http://localhost:8080/oauth2/jwks"  # Identity-Service des FBS
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"  # for HS… only
    jwt_issuer: str = ""  # expected issuer (iss); empty = not checked
    jwt_audience: str = ""  # expected client IDs (aud), comma-separated; empty = not checked
    jwt_leeway_seconds: int = 5  # tolerance for clock skew at expiry
    jwt_user_claim: str = "id"  # Numerische Nutzer-ID aus dem Token
    jwt_roles_claim: str = "roles"  # Feld im Token mit Rollen-Liste (später definiert)
    jwt_global_role_claim: str = "globalRole"  # globale Rolle des Feedback-Systems

    # Sign-in without FBS: the API exchanges the code and renews the token at the
    # identity service of the FBS, so the browser asks nothing there and the secret
    # of the app stays here. Without a secret (PUBLIC) the FBS gives no refresh token.
    # Use the same shell origin as VITE_FBS_HOST_ORIGIN to preserve the issuer.
    oidc_token_uri: str = "http://localhost:8083/oauth2/token"
    oidc_token_host: str = ""  # Public Host header when Docker uses an internal address
    oidc_client_id: str = "modeling-copilot"  # provider ID of the app in the FBS
    oidc_client_secret: str = ""  # secret of the app (CONFIDENTIAL)

    # Service identity towards Collab-Kit (CK): the API mints its own tokens, CK checks them
    # with the public key. Issuer, algorithm and ID must match CK (SERVICE_*), the ID
    # starts with "service-". Empty = sharing is switched off.
    ck_base_url: str = "http://localhost:24202"
    service_issuer: str = ""
    service_algorithm: str = ""  # RS…, PS… oder ES…
    service_actor: str = ""
    service_private_key: str = ""  # PEM, also single-line with \n

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
