from __future__ import annotations

import time
from collections import defaultdict
from typing import Deque, Dict
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AUTH_COOKIE, current_admin, get_session
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.admin import Admin
from app.schemas.auth import (
    AdminInfo,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Простой rate-limit логина: не более 10 попыток за 60 секунд с одного IP.
_login_attempts: Dict[str, Deque[float]] = defaultdict(deque)
_RATE_LIMIT_WINDOW = 60.0
_RATE_LIMIT_MAX = 10


def _check_login_rate_limit(ip: str) -> None:
    now = time.monotonic()
    bucket = _login_attempts[ip]
    while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток входа. Подождите минуту и попробуйте снова.",
        )
    bucket.append(now)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    _check_login_rate_limit(client_ip)
    admin = (
        await session.execute(select(Admin).where(Admin.username == payload.username))
    ).scalar_one_or_none()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    token = create_access_token(subject=admin.username)
    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        max_age=settings.jwt_ttl_min * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return LoginResponse(ok=True, username=admin.username)


@router.post("/logout")
async def logout(response: Response, _: Admin = Depends(current_admin)) -> dict:
    response.delete_cookie(AUTH_COOKIE, path="/")
    return {"ok": True}


@router.get("/me", response_model=AdminInfo)
async def me(admin: Admin = Depends(current_admin)) -> AdminInfo:
    return AdminInfo(id=admin.id, username=admin.username)


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/password")
async def change_password(
    payload: PasswordChangeRequest,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not verify_password(payload.old_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Старый пароль не совпадает")
    admin.password_hash = hash_password(payload.new_password)
    await session.commit()
    return {"ok": True}
