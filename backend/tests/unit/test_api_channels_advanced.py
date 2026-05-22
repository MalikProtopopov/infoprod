"""Дополнительные тесты /api/channels: patch_channel, 404 cases, edge cases."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_patch_channel_updates_title(admin_client, make_committed, clean_db):
    channel = await make_committed.channel(title="Old name")
    r = await admin_client.patch(f"/api/channels/{channel.id}", json={"title": "New name"})
    assert r.status_code == 200
    assert r.json()["title"] == "New name"


@pytest.mark.asyncio
async def test_patch_channel_updates_username(admin_client, make_committed, clean_db):
    channel = await make_committed.channel(username=None)
    r = await admin_client.patch(f"/api/channels/{channel.id}", json={"username": "newuser"})
    assert r.status_code == 200
    assert r.json()["username"] == "newuser"


@pytest.mark.asyncio
async def test_patch_channel_no_changes(admin_client, make_committed, clean_db):
    """PATCH с пустым body не падает."""
    channel = await make_committed.channel()
    r = await admin_client.patch(f"/api/channels/{channel.id}", json={})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_patch_unknown_channel_404(admin_client, clean_db):
    r = await admin_client.patch("/api/channels/99999", json={"title": "X"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_channel_404(admin_client, clean_db):
    r = await admin_client.delete("/api/channels/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_channels_includes_bot_username(admin_client, make_committed, clean_db):
    bot = await make_committed.bot(username="thebot")
    await make_committed.channel(bot=bot)

    r = await admin_client.get("/api/channels")
    body = r.json()
    assert body[0]["bot_username"] == "thebot"


@pytest.mark.asyncio
async def test_list_channels_requires_auth(api_client):
    r = await api_client.get("/api/channels")
    assert r.status_code == 401
