"""Form / FormField — самостоятельная сущность.

Форма — последовательный сбор полей из текстовых сообщений юзера.
По завершении создаётся Lead с заполненными ответами в extra_data.

product_id опционален: форму можно использовать без привязки к продукту
для чистого сбора данных (например, опрос в воронке без воронки продаж).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Form(Base):
    __tablename__ = "forms"
    __table_args__ = (
        Index("ix_forms_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Опционально: куда падает Lead после submit. Если NULL — Lead.product_id = NULL.
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    success_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Двумерный массив кнопок, показывается после success_message.
    # Формат: [[{"text": "...", "callback_data" / "url": "..."}, ...], ...]
    completion_buttons: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    fields: Mapped[List["FormField"]] = relationship(
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormField.order_idx",
    )


class FormField(Base):
    __tablename__ = "form_fields"
    __table_args__ = (
        Index("ix_form_fields_form_order", "form_id", "order_idx"),
        UniqueConstraint("form_id", "key", name="ix_form_fields_form_key"),
        CheckConstraint(
            "field_type IN ('text','phone','email','url','number')",
            name="ck_form_fields_field_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    form_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    # Ключ — стабильный идентификатор поля; используется в Lead.extra_data[key].
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="text", server_default="text"
    )
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    max_length: Mapped[int] = mapped_column(
        Integer, nullable=False, default=500, server_default="500"
    )

    form: Mapped["Form"] = relationship(back_populates="fields")
