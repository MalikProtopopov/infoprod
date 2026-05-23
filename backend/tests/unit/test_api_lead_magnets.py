"""API-тесты /api/lead-magnets — upload (multipart), CRUD."""
from __future__ import annotations

import io

import pytest


@pytest.mark.asyncio
async def test_list_empty(admin_client, clean_db):
    r = await admin_client.get("/api/lead-magnets")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_upload_pdf(admin_client, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.lead_magnets.STORAGE_DIR", tmp_path)
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 hello"), "application/pdf")}
    data = {"name": "Test PDF", "description": "Description"}
    r = await admin_client.post("/api/lead-magnets", files=files, data=data)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Test PDF"
    assert body["file_type"] == "pdf"
    assert body["file_size"] > 0


@pytest.mark.asyncio
async def test_upload_empty_file_422(admin_client, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.lead_magnets.STORAGE_DIR", tmp_path)
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    data = {"name": "Empty"}
    r = await admin_client.post("/api/lead-magnets", files=files, data=data)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_upload_with_product_id(admin_client, make_committed, monkeypatch, tmp_path, clean_db):
    monkeypatch.setattr("app.services.lead_magnets.STORAGE_DIR", tmp_path)
    product = await make_committed.product()
    files = {"file": ("guide.pdf", io.BytesIO(b"PDF data"), "application/pdf")}
    data = {"name": "Guide", "product_id": str(product.id)}
    r = await admin_client.post("/api/lead-magnets", files=files, data=data)
    assert r.status_code == 201
    assert r.json()["product_id"] == product.id


@pytest.mark.asyncio
async def test_get_lead_magnet(admin_client, make_committed, clean_db):
    lm = await make_committed.lead_magnet(name="Some LM")
    r = await admin_client.get(f"/api/lead-magnets/{lm.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Some LM"


@pytest.mark.asyncio
async def test_get_unknown_404(admin_client, clean_db):
    r = await admin_client.get("/api/lead-magnets/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_lead_magnet(admin_client, make_committed, clean_db):
    lm = await make_committed.lead_magnet(name="Old name", is_active=True)
    r = await admin_client.patch(
        f"/api/lead-magnets/{lm.id}",
        json={"name": "New name", "is_active": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "New name"
    assert body["is_active"] is False


@pytest.mark.asyncio
async def test_delete_lead_magnet(admin_client, make_committed, tmp_path, clean_db):
    # Файл должен существовать чтобы проверить что он удалится
    f = tmp_path / "to_delete.pdf"
    f.write_bytes(b"data")
    lm = await make_committed.lead_magnet(file_url=str(f))
    r = await admin_client.delete(f"/api/lead-magnets/{lm.id}")
    assert r.status_code == 204
    assert not f.exists()


@pytest.mark.asyncio
async def test_download_lead_magnet(admin_client, make_committed, tmp_path, clean_db):
    f = tmp_path / "download_me.pdf"
    f.write_bytes(b"PDF download data")
    lm = await make_committed.lead_magnet(file_url=str(f), file_type="pdf", name="Download")
    r = await admin_client.get(f"/api/lead-magnets/{lm.id}/download")
    assert r.status_code == 200
    assert "application/pdf" in r.headers["content-type"]
    assert r.content == b"PDF download data"


@pytest.mark.asyncio
async def test_download_missing_file_404(admin_client, make_committed, clean_db):
    lm = await make_committed.lead_magnet(file_url="/tmp/nonexistent_xyz.pdf")
    r = await admin_client.get(f"/api/lead-magnets/{lm.id}/download")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_requires_auth(api_client):
    r = await api_client.get("/api/lead-magnets")
    assert r.status_code == 401
