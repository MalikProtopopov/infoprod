"""API контент-блоков продукта: CRUD блоков, загрузка медиа, reorder, поля продукта."""
from __future__ import annotations

import io

import pytest

_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 16
_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 16


def _img(name="p.png"):
    return {"file": (name, io.BytesIO(_PNG), "image/png")}


def _vid(name="v.mp4"):
    return {"file": (name, io.BytesIO(_MP4), "video/mp4")}


@pytest.mark.asyncio
async def test_block_crud_and_reorder(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    # создать 2 блока
    b1 = (await admin_client.post(f"/api/products/{product.id}/content-blocks", json={"kind": "text", "text": "Привет"})).json()
    b2 = (await admin_client.post(f"/api/products/{product.id}/content-blocks", json={"kind": "media"})).json()
    assert b1["order_idx"] == 0 and b2["order_idx"] == 1

    # список
    lst = (await admin_client.get(f"/api/products/{product.id}/content-blocks")).json()
    assert len(lst) == 2

    # reorder
    r = await admin_client.post(f"/api/products/{product.id}/content-blocks/reorder",
                                json={"ordered_ids": [b2["id"], b1["id"]]})
    order = {b["id"]: b["order_idx"] for b in r.json()}
    assert order[b2["id"]] == 0 and order[b1["id"]] == 1

    # update + delete
    upd = await admin_client.patch(f"/api/content-blocks/{b1['id']}", json={"text": "Обновлено", "delay_ms": 1500})
    assert upd.json()["text"] == "Обновлено" and upd.json()["delay_ms"] == 1500
    assert (await admin_client.delete(f"/api/content-blocks/{b1['id']}")).status_code == 204


@pytest.mark.asyncio
async def test_media_upload_and_limits(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    media_block = (await admin_client.post(f"/api/products/{product.id}/content-blocks", json={"kind": "media"})).json()
    r = await admin_client.post(f"/api/content-blocks/{media_block['id']}/media", files=_img())
    assert r.status_code == 201
    block = r.json()
    assert len(block["media"]) == 1
    assert block["media"][0]["media_type"] == "photo"

    # video_note блок: 1 видео → media_type=video_note; 2-е → 409
    note_block = (await admin_client.post(f"/api/products/{product.id}/content-blocks", json={"kind": "video_note"})).json()
    r1 = await admin_client.post(f"/api/content-blocks/{note_block['id']}/media", files=_vid())
    assert r1.status_code == 201
    assert r1.json()["media"][0]["media_type"] == "video_note"
    r2 = await admin_client.post(f"/api/content-blocks/{note_block['id']}/media", files=_vid("v2.mp4"))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_text_block_rejects_media(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    tb = (await admin_client.post(f"/api/products/{product.id}/content-blocks", json={"kind": "text", "text": "x"})).json()
    r = await admin_client.post(f"/api/content-blocks/{tb['id']}/media", files=_img())
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_media_file_served(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    mb = (await admin_client.post(f"/api/products/{product.id}/content-blocks", json={"kind": "media"})).json()
    up = await admin_client.post(f"/api/content-blocks/{mb['id']}/media", files=_img())
    mid = up.json()["media"][0]["id"]
    r = await admin_client.get(f"/api/content-block-media/{mid}/file")
    assert r.status_code == 200
    assert r.content == _PNG


@pytest.mark.asyncio
async def test_product_content_fields_persist(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.patch(f"/api/products/{product.id}", json={
        "card_text": "<b>Оффер</b> <blockquote expandable>детали</blockquote>",
        "thank_you_message": "Спасибо за покупку!",
        "presentation_enabled": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["card_text"].startswith("<b>Оффер")
    assert body["thank_you_message"] == "Спасибо за покупку!"
    assert body["presentation_enabled"] is False
