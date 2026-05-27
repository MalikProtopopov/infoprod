from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Логирование и Sentry — настраиваем до импорта роутеров,
# чтобы все эмиты внутри них уже шли через structlog.
from app.core.logging import configure_logging, get_logger
from app.core.sentry import init_sentry

configure_logging()
init_sentry()

logger = get_logger("app")

from app.api.auth import admin_router, router as auth_router  # noqa: E402
from app.api.bots import router as bots_router  # noqa: E402
from app.api.channels import router as channels_router  # noqa: E402
from app.api.leads import router as leads_router  # noqa: E402
from app.api.middleware.request_id import RequestContextMiddleware  # noqa: E402
from app.core.metrics import PrometheusMetricsMiddleware, metrics_response  # noqa: E402
from app.api.payments import router as payments_router  # noqa: E402
from app.api.products import router as products_router  # noqa: E402
from app.api.stats import router as stats_router  # noqa: E402
from app.api.stats import overview_router as stats_overview_router  # noqa: E402
from app.api.config import router as config_router  # noqa: E402
from app.api.subscriptions import router as subscriptions_router  # noqa: E402
from app.api.tracking_links import router as tracking_links_router  # noqa: E402
from app.api.users import router as users_router  # noqa: E402
from app.api.funnels import router as funnels_router  # noqa: E402
from app.api.funnels import entries_router as funnel_entries_router  # noqa: E402
from app.api.funnels import steps_router as funnel_steps_router  # noqa: E402
from app.api.lead_magnets import router as lead_magnets_router  # noqa: E402
from app.api.funnel_step_media import router as funnel_step_media_router  # noqa: E402
from app.api.funnel_triggers import router as funnel_triggers_router  # noqa: E402
from app.api.audit_log import router as audit_router  # noqa: E402
from app.api.feature_requests import router as feature_requests_router  # noqa: E402
from app.api.quizzes import router as quizzes_router  # noqa: E402
from app.api.forms import router as forms_router  # noqa: E402
from app.bot import manager as bot_manager  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.features import current_features  # noqa: E402
from app.workers import scheduler  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.admin_password:
        raise RuntimeError(
            "ADMIN_PASSWORD is empty. Set ADMIN_PASSWORD in .env before starting the service."
        )
    if len(settings.jwt_secret) < 32 or settings.jwt_secret == "dev-secret-change-me":
        logger.warning("jwt_secret.weak")
    logger.info("app.starting", env=os.environ.get("ENV", "production"))
    scheduler.start()
    try:
        await bot_manager.start()
    except Exception:
        logger.exception("bot_manager.start_failed")
    try:
        yield
    finally:
        logger.info("app.shutting_down")
        try:
            await bot_manager.stop()
        except Exception:
            logger.exception("bot_manager.stop_failed")
        scheduler.stop()


app = FastAPI(title="Infobizbot API", version="1.0.0", lifespan=lifespan)

# Middleware — request_id первым, чтобы все остальные слои уже несли его в контексте
app.add_middleware(RequestContextMiddleware)
# Prometheus идёт сразу после request_id, чтобы успел замерить latency финально
app.add_middleware(PrometheusMetricsMiddleware)


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    return metrics_response()

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ───────── Ядро: подключается всегда ─────────
CORE_ROUTERS = (
    auth_router,
    admin_router,
    bots_router,
    channels_router,
    products_router,
    users_router,
    audit_router,
    feature_requests_router,
    config_router,
    stats_overview_router,  # /stats/overview — нужен главной админки всегда
)

# ───────── Отключаемые фичи → их роутеры ─────────
# Ключи соответствуют app.core.features.FEATURE_REGISTRY. Резолвер уже учёл
# каскад зависимостей, поэтому здесь просто читаем эффективный набор.
FEATURE_ROUTERS: dict[str, list] = {
    "leads": [leads_router],
    "monetization": [payments_router, subscriptions_router],
    "tracking_links": [tracking_links_router],
    "analytics": [stats_router],
    "funnels": [
        funnels_router,
        funnel_entries_router,
        funnel_steps_router,
        funnel_step_media_router,
    ],
    "funnel_triggers": [funnel_triggers_router],
    "quizzes": [quizzes_router],
    "forms": [forms_router],
    "lead_magnets": [lead_magnets_router],
}


def build_api_router(features: dict[str, bool]) -> APIRouter:
    """Собирает /api-роутер: ядро всегда + фичевые роутеры по флагам.

    Вынесено в функцию, чтобы было тестируемо без перезагрузки модуля.
    """
    api = APIRouter(prefix="/api")

    @api.get("/healthz")
    async def healthz() -> dict:  # noqa: WPS430 — локальный эндпойнт ок
        return {"ok": True}

    for core_router in CORE_ROUTERS:
        api.include_router(core_router)

    for key, routers in FEATURE_ROUTERS.items():
        if features.get(key):
            for r in routers:
                api.include_router(r)
            logger.info("feature.enabled", feature=key)
        else:
            logger.info("feature.disabled", feature=key)

    return api


app.include_router(build_api_router(current_features()))
