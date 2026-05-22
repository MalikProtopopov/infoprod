"""Unit-тесты для TrackingLinksService."""
from __future__ import annotations

import pytest

from app.services.tracking_links import (
    ConflictError,
    InvalidSlugError,
    SLUG_PATTERN,
    TrackingLinksService,
    product_code_conflicts_with_slug,
)


async def _make_product(session, factories, **overrides):
    """factories.Product() + flush — id уже есть."""
    product = factories.Product(**overrides)
    await session.flush()
    return product


@pytest.mark.asyncio
async def test_create_with_custom_slug(session, factories):
    product = await _make_product(session, factories)
    svc = TrackingLinksService(session)
    link = await svc.create(
        product_id=product.id, utm_source="instagram",
        utm_medium="reels", custom_slug="mycustom",
    )
    await session.flush()
    assert link.slug == "mycustom"
    assert link.utm_source == "instagram"
    assert link.utm_medium == "reels"
    assert link.is_active is True
    assert link.click_count == 0
    assert link.unique_users == 0


@pytest.mark.asyncio
async def test_create_autogenerates_8char_slug(session, factories):
    product = await _make_product(session, factories)
    svc = TrackingLinksService(session)
    link = await svc.create(product_id=product.id, utm_source="ig")
    await session.flush()
    assert len(link.slug) == 8
    assert SLUG_PATTERN.match(link.slug)


@pytest.mark.asyncio
async def test_invalid_custom_slug_raises(session, factories):
    product = await _make_product(session, factories)
    svc = TrackingLinksService(session)
    with pytest.raises(InvalidSlugError):
        await svc.create(product_id=product.id, utm_source="ig", custom_slug="ab")


@pytest.mark.asyncio
async def test_invalid_chars_in_slug_raises(session, factories):
    product = await _make_product(session, factories)
    svc = TrackingLinksService(session)
    with pytest.raises(InvalidSlugError):
        await svc.create(product_id=product.id, utm_source="ig", custom_slug="bad slug")


@pytest.mark.asyncio
async def test_collision_with_existing_link(session, factories):
    product = await _make_product(session, factories)
    factories.TrackingLink(slug="taken123", product=product)
    await session.flush()
    svc = TrackingLinksService(session)
    with pytest.raises(ConflictError, match="already taken"):
        await svc.create(product_id=product.id, utm_source="ig", custom_slug="taken123")


@pytest.mark.asyncio
async def test_collision_with_product_code(session, factories):
    await _make_product(session, factories, code="yoga12ab")
    p2 = await _make_product(session, factories)
    svc = TrackingLinksService(session)
    with pytest.raises(ConflictError, match="product"):
        await svc.create(product_id=p2.id, utm_source="ig", custom_slug="yoga12ab")


@pytest.mark.asyncio
async def test_find_by_slug_existing(session, factories):
    product = await _make_product(session, factories)
    link = factories.TrackingLink(slug="lookup12", product=product)
    await session.flush()
    svc = TrackingLinksService(session)
    found = await svc.find_by_slug("lookup12")
    assert found is not None
    assert found.id == link.id


@pytest.mark.asyncio
async def test_find_by_slug_missing(session):
    svc = TrackingLinksService(session)
    assert await svc.find_by_slug("nosuch01") is None


@pytest.mark.asyncio
async def test_increment_click_count(session, factories):
    product = await _make_product(session, factories)
    link = factories.TrackingLink(product=product)
    await session.flush()
    svc = TrackingLinksService(session)
    await svc.increment_click_count(link.id)
    await svc.increment_click_count(link.id)
    await svc.increment_click_count(link.id)
    await session.refresh(link)
    assert link.click_count == 3


@pytest.mark.asyncio
async def test_increment_unique_users(session, factories):
    product = await _make_product(session, factories)
    link = factories.TrackingLink(product=product)
    await session.flush()
    svc = TrackingLinksService(session)
    await svc.increment_unique_users(link.id)
    await svc.increment_unique_users(link.id)
    await session.refresh(link)
    assert link.unique_users == 2


@pytest.mark.asyncio
async def test_deactivate(session, factories):
    product = await _make_product(session, factories)
    link = factories.TrackingLink(product=product, is_active=True)
    await session.flush()
    svc = TrackingLinksService(session)
    await svc.deactivate(link.id)
    await session.refresh(link)
    assert link.is_active is False


@pytest.mark.asyncio
async def test_product_code_conflicts_with_slug_returns_true_when_slug_exists(session, factories):
    product = await _make_product(session, factories)
    factories.TrackingLink(slug="testslug", product=product)
    await session.flush()
    assert await product_code_conflicts_with_slug(session, "testslug") is True


@pytest.mark.asyncio
async def test_product_code_conflicts_with_slug_returns_false_when_no_slug(session):
    assert await product_code_conflicts_with_slug(session, "freecode") is False
