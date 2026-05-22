"""Тесты core/sentry — conditional init на DSN."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_init_sentry_skipped_when_no_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    from app.core.sentry import init_sentry
    # Не падает, ничего не делает
    init_sentry()


def test_init_sentry_skipped_when_empty_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "")
    from app.core.sentry import init_sentry
    init_sentry()


def test_init_sentry_skipped_when_whitespace_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "   ")
    from app.core.sentry import init_sentry
    init_sentry()


def test_init_sentry_calls_sdk_when_dsn_present(monkeypatch):
    """С реальным DSN — sentry_sdk.init вызывается с правильными опциями."""
    monkeypatch.setenv("SENTRY_DSN", "https://aaa@o0.ingest.sentry.io/0")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")

    init_called_with = {}
    fake_init = MagicMock(side_effect=lambda **kw: init_called_with.update(kw))

    # Monkeypatch sentry_sdk внутри функции
    import sentry_sdk
    monkeypatch.setattr(sentry_sdk, "init", fake_init)

    from app.core.sentry import init_sentry
    init_sentry()

    fake_init.assert_called_once()
    assert init_called_with["dsn"] == "https://aaa@o0.ingest.sentry.io/0"
    assert init_called_with["environment"] == "test"
    assert init_called_with["traces_sample_rate"] == 0.5
    assert init_called_with["send_default_pii"] is False
    assert "before_send" in init_called_with


def test_before_send_scrubs_authorization_header(monkeypatch):
    """before_send_pii удаляет Authorization/Cookie из event.request.headers."""
    monkeypatch.setenv("SENTRY_DSN", "https://aaa@o0.ingest.sentry.io/0")

    captured: dict = {}
    fake_init = MagicMock(side_effect=lambda **kw: captured.update(kw))

    import sentry_sdk
    monkeypatch.setattr(sentry_sdk, "init", fake_init)

    from app.core.sentry import init_sentry
    init_sentry()

    before_send = captured["before_send"]
    event_in = {
        "request": {
            "headers": {
                "Authorization": "Bearer xyz",
                "Cookie": "session=abc",
                "X-Api-Key": "topsecret",
                "User-Agent": "Mozilla",
            }
        }
    }
    out = before_send(event_in, {})
    h = out["request"]["headers"]
    assert "Authorization" not in h
    assert "Cookie" not in h
    assert "X-Api-Key" not in h
    # User-Agent остался
    assert h["User-Agent"] == "Mozilla"


def test_before_send_handles_missing_request(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://aaa@o0.ingest.sentry.io/0")

    captured: dict = {}
    fake_init = MagicMock(side_effect=lambda **kw: captured.update(kw))

    import sentry_sdk
    monkeypatch.setattr(sentry_sdk, "init", fake_init)

    from app.core.sentry import init_sentry
    init_sentry()

    before_send = captured["before_send"]
    # Event без request — не падает
    assert before_send({}, {}) == {}
    assert before_send({"request": None}, {}) == {"request": None}
