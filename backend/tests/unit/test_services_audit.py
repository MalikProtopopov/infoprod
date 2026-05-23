"""Тесты services/audit — log_action + _scrub."""
from __future__ import annotations

import pytest

from app.services.audit import _scrub, log_action


def test_scrub_redacts_known_secret_keys():
    out = _scrub({"password": "secret", "username": "admin"})
    assert out["password"] == "***REDACTED***"
    assert out["username"] == "admin"


def test_scrub_handles_nested_dict():
    out = _scrub({"data": {"old_password": "x", "new_password": "y", "name": "n"}})
    assert out["data"]["old_password"] == "***REDACTED***"
    assert out["data"]["new_password"] == "***REDACTED***"
    assert out["data"]["name"] == "n"


def test_scrub_case_insensitive():
    out = _scrub({"PASSWORD": "x", "Token": "y"})
    assert out["PASSWORD"] == "***REDACTED***"
    assert out["Token"] == "***REDACTED***"


def test_scrub_handles_none_and_empty():
    assert _scrub(None) is None
    assert _scrub({}) == {}


def test_scrub_preserves_non_secret_values():
    out = _scrub({"id": 42, "active": True, "name": "test"})
    assert out == {"id": 42, "active": True, "name": "test"}


@pytest.mark.asyncio
async def test_log_action_creates_audit_record(session, make):
    admin = await make.admin()
    entry = await log_action(
        session,
        admin_id=admin.id,
        action="create",
        resource_type="product",
        resource_id=42,
        summary="Created test product",
        method="POST",
        path="/api/products",
        payload={"name": "Test"},
    )
    assert entry.id is not None
    assert entry.admin_id == admin.id
    assert entry.action == "create"
    assert entry.resource_type == "product"
    assert entry.resource_id == 42


@pytest.mark.asyncio
async def test_log_action_scrubs_payload(session, make):
    admin = await make.admin()
    entry = await log_action(
        session, admin_id=admin.id, action="login",
        resource_type="auth",
        payload={"username": "admin", "password": "super-secret"},
    )
    assert entry.payload["password"] == "***REDACTED***"
    assert entry.payload["username"] == "admin"
