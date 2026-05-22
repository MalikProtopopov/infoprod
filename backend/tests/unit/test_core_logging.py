"""Тесты core/logging — маскирование секретов, service-tag, configure_logging."""
from __future__ import annotations

import structlog

from app.core.logging import _add_service, _mask_secrets_processor, configure_logging, get_logger


class TestMaskSecretsProcessor:
    def test_masks_password(self):
        out = _mask_secrets_processor(None, "info", {"password": "supersecret"})
        assert out["password"] == "***REDACTED***"

    def test_masks_jwt_token(self):
        out = _mask_secrets_processor(None, "info", {"token": "abc.def.ghi"})
        assert out["token"] == "***REDACTED***"

    def test_masks_authorization_header(self):
        out = _mask_secrets_processor(None, "info", {"authorization": "Bearer xyz"})
        assert out["authorization"] == "***REDACTED***"

    def test_masks_set_cookie(self):
        out = _mask_secrets_processor(None, "info", {"set-cookie": "session=abc; HttpOnly"})
        assert out["set-cookie"] == "***REDACTED***"

    def test_case_insensitive(self):
        out = _mask_secrets_processor(None, "info", {"Password": "x", "TOKEN": "y"})
        assert out["Password"] == "***REDACTED***"
        assert out["TOKEN"] == "***REDACTED***"

    def test_does_not_touch_safe_fields(self):
        out = _mask_secrets_processor(None, "info", {"username": "admin", "id": 42})
        assert out["username"] == "admin"
        assert out["id"] == 42

    def test_partially_masks_long_token_strings(self):
        """Длинные строки в полях с подстрокой 'token'/'key'/'secret' маскируются частично."""
        long_token = "x" * 150
        out = _mask_secrets_processor(None, "info", {"api_token": long_token})
        # api_token не в SECRET_KEYS дословно, поэтому partial mask
        assert "..." in out["api_token"]
        assert len(out["api_token"]) < 50

    def test_short_token_field_unchanged(self):
        out = _mask_secrets_processor(None, "info", {"refresh_token_id": 5})
        assert out["refresh_token_id"] == 5


class TestAddService:
    def test_adds_service_when_missing(self):
        out = _add_service(None, "info", {})
        assert "service" in out
        assert out["service"] == "backend"

    def test_does_not_overwrite_existing(self):
        out = _add_service(None, "info", {"service": "worker"})
        assert out["service"] == "worker"


class TestConfigureLogging:
    def test_configure_sets_up_structlog(self):
        configure_logging(level="DEBUG")
        log = get_logger("test")
        # Не падаем при попытке логнуть
        log.info("hello", x=1)

    def test_get_logger_returns_structlog_bound_logger(self):
        log = get_logger()
        # У structlog logger есть метод .bind
        assert hasattr(log, "info")
        assert hasattr(log, "bind")
