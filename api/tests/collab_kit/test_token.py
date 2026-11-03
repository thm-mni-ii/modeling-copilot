import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from modeling_api.core.config import settings
from modeling_api.core.errors import ApiError
from modeling_api.services.collab_kit import token as collab_token


@pytest.fixture
def public_key(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    monkeypatch.setattr(settings, "service_issuer", "modeling-copilot-api")
    monkeypatch.setattr(settings, "service_algorithm", "ES256")
    monkeypatch.setattr(settings, "service_actor", "service-modeling-copilot")
    monkeypatch.setattr(settings, "service_private_key", private)
    monkeypatch.setattr(collab_token, "_token", None)
    return key.public_key()


def test_token_is_verifiable_and_short_lived(public_key, monkeypatch):
    monkeypatch.setattr(collab_token, "_now", lambda: 1_000)
    claims = jwt.decode(
        collab_token.service_token(),
        public_key,
        algorithms=["ES256"],
        issuer="modeling-copilot-api",
        options={"verify_exp": False},
    )
    assert claims["sub"] == "service-modeling-copilot"
    assert 0 < claims["exp"] - claims["iat"] <= 600


def test_token_is_reused_and_renewed_shortly_before_expiry(public_key, monkeypatch):
    now = 1_000
    monkeypatch.setattr(collab_token, "_now", lambda: now)
    first = collab_token.service_token()
    now += collab_token.LIFETIME_SECONDS - collab_token.RENEW_BEFORE_SECONDS - 1
    assert collab_token.service_token() == first
    now += 1
    assert collab_token.service_token() != first


def test_unconfigured_service_switches_sharing_off(monkeypatch):
    monkeypatch.setattr(settings, "service_private_key", "")
    monkeypatch.setattr(collab_token, "_token", None)
    with pytest.raises(ApiError) as error:
        collab_token.service_token()
    assert error.value.code == "SHARING_DISABLED"
