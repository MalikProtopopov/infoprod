"""Структурированное логирование на structlog.

Backend пишет JSON-логи в stdout. Каждый лог несёт `request_id`, `service`,
любой дополнительный контекст из ContextVar (см. middleware/request_id.py).

Секреты в `event_dict` маскируются автоматически.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars

ENV = os.environ.get("ENV", "production")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "backend")

# Поля, которые маскируем во всех логах
SECRET_KEYS = frozenset({
    "password",
    "password_hash",
    "token",
    "jwt",
    "secret",
    "authorization",
    "cookie",
    "set-cookie",
    "access_token",
    "api_key",
    "x-api-key",
})


def _mask_secrets_processor(
    logger: Any, method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Заменяет значения по ключу-имени, и частично длинные `*_token` строки."""
    for k in list(event_dict.keys()):
        kl = k.lower()
        if kl in SECRET_KEYS:
            event_dict[k] = "***REDACTED***"
            continue
        v = event_dict[k]
        if isinstance(v, str) and len(v) > 100 and any(s in kl for s in ("token", "key", "secret")):
            event_dict[k] = v[:4] + "..." + v[-4:]
    return event_dict


def _add_service(
    logger: Any, method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    event_dict.setdefault("service", SERVICE_NAME)
    return event_dict


def configure_logging(level: str | None = None) -> None:
    """Один раз при старте приложения."""
    log_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    processors: list[structlog.types.Processor] = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        _add_service,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        _mask_secrets_processor,
    ]
    if ENV in ("development", "test"):
        # ConsoleRenderer сам красиво форматирует исключения — dict_tracebacks
        # здесь несовместим (он отдаёт list, а рендерер делает "\n"+exc → TypeError).
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # В проде — структурный JSON: dict_tracebacks разворачивает traceback в dict.
        processors.append(structlog.processors.dict_tracebacks)
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
