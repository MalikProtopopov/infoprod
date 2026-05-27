"""Integration: полный покупательский флоу через admin API.

Шаги:
1. Admin создаёт продукт/канал/бот (через make_committed).
2. Admin создаёт трекинговую ссылку через API.
3. Эмуляция клика: прямой INSERT (бот хендлеры тестируются отдельно в unit).
4. Эмуляция лида от клиента через прямой INSERT с tracking_link_id.
5. Admin создаёт платёж через API.
6. Проверяем: подписка active, payment.admin_id + tracking_link_id, lead.status=paid, stats/sources видит конверсию.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import payment_form
from sqlalchemy import text


pytestmark = pytest.mark.integration


def _patch_tg(monkeypatch):
    calls = MagicMock()
    calls.invite = AsyncMock(return_value="https://t.me/+inviteflow")
    calls.kick = AsyncMock(return_value=True)
    calls.send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.services.subscriptions.tg.create_one_time_invite", calls.invite)
    monkeypatch.setattr("app.services.subscriptions.tg.kick_user", calls.kick)
    monkeypatch.setattr("app.services.subscriptions.tg.send_message_safe", calls.send)
    return calls


@pytest.mark.asyncio
async def test_full_purchase_flow(
    admin_client, make_committed, engine, clean_db, monkeypatch,
):
    # ──── 1. Каталог + ссылка ────
    bot_model = await make_committed.bot(username="flowbot", telegram_bot_id=88888)
    channel = await make_committed.channel(bot=bot_model)
    product = await make_committed.product(
        channel=channel, price_3m=1000, price_6m=1800, price_12m=3000,
    )

    r = await admin_client.post(
        "/api/tracking-links",
        json={
            "product_id": product.id,
            "utm_source": "instagram",
            "utm_medium": "reels",
            "utm_campaign": "flow_test",
            "custom_slug": "flowslug",
        },
    )
    assert r.status_code == 201
    link_id = r.json()["id"]

    # ──── 2. Эмуляция клика клиента: пользователь + click_count ++ ────
    user = await make_committed.user(
        telegram_user_id=55555, first_name="FlowUser", username="flowuser",
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE tracking_links SET click_count = click_count+1, unique_users = unique_users+1 "
                "WHERE id = :id"
            ),
            {"id": link_id},
        )
        await conn.execute(
            text(
                "UPDATE users SET first_utm_source=:s, first_tracking_link_id=:l, "
                "first_product_id=:p, first_bot_id=:b WHERE id=:uid"
            ),
            {"s": "instagram", "l": link_id, "p": product.id, "b": bot_model.id, "uid": user.id},
        )

    # ──── 3. Эмулируем lead «Оставить заявку» с UTM-атрибуцией ────
    lead = await make_committed.lead(
        user=user, product=product, status="new",
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE leads SET tracking_link_id=:l, utm_source=:s, utm_medium=:m, utm_campaign=:c "
                "WHERE id=:id"
            ),
            {"l": link_id, "s": "instagram", "m": "reels", "c": "flow_test", "id": lead.id},
        )

    # ──── 4. Admin создаёт платёж через API ────
    _patch_tg(monkeypatch)
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 3),
    )
    assert r.status_code == 201, r.text
    payment_id = r.json()["id"]

    # ──── 5. Все ожидаемые эффекты ────
    async with engine.connect() as conn:
        payment_row = (
            await conn.execute(
                text("SELECT admin_id, tracking_link_id FROM payments WHERE id=:id"),
                {"id": payment_id},
            )
        ).first()
        assert payment_row[0] is not None, "admin_id должен быть заполнен"
        assert payment_row[1] == link_id, "tracking_link_id наследуется от lead"

        sub_row = (
            await conn.execute(
                text("SELECT status, invite_link FROM subscriptions WHERE user_id=:uid"),
                {"uid": user.id},
            )
        ).first()
        assert sub_row[0] == "active"
        assert sub_row[1] == "https://t.me/+inviteflow"

        lead_row = (
            await conn.execute(
                text("SELECT status, paid_at FROM leads WHERE id=:id"),
                {"id": lead.id},
            )
        ).first()
        assert lead_row[0] == "paid", "lead авто-помечается paid после платежа"
        assert lead_row[1] is not None

    # ──── 6. В /stats/sources видна полная конверсия ────
    r = await admin_client.get("/api/stats/sources?group_by=source")
    body = r.json()
    ig_row = next((row for row in body["rows"] if row.get("source") == "instagram"), None)
    assert ig_row is not None
    assert ig_row["leads"] == 1
    assert ig_row["payments"] == 1
    assert float(ig_row["revenue"]) == 1000.0
    assert ig_row["clicks"] == 1
    assert ig_row["unique_users"] == 1


@pytest.mark.asyncio
async def test_payment_creation_rejects_inactive_bot(
    admin_client, make_committed, clean_db, monkeypatch,
):
    """Если bot_manager.get_aiogram_bot возвращает None — POST /payments → 409."""
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: None)
    product = await make_committed.product()
    user = await make_committed.user()

    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 3),
    )
    assert r.status_code == 409
    assert "неактивен" in r.json()["detail"].lower() or "невозможно" in r.json()["detail"].lower()
