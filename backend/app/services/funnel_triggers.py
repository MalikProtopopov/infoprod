"""FunnelTriggersService — case-insensitive lookup кодовых слов."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.funnel_trigger import FunnelTrigger


class TriggerConflictError(Exception):
    pass


class InvalidTriggerWordError(Exception):
    pass


def _normalize(word: str) -> str:
    return word.strip().lower()


def _validate(word: str) -> None:
    norm = _normalize(word)
    if len(norm) < 2 or len(norm) > 64:
        raise InvalidTriggerWordError("Слово должно быть от 2 до 64 символов")
    # Запрещаем пробелы внутри триггера — это слово, не фраза
    if any(c.isspace() for c in norm):
        raise InvalidTriggerWordError("Слово не может содержать пробелы")


class FunnelTriggersService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, word: str, funnel_id: int) -> FunnelTrigger:
        _validate(word)
        normalized = _normalize(word)
        # Проверка уникальности lower(word)
        existing = (
            await self.session.execute(
                select(FunnelTrigger).where(func.lower(FunnelTrigger.word) == normalized)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise TriggerConflictError(f"Слово '{normalized}' уже используется")

        trigger = FunnelTrigger(word=normalized, funnel_id=funnel_id, is_active=True)
        self.session.add(trigger)
        await self.session.flush()
        return trigger

    async def find_by_word(self, text: str) -> Optional[FunnelTrigger]:
        normalized = _normalize(text)
        if not normalized:
            return None
        return (
            await self.session.execute(
                select(FunnelTrigger).where(
                    func.lower(FunnelTrigger.word) == normalized,
                    FunnelTrigger.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def increment_use_count(self, trigger_id: int) -> None:
        await self.session.execute(
            update(FunnelTrigger)
            .where(FunnelTrigger.id == trigger_id)
            .values(use_count=FunnelTrigger.use_count + 1)
        )

    async def update(self, trigger_id: int, *,
                     is_active: bool | None = None,
                     word: str | None = None) -> FunnelTrigger | None:
        t = await self.session.get(FunnelTrigger, trigger_id)
        if t is None:
            return None
        if word is not None:
            _validate(word)
            new = _normalize(word)
            if new != t.word.lower():
                clash = (
                    await self.session.execute(
                        select(FunnelTrigger).where(
                            func.lower(FunnelTrigger.word) == new,
                            FunnelTrigger.id != trigger_id,
                        )
                    )
                ).scalar_one_or_none()
                if clash is not None:
                    raise TriggerConflictError(f"Слово '{new}' уже используется")
                t.word = new
        if is_active is not None:
            t.is_active = is_active
        return t

    async def delete(self, trigger_id: int) -> bool:
        t = await self.session.get(FunnelTrigger, trigger_id)
        if t is None:
            return False
        await self.session.delete(t)
        return True
