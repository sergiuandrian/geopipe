"""Auth, billing, and plan-limit tests for the GeoPipe MVP."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fresh app + DB for each test."""
    data = tmp_path / "data"
    uploads = tmp_path / "uploads"
    data.mkdir()
    uploads.mkdir()
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("UPLOAD_DIR", str(uploads))
    monkeypatch.setenv("FREE_REQUEST_LIMIT", "5")
    monkeypatch.setenv("PRO_REQUEST_LIMIT", "1000")
    monkeypatch.setenv("JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()

    import app.core.database as database
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    database.engine = create_async_engine(get_settings().database_url, echo=False)
    database.SessionLocal = async_sessionmaker(database.engine, expire_on_commit=False, class_=AsyncSession)

    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_signup_login_and_me(client: TestClient) -> None:
    signup = client.post(
        "/v1/auth/signup",
        json={"email": "owner@example.com", "password": "password123", "name": "Owner"},
    )
    assert signup.status_code == 200, signup.text
    body = signup.json()
    assert body["user"]["email"] == "owner@example.com"
    assert body["project"]["plan"] == "free"
    assert body["api_key"].startswith("gp_")
    token = body["access_token"]

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["usage"]["limit"] == 5

    login = client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_dev_upgrade_and_plan_limits(client: TestClient) -> None:
    signup = client.post(
        "/v1/auth/signup",
        json={"email": "limits@example.com", "password": "password123"},
    )
    token = signup.json()["access_token"]
    api_key = signup.json()["api_key"]
    headers = {"Authorization": f"Bearer {token}", "X-API-Key": api_key}

    for _ in range(5):
        response = client.get("/v1/layers", headers=headers)
        assert response.status_code == 200, response.text

    blocked = client.get("/v1/layers", headers=headers)
    assert blocked.status_code == 402

    upgrade = client.post("/v1/billing/dev-upgrade", headers={"Authorization": f"Bearer {token}"})
    assert upgrade.status_code == 200
    assert upgrade.json()["project"]["plan"] == "pro"

    allowed = client.get("/v1/layers", headers=headers)
    assert allowed.status_code == 200

    usage = client.get("/v1/billing/usage", headers={"Authorization": f"Bearer {token}"})
    assert usage.status_code == 200
    payload = usage.json()
    assert payload["usage"]["plan"] == "pro"
    assert payload["usage"]["limit"] == 1000
    assert payload["usage"]["requests"] >= 6


def test_plans_endpoint_public(client: TestClient) -> None:
    response = client.get("/v1/billing/plans")
    assert response.status_code == 200
    plans = {item["id"]: item for item in response.json()["plans"]}
    assert plans["free"]["request_limit"] == 5
    assert plans["pro"]["request_limit"] == 1000
    assert response.json()["stripe_configured"] is False


def test_bootstrap_still_works_anonymously(client: TestClient) -> None:
    response = client.get("/v1/bootstrap")
    assert response.status_code == 200
    body = response.json()
    assert body["project"]["plan"] == "free"
    assert "usage" in body
    assert body["auth_required"] is False
