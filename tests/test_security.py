
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.main import app
from api.dependencies import (
    get_auth_session,
    verify_csrf,
)
from api.security import hash_token


TRUSTED_ORIGIN = "http://localhost:5173"


def test_unauthenticated_session():
    from api.dependencies import get_auth_session

    with pytest.raises(HTTPException) as exc:
        get_auth_session(
            warranty_session=None,
            db=Mock(),
        )

    assert exc.value.status_code == 401


def test_missing_csrf_token():
    session = SimpleNamespace(
        csrf_token_hash=hash_token("valid-token")
    )

    with pytest.raises(HTTPException) as exc:
        verify_csrf(
            x_csrf_token=None,
            session=session,
        )

    assert exc.value.status_code == 403


def test_invalid_csrf_token():
    session = SimpleNamespace(
        csrf_token_hash=hash_token("valid-token")
    )

    with pytest.raises(HTTPException) as exc:
        verify_csrf(
            x_csrf_token="wrong-token",
            session=session,
        )

    assert exc.value.status_code == 403


def test_valid_csrf_token():
    session = SimpleNamespace(
        csrf_token_hash=hash_token("valid-token")
    )

    result = verify_csrf(
        x_csrf_token="valid-token",
        session=session,
    )

    assert result is None


def test_untrusted_origin_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://untrusted.example"
            },
            json={},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Untrusted request origin"
    )


def test_missing_origin_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={},
        )

    assert response.status_code == 403
