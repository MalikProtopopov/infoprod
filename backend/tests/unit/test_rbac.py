"""Тесты RBAC: require_role / require_perm."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.deps import ROLE_PERMS, require_role, require_perm


class _FakeAdmin:
    def __init__(self, role: str):
        self.role = role


@pytest.mark.asyncio
async def test_require_role_admin_ok():
    check = require_role("admin")
    admin = _FakeAdmin("admin")
    result = await check(admin=admin)
    assert result is admin


@pytest.mark.asyncio
async def test_require_role_manager_for_admin_role_denied():
    check = require_role("admin")
    manager = _FakeAdmin("manager")
    with pytest.raises(HTTPException) as exc:
        await check(admin=manager)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_multiple():
    check = require_role("admin", "manager")
    assert (await check(admin=_FakeAdmin("admin"))) is not None
    assert (await check(admin=_FakeAdmin("manager"))) is not None
    with pytest.raises(HTTPException):
        await check(admin=_FakeAdmin("viewer"))


@pytest.mark.asyncio
async def test_require_perm_admin_has_all():
    check = require_perm("delete")
    assert (await check(admin=_FakeAdmin("admin"))) is not None


@pytest.mark.asyncio
async def test_require_perm_viewer_read_only():
    check_read = require_perm("read")
    check_create = require_perm("create")
    viewer = _FakeAdmin("viewer")
    assert (await check_read(admin=viewer)) is not None
    with pytest.raises(HTTPException):
        await check_create(admin=viewer)


@pytest.mark.asyncio
async def test_require_perm_manager_cant_delete():
    check = require_perm("delete")
    with pytest.raises(HTTPException):
        await check(admin=_FakeAdmin("manager"))


@pytest.mark.asyncio
async def test_require_perm_unknown_role_denied():
    check = require_perm("read")
    with pytest.raises(HTTPException):
        await check(admin=_FakeAdmin("nosuchrole"))


def test_role_perms_structure():
    """Базовая проверка контракта ROLE_PERMS."""
    assert "admin" in ROLE_PERMS
    assert "*" in ROLE_PERMS["admin"]
    assert "read" in ROLE_PERMS["viewer"]
    assert "delete" not in ROLE_PERMS["manager"]
