"""Tests for auth middleware in dev mode (AUTH_DEV_MODE=true)."""

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from auth.middleware import get_current_user, require_admin
from db.models import User
from main import app


def _make_user(*, is_admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        slug=f"test-{uuid.uuid4()}",
        email="test@truboard.com",
        display_name="Test User",
        is_admin=is_admin,
    )


def test_auth_routes_exist():
    client = TestClient(app)
    resp = client.get("/api/auth/login")
    assert resp.status_code == 200


def test_logout_with_auth():
    user = _make_user()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["user"] == "test@truboard.com"
    finally:
        app.dependency_overrides.clear()


def test_require_admin_allows_admin():
    admin = _make_user(is_admin=True)
    result = asyncio.get_event_loop().run_until_complete(require_admin(admin))
    assert result.is_admin is True


def test_require_admin_rejects_non_admin():
    user = _make_user(is_admin=False)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(require_admin(user))
    assert exc_info.value.status_code == 403
