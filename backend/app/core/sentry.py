"""Инициализация Sentry — только если задан SENTRY_DSN.

В тестах и dev SENTRY_DSN пустой → Sentry SDK не активируется.
"""
from __future__ import annotations

import os

import structlog

logger = structlog.get_logger("sentry")


def init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("sentry.skipped", reason="no_dsn")
        return

    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    def _scrub_pii(event, hint):  # noqa: ARG001
        # Дополнительно вычищаем заголовки авторизации (на случай если pii=True)
        if "request" in event and isinstance(event["request"], dict):
            headers = event["request"].get("headers") or {}
            if isinstance(headers, dict):
                for h in ("Authorization", "Cookie", "X-Api-Key"):
                    headers.pop(h, None)
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("ENV", "production"),
        release=os.environ.get("GIT_SHA", "unknown"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.05")),
        send_default_pii=False,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            AsyncioIntegration(),
            SqlalchemyIntegration(),
        ],
        before_send=_scrub_pii,
    )
    logger.info("sentry.initialized", env=os.environ.get("ENV", "production"))
