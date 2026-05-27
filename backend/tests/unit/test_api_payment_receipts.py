"""API: чеки платежа — загрузка (до 3), список, отдача файла, валидация типа."""
from __future__ import annotations

import io

import pytest

_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 32


def _png(name: str = "receipt.png"):
    return {"file": (name, io.BytesIO(_PNG), "image/png")}


@pytest.mark.asyncio
async def test_upload_and_list_receipt(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.api.payments.RECEIPTS_DIR", tmp_path)
    payment = await make_committed.payment()

    r = await admin_client.post(f"/api/payments/{payment.id}/receipts", files=_png())
    assert r.status_code == 201
    body = r.json()
    assert len(body) == 1
    assert body[0]["is_image"] is True
    assert body[0]["mime_type"] == "image/png"

    lst = await admin_client.get(f"/api/payments/{payment.id}/receipts")
    assert lst.status_code == 200
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_receipts_max_three(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.api.payments.RECEIPTS_DIR", tmp_path)
    payment = await make_committed.payment()
    for i in range(3):
        assert (await admin_client.post(f"/api/payments/{payment.id}/receipts", files=_png(f"r{i}.png"))).status_code == 201
    # 4-й — отказ
    r = await admin_client.post(f"/api/payments/{payment.id}/receipts", files=_png("r4.png"))
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_receipt_rejects_bad_type(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.api.payments.RECEIPTS_DIR", tmp_path)
    payment = await make_committed.payment()
    files = {"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await admin_client.post(f"/api/payments/{payment.id}/receipts", files=files)
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_receipt_file_served(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.api.payments.RECEIPTS_DIR", tmp_path)
    payment = await make_committed.payment()
    up = await admin_client.post(f"/api/payments/{payment.id}/receipts", files=_png())
    rid = up.json()[0]["id"]

    r = await admin_client.get(f"/api/payments/{payment.id}/receipts/{rid}/file")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert r.content == _PNG


@pytest.mark.asyncio
async def test_list_payments_includes_receipts(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.api.payments.RECEIPTS_DIR", tmp_path)
    payment = await make_committed.payment()
    await admin_client.post(f"/api/payments/{payment.id}/receipts", files=_png())

    r = await admin_client.get("/api/payments")
    assert r.status_code == 200
    target = next(p for p in r.json() if p["id"] == payment.id)
    assert len(target["receipts"]) == 1
    assert target["receipts"][0]["is_image"] is True


@pytest.mark.asyncio
async def test_receipt_file_wrong_payment_404(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.api.payments.RECEIPTS_DIR", tmp_path)
    p1 = await make_committed.payment()
    p2 = await make_committed.payment()
    up = await admin_client.post(f"/api/payments/{p1.id}/receipts", files=_png())
    rid = up.json()[0]["id"]
    # тот же receipt под другим payment_id → 404
    r = await admin_client.get(f"/api/payments/{p2.id}/receipts/{rid}/file")
    assert r.status_code == 404
