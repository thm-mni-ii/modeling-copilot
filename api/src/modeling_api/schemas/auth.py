"""Schemas for signing in without the Feedbacksystem around the web app."""

from pydantic import Field

from modeling_api.schemas.common import ApiSchema


class CodeExchange(ApiSchema):
    """Authorization code the Feedbacksystem returned to the web app."""

    code: str = Field(min_length=1, description="Authorization code from the redirect.")
    code_verifier: str = Field(min_length=43, max_length=128, description="PKCE verifier of the sign-in.")
    redirect_uri: str = Field(min_length=1, description="Redirect URI the sign-in started with.")


class TokenRefresh(ApiSchema):
    """Refresh token of an earlier exchange."""

    refresh_token: str = Field(min_length=1)


class Tokens(ApiSchema):
    """Tokens issued by the Feedbacksystem."""

    access_token: str
    refresh_token: str | None = Field(default=None, description="Only issued to a confidential client.")
    expires_in: int | None = Field(default=None, description="Lifetime of the access token in seconds.")
