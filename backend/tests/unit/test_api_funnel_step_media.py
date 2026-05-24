"""API-тесты для /api/funnel-steps/{id}/media — upload, reorder, delete."""
from __future__ import annotations

import io

import pytest


@pytest.mark.asyncio
async def test_list_empty_step_media(admin_client, make_committed, clean_db):
    step = await make_committed.funnel_step()
    r = await admin_client.get(f"/api/funnel-steps/{step.id}/media")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_step_not_found_404(admin_client, clean_db):
    r = await admin_client.get("/api/funnel-steps/999999/media")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_upload_photo(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    files = {"file": ("photo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 100), "image/png")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["media_type"] == "photo"
    assert body["mime_type"] == "image/png"
    assert body["file_size"] > 0
    assert body["order_idx"] == 0
    assert body["has_telegram_file_id"] is False


@pytest.mark.asyncio
async def test_upload_video_detects_type(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    files = {"file": ("clip.mp4", io.BytesIO(b"\x00" * 1024), "video/mp4")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    assert r.status_code == 201
    assert r.json()["media_type"] == "video"


@pytest.mark.asyncio
async def test_upload_unknown_mime_becomes_document(
    admin_client, make_committed, monkeypatch, tmp_path, clean_db
):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    files = {"file": ("notes.zip", io.BytesIO(b"PK..." + b"x" * 50), "application/zip")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    assert r.status_code == 201
    assert r.json()["media_type"] == "document"


@pytest.mark.asyncio
async def test_upload_photo_over_10mb_rejected(
    admin_client, make_committed, monkeypatch, tmp_path, clean_db
):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    big = b"\x89PNG\r\n\x1a\n" + b"x" * (11 * 1024 * 1024)
    files = {"file": ("big.png", io.BytesIO(big), "image/png")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    assert r.status_code == 422
    assert "MB" in r.json()["detail"]


@pytest.mark.asyncio
async def test_upload_video_over_50mb_rejected(
    admin_client, make_committed, monkeypatch, tmp_path, clean_db
):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    big = b"\x00" * (51 * 1024 * 1024)
    files = {"file": ("huge.mp4", io.BytesIO(big), "video/mp4")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(
    admin_client, make_committed, monkeypatch, tmp_path, clean_db
):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    files = {"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_order_idx_increments(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    for i in range(3):
        files = {"file": (f"f{i}.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 10), "image/png")}
        r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
        assert r.status_code == 201
        assert r.json()["order_idx"] == i


@pytest.mark.asyncio
async def test_reorder(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    ids = []
    for i in range(3):
        files = {"file": (f"f{i}.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 10), "image/png")}
        r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
        ids.append(r.json()["id"])
    # Переставить наоборот: 2, 0, 1
    new_order = [ids[2], ids[0], ids[1]]
    r = await admin_client.patch(
        f"/api/funnel-steps/{step.id}/media/reorder",
        json={"ordered_ids": new_order},
    )
    assert r.status_code == 200
    after = r.json()
    assert [m["id"] for m in after] == new_order
    assert [m["order_idx"] for m in after] == [0, 1, 2]


@pytest.mark.asyncio
async def test_update_caption(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    files = {"file": ("f.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 10), "image/png")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    media_id = r.json()["id"]
    r = await admin_client.patch(
        f"/api/funnel-step-media/{media_id}", json={"caption": "Привет мир"}
    )
    assert r.status_code == 200
    assert r.json()["caption"] == "Привет мир"


@pytest.mark.asyncio
async def test_delete(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    files = {"file": ("f.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 10), "image/png")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    media_id = r.json()["id"]
    r = await admin_client.delete(f"/api/funnel-step-media/{media_id}")
    assert r.status_code == 204
    r = await admin_client.get(f"/api/funnel-steps/{step.id}/media")
    assert r.json() == []


@pytest.mark.asyncio
async def test_max_10_media_per_step(
    admin_client, make_committed, monkeypatch, tmp_path, clean_db
):
    """11-й файл на шаг отвергается с 422."""
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    step = await make_committed.funnel_step()
    for _ in range(10):
        files = {"file": ("f.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 10), "image/png")}
        r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
        assert r.status_code == 201
    # 11-й
    files = {"file": ("over.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 10), "image/png")}
    r = await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)
    assert r.status_code == 422
    assert "10" in r.json()["detail"]


@pytest.mark.asyncio
async def test_funnel_detail_includes_media(
    admin_client, make_committed, monkeypatch, tmp_path, clean_db
):
    """GET /api/funnels/{id} возвращает шаги с массивом media[]."""
    monkeypatch.setattr("app.services.step_media.STORAGE_DIR", tmp_path)
    funnel = await make_committed.funnel()
    step = await make_committed.funnel_step(funnel_id=funnel.id)
    files = {"file": ("f.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 10), "image/png")}
    await admin_client.post(f"/api/funnel-steps/{step.id}/media", files=files)

    r = await admin_client.get(f"/api/funnels/{funnel.id}")
    assert r.status_code == 200
    steps = r.json()["steps"]
    assert len(steps) >= 1
    target_step = next(s for s in steps if s["id"] == step.id)
    assert len(target_step["media"]) == 1
    assert target_step["media"][0]["media_type"] == "photo"
