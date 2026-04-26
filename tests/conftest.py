"""Shared fixtures for the pymercury test suite."""

import base64
import json
from typing import Any, Dict, Optional

import pytest


def _encode_segment(data: Dict[str, Any]) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps(data).encode("utf-8"))
        .rstrip(b"=")
        .decode("ascii")
    )


def make_fake_jwt(payload: Optional[Dict[str, Any]] = None) -> str:
    """Build a minimal unsigned JWT.

    The library decodes JWTs without verification, so a "fakesignature" is fine.
    """
    header = {"alg": "RS256", "typ": "JWT"}
    body = payload if payload is not None else {
        "extension_customerId": "cust-test",
        "accountId": "acc-test",
        "serviceId": "svc-test",
        "email": "test@example.com",
        "given_name": "Test",
        "family_name": "User",
        "exp": 9999999999,
        "iat": 1700000000,
    }
    return f"{_encode_segment(header)}.{_encode_segment(body)}.fakesignature"


@pytest.fixture
def fake_jwt():
    """Return the fake-JWT factory."""
    return make_fake_jwt


@pytest.fixture
def fake_oauth_token_data(fake_jwt):
    """A token_data dict that OAuthTokens can parse to populate every field."""
    return {
        "access_token": fake_jwt(),
        "refresh_token": "rt_test_123",
        "expires_in": 3600,
        "token_type": "Bearer",
    }


@pytest.fixture(autouse=True)
def restore_default_config():
    """Snapshot pymercury.config.default_config so importlib.reload tests
    don't leak state into other tests."""
    import pymercury.config as cfg_mod

    snapshot = cfg_mod.default_config
    yield
    cfg_mod.default_config = snapshot
