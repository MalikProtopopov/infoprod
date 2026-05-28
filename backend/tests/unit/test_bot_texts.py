"""Регрессии и unit-тесты для bot/texts.py."""
from __future__ import annotations

from datetime import datetime, timezone

from app.bot.texts import (
    access_expired,
    access_granted,
    my_subscriptions_line,
    product_card,
)


class TestProductCard:
    """Регрессии бага «нулевые цены показываются как 0 RUB» (2026-05-22)."""

    def test_all_three_prices_shown(self):
        out = product_card("Курс", "Описание", 1000, 1500, 2000, "RUB")
        assert "3 мес." in out
        assert "6 мес." in out
        assert "12 мес." in out
        assert "1 000" in out
        assert "1 500" in out
        assert "2 000" in out

    def test_zero_prices_hidden(self):
        # Регрессия — 0 не должен показываться
        out = product_card("X", None, 1000, 0, 0, "RUB")
        assert "1 000" in out
        assert "3 мес." in out
        assert "6 мес." not in out
        assert "12 мес." not in out

    def test_all_zero_shows_fallback(self):
        out = product_card("X", "desc", 0, 0, 0, "RUB")
        assert "индивидуально" in out
        assert "Оставить заявку" in out

    def test_html_escape_in_name(self):
        out = product_card("<script>", None, 100, 0, 0, "RUB")
        assert "<script>" not in out
        assert "&lt;script&gt;" in out

    def test_no_description_omits_block(self):
        out = product_card("Name only", None, 100, 0, 0, "RUB")
        assert "Name only" in out

    def test_description_is_present(self):
        out = product_card("N", "Подробное описание", 100, 0, 0, "RUB")
        assert "Подробное описание" in out


class TestAccessMessages:
    def test_access_granted_includes_channel_link_and_date(self):
        ends = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        out = access_granted("Йога", ends, "https://t.me/+abc")
        assert "Йога" in out
        assert "https://t.me/+abc" in out
        assert "22.08.2026" in out

    def test_access_expired_mentions_channel(self):
        out = access_expired("Йога 12")
        assert "Йога 12" in out
        assert "/start" in out


class TestMySubscriptionsLine:
    def test_active_label(self):
        ends = datetime(2026, 12, 31, tzinfo=timezone.utc)
        line = my_subscriptions_line("Канал", ends, "active")
        assert "активна" in line
        assert "31.12.2026" in line

    def test_expired_label(self):
        ends = datetime(2026, 1, 1, tzinfo=timezone.utc)
        line = my_subscriptions_line("X", ends, "expired")
        assert "истекла" in line

    def test_revoked_label(self):
        ends = datetime(2026, 1, 1, tzinfo=timezone.utc)
        line = my_subscriptions_line("X", ends, "revoked")
        assert "отозвана" in line
