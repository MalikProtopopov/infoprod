"""Хелперы для тестов."""
from __future__ import annotations

import io

# Минимальный валидный PNG-заголовок — годится как тестовый чек.
_RECEIPT_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 16


def payment_form(*, with_receipt: bool = True, **fields) -> dict:
    """kwargs для admin_client.post('/api/payments', ...) в multipart-формате.

    Создание платежа теперь требует чек (multipart). По умолчанию прикладываем
    валидный PNG; with_receipt=False — для теста «чек обязателен».
    """
    data = {k: str(v) for k, v in fields.items() if v is not None}
    kwargs: dict = {"data": data}
    if with_receipt:
        kwargs["files"] = {"receipts": ("receipt.png", io.BytesIO(_RECEIPT_PNG), "image/png")}
    return kwargs
