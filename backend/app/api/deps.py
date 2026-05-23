from __future__ import annotations

from typing import AsyncIterator

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.admin import Admin

AUTH_COOKIE = "access_token"


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def current_admin(
    access_token: str | None = Cookie(default=None, alias=AUTH_COOKIE),
    session: AsyncSession = Depends(get_session),
) -> Admin:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    data = decode_token(access_token)
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    username = data.get("sub")
    admin = (await session.execute(select(Admin).where(Admin.username == username))).scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found")
    return admin


# ───────── RBAC ─────────

ROLE_PERMS = {
    # roles → набор разрешений; * = всё
    "admin": {"*"},
    "manager": {"read", "create", "update"},  # без delete
    "viewer": {"read"},
}


def require_role(*allowed: str):
    """Dependency: разрешает доступ только указанным ролям.

    Использование:
        @router.delete(..., dependencies=[Depends(require_role("admin"))])
    """
    allowed_set = set(allowed)

    async def _check(admin: Admin = Depends(current_admin)) -> Admin:
        if admin.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется одна из ролей: {', '.join(sorted(allowed_set))}",
            )
        return admin

    return _check


def require_perm(perm: str):
    """Dependency: проверка по permission ('read'/'create'/'update'/'delete')."""
    async def _check(admin: Admin = Depends(current_admin)) -> Admin:
        perms = ROLE_PERMS.get(admin.role, set())
        if "*" not in perms and perm not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Роль {admin.role!r} не имеет права {perm!r}",
            )
        return admin

    return _check
