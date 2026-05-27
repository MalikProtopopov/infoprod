"""AuditMiddleware — авто-фиксация всех аутентифицированных мутаций в audit_log.

Раньше log_action вызывался вручную лишь в нескольких эндпойнтах (≈5 из ~52),
поэтому журнал был почти пустой. Этот middleware пишет запись для КАЖДОГО
успешного POST/PATCH/PUT/DELETE под /api от залогиненного админа — гарантированное
покрытие без правки каждого хендлера.

Пишет: admin_id (по токену), action, resource_type, resource_id (из пути),
method, path, ip, user_agent. Тело запроса не читаем (без утечек/без расхода стрима).
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security import decode_token
from app.db import session as _db  # ленивая ссылка на SessionLocal (тесты её подменяют)

logger = structlog.get_logger("audit_mw")

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_ACTION_BY_METHOD = {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}
# Кастомные POST-действия (не «create») — берём из последнего сегмента пути.
_ACTION_VERBS = {"revoke", "extend", "reorder", "cancel", "complete", "csv", "password"}
# Эти префиксы логируются отдельно (вручную) или не нужны в аудите.
_SKIP_SEGMENTS = {"auth", "audit-log", "config", "feature-requests"}
# URL-сегмент (мн.ч.) → resource_type (ед.ч.), как в ручных вызовах log_action.
_RESOURCE_BY_SEGMENT = {
    "payments": "payment",
    "products": "product",
    "channels": "channel",
    "bots": "bot",
    "funnels": "funnel",
    "funnel-steps": "funnel_step",
    "funnel-entries": "funnel_entry",
    "funnel-triggers": "funnel_trigger",
    "funnel-step-media": "funnel_step_media",
    "lead-magnets": "lead_magnet",
    "quizzes": "quiz",
    "forms": "form",
    "leads": "lead",
    "subscriptions": "subscription",
    "tracking-links": "tracking_link",
    "users": "user",
}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        try:
            await self._maybe_audit(request, response)
        except Exception:  # аудит никогда не должен ломать запрос
            logger.warning("audit_mw.failed", exc_info=True)
        return response

    async def _maybe_audit(self, request: Request, response) -> None:
        if request.method not in _MUTATING or response.status_code >= 400:
            return
        path = request.url.path
        if not path.startswith("/api/"):
            return
        segments = [s for s in path[len("/api/"):].split("/") if s]
        if not segments or segments[0] in _SKIP_SEGMENTS:
            return
        # GDPR-forget логируется вручную с осмысленным action — не дублируем.
        if segments[-1] == "forget":
            return

        token = request.cookies.get("access_token")
        data = decode_token(token) if token else None
        if not data:
            return  # неаутентифицированную мутацию и так бы не пропустили
        username = data.get("sub")

        resource_type = _RESOURCE_BY_SEGMENT.get(segments[0], segments[0])
        resource_id = int(segments[1]) if len(segments) > 1 and segments[1].isdigit() else None
        last = segments[-1]
        action = last if last in _ACTION_VERBS else _ACTION_BY_METHOD[request.method]
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")

        from app.models.admin import Admin
        from app.services.audit import log_action

        async with _db.SessionLocal() as session:
            admin_id = (
                await session.execute(select(Admin.id).where(Admin.username == username))
            ).scalar_one_or_none()
            await log_action(
                session,
                admin_id=admin_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                method=request.method,
                path=path,
                ip=ip,
                user_agent=ua,
            )
            await session.commit()
