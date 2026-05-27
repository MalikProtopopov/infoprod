from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.bot import manager as bot_manager
from app.models.admin import Admin
from app.models.channel import Channel
from app.models.payment import Payment
from app.models.payment_receipt import PaymentReceipt
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.payment import PaymentOut, PaymentUpdate, ReceiptOut
from app.services import subscriptions as sub_service

router = APIRouter(prefix="/payments", tags=["payments"])

# Чеки платежа: только загрузка (без edit/delete), до 3 на платёж.
RECEIPTS_DIR = Path(os.environ.get("RECEIPTS_DIR", "/var/lib/infobizbot/receipts"))
MAX_RECEIPTS = 3
RECEIPT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
ALLOWED_RECEIPT_MIMES = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf",
}
_EXT_BY_MIME = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "application/pdf": ".pdf",
}


def _receipt_out(r: PaymentReceipt) -> ReceiptOut:
    return ReceiptOut(
        id=r.id,
        mime_type=r.mime_type,
        is_image=r.mime_type.startswith("image/"),
        original_filename=r.original_filename,
        created_at=r.created_at,
    )


def _to_out(
    p: Payment,
    user: User | None = None,
    product_name: str | None = None,
    receipts: list[PaymentReceipt] | None = None,
) -> PaymentOut:
    return PaymentOut(
        id=p.id,
        user_id=p.user_id,
        user_username=getattr(user, "username", None) if user else None,
        user_first_name=getattr(user, "first_name", None) if user else None,
        product_id=p.product_id,
        product_name=product_name,
        period_months=p.period_months,
        amount=p.amount,
        currency=p.currency,
        comment=p.comment,
        created_at=p.created_at,
        receipts=[_receipt_out(r) for r in (receipts or [])],
    )


def _price_for_period(product: Product, period_months: int) -> Decimal:
    return {3: product.price_3m, 6: product.price_6m, 12: product.price_12m}[period_months]


@router.get("", response_model=list[PaymentOut])
async def list_payments(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    user_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
) -> list[PaymentOut]:
    stmt = (
        select(Payment, User, Product.name)
        .join(User, User.id == Payment.user_id)
        .join(Product, Product.id == Payment.product_id)
        .order_by(Payment.id.desc())
    )
    if user_id is not None:
        stmt = stmt.where(Payment.user_id == user_id)
    if product_id is not None:
        stmt = stmt.where(Payment.product_id == product_id)
    rows = (await session.execute(stmt)).all()

    # Чеки одним запросом для всех платежей страницы (для превью в списке).
    payment_ids = [p.id for p, _, _ in rows]
    receipts_by_payment: dict[int, list[PaymentReceipt]] = {}
    if payment_ids:
        rcpts = (
            await session.execute(
                select(PaymentReceipt)
                .where(PaymentReceipt.payment_id.in_(payment_ids))
                .order_by(PaymentReceipt.id)
            )
        ).scalars().all()
        for r in rcpts:
            receipts_by_payment.setdefault(r.payment_id, []).append(r)

    return [_to_out(p, u, pn, receipts_by_payment.get(p.id)) for p, u, pn in rows]


@router.post("", response_model=PaymentOut, status_code=201)
async def create_payment(
    user_id: int = Form(...),
    product_id: int = Form(...),
    period_months: int = Form(...),
    amount: str | None = Form(None),
    comment: str | None = Form(None),
    # Чек обязателен: платёж нельзя создать без подтверждения оплаты.
    # Атомарно с созданием платежа — нет платежа без чека даже через API.
    receipts: list[UploadFile] = File(...),
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    if period_months not in (3, 6, 12):
        raise HTTPException(status_code=422, detail="Период должен быть 3, 6 или 12 месяцев")

    # Проверяем и читаем чеки ДО любых side-effect'ов (выдача доступа/инвайт).
    staged = await _read_receipts_or_422(receipts)

    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
    product = (
        await session.execute(select(Product).where(Product.id == product_id))
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=400, detail="Продукт не найден")

    channel = (
        await session.execute(select(Channel).where(Channel.id == product.channel_id))
    ).scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=400, detail="Канал продукта не найден")
    if bot_manager.get_aiogram_bot(channel.bot_id) is None:
        raise HTTPException(
            status_code=409,
            detail="Бот канала неактивен или не запущен — невозможно выдать доступ. Активируйте бота в разделе «Боты».",
        )

    amount_dec: Decimal | None = None
    if amount is not None and str(amount).strip() != "":
        try:
            amount_dec = Decimal(str(amount))
        except Exception:
            raise HTTPException(status_code=422, detail="Некорректная сумма")
        if amount_dec < 0:
            raise HTTPException(status_code=422, detail="Сумма не может быть отрицательной")
    final_amount = amount_dec if amount_dec is not None else _price_for_period(product, period_months)

    # Last-touch атрибуция платежа: наследуется от самой свежей заявки этой пары user+product
    # (если таковая есть и в ней проставлен tracking_link_id)
    from app.models.lead import Lead
    last_lead_tl = (
        await session.execute(
            select(Lead.tracking_link_id)
            .where(
                Lead.user_id == user.id,
                Lead.product_id == product.id,
                Lead.tracking_link_id.is_not(None),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    payment = Payment(
        user_id=user.id,
        product_id=product.id,
        period_months=period_months,
        amount=final_amount,
        currency=product.currency,
        comment=comment,
        admin_id=admin.id,
        tracking_link_id=last_lead_tl,
    )
    session.add(payment)
    await session.flush()  # получить id

    await sub_service.grant_for_payment(session, payment)

    # Автоматически отмечаем последнюю заявку этого user+product как paid
    from datetime import datetime, timezone
    last_lead = (
        await session.execute(
            select(Lead)
            .where(
                Lead.user_id == user.id,
                Lead.product_id == product.id,
                Lead.status.in_(["new", "contacted"]),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_lead is not None:
        last_lead.status = "paid"
        if last_lead.paid_at is None:
            last_lead.paid_at = datetime.now(tz=timezone.utc)
        # Привязываем платёж к заявке (обратная связь для целостности).
        last_lead.payment_id = payment.id

    # NEW: автоотмена активных воронок на этот продукт
    from app.services.funnels import FunnelsService
    funnels_svc = FunnelsService(session)
    await funnels_svc.cancel_entries_for_user_on_payment(
        user_id=user.id, product_id=product.id,
    )

    # Сохраняем чеки на диск + строки (в той же транзакции — атомарно с платежом).
    receipt_rows = _save_staged_receipts(session, payment.id, admin.id, staged)

    # Аудит создания платежа пишет AuditMiddleware (POST /payments → payment/create).

    await session.commit()
    await session.refresh(payment)

    return _to_out(payment, user, product.name, receipt_rows)


@router.patch("/{payment_id}", response_model=PaymentOut)
async def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    p = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payload.comment is not None:
        p.comment = payload.comment
    await session.commit()
    await session.refresh(p)
    return _to_out(p)


@router.delete("/{payment_id}", status_code=204, response_class=Response)
async def delete_payment(
    payment_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    p = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Отозвать связанные подписки
    subs = (
        await session.execute(select(Subscription).where(Subscription.payment_id == p.id))
    ).scalars().all()
    for s in subs:
        if s.status == "active":
            await sub_service.revoke(session, s, status="revoked", notify=True)

    await session.delete(p)
    await session.commit()
    return Response(status_code=204)


# ===================== Чеки платежа (только загрузка) =====================

def _resolve_receipt_mime(file: UploadFile) -> str | None:
    """Определяет mime чека: content_type, иначе по расширению имени файла."""
    mime = (file.content_type or "").lower().split(";")[0].strip()
    if mime in ALLOWED_RECEIPT_MIMES:
        return mime
    name = (file.filename or "").lower()
    by_ext = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf",
    }
    for ext, m in by_ext.items():
        if name.endswith(ext):
            return m
    return None


async def _read_receipts_or_422(files: list[UploadFile]) -> list[tuple[str | None, str, bytes]]:
    """Валидирует и читает чеки. Требует ≥1, ≤MAX_RECEIPTS. 422/413/415 при проблемах."""
    real = [f for f in files if f is not None and f.filename]
    if not real:
        raise HTTPException(
            status_code=422, detail="Чек обязателен — приложите подтверждение оплаты"
        )
    if len(real) > MAX_RECEIPTS:
        raise HTTPException(status_code=422, detail=f"Не более {MAX_RECEIPTS} чеков")
    staged: list[tuple[str | None, str, bytes]] = []
    for f in real:
        mime = _resolve_receipt_mime(f)
        if mime is None:
            raise HTTPException(
                status_code=415,
                detail="Чек: допустимы изображения (jpg/png/webp/gif) или PDF",
            )
        content = await f.read()
        if not content:
            raise HTTPException(status_code=422, detail="Пустой файл чека")
        if len(content) > RECEIPT_MAX_BYTES:
            raise HTTPException(
                status_code=413, detail=f"Чек больше {RECEIPT_MAX_BYTES // (1024 * 1024)} МБ"
            )
        staged.append((f.filename, mime, content))
    return staged


def _save_staged_receipts(
    session: AsyncSession, payment_id: int, admin_id: int | None,
    staged: list[tuple[str | None, str, bytes]],
) -> list[PaymentReceipt]:
    """Пишет файлы на диск и создаёт строки PaymentReceipt (без commit)."""
    pdir = RECEIPTS_DIR / str(payment_id)
    pdir.mkdir(parents=True, exist_ok=True)
    rows: list[PaymentReceipt] = []
    for filename, mime, content in staged:
        dst = pdir / f"{uuid.uuid4().hex}{_EXT_BY_MIME.get(mime, '')}"
        dst.write_bytes(content)
        rec = PaymentReceipt(
            payment_id=payment_id,
            storage_path=str(dst),
            original_filename=filename,
            mime_type=mime,
            file_size=len(content),
            uploaded_by=admin_id,
        )
        session.add(rec)
        rows.append(rec)
    return rows


@router.get("/{payment_id}/receipts", response_model=list[ReceiptOut])
async def list_receipts(
    payment_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ReceiptOut]:
    rows = (
        await session.execute(
            select(PaymentReceipt)
            .where(PaymentReceipt.payment_id == payment_id)
            .order_by(PaymentReceipt.id)
        )
    ).scalars().all()
    return [_receipt_out(r) for r in rows]


@router.post("/{payment_id}/receipts", response_model=list[ReceiptOut], status_code=201)
async def upload_receipt(
    payment_id: int,
    file: UploadFile = File(...),
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ReceiptOut]:
    payment = (
        await session.execute(select(Payment).where(Payment.id == payment_id))
    ).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    existing = (
        await session.execute(
            select(PaymentReceipt)
            .where(PaymentReceipt.payment_id == payment_id)
            .order_by(PaymentReceipt.id)
        )
    ).scalars().all()
    if len(existing) >= MAX_RECEIPTS:
        raise HTTPException(status_code=409, detail=f"Уже загружено {MAX_RECEIPTS} чека — лимит")

    mime = _resolve_receipt_mime(file)
    if mime is None:
        raise HTTPException(
            status_code=415, detail="Допустимы изображения (jpg/png/webp/gif) или PDF"
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Пустой файл")
    if len(content) > RECEIPT_MAX_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Файл больше {RECEIPT_MAX_BYTES // (1024 * 1024)} МБ"
        )

    pdir = RECEIPTS_DIR / str(payment_id)
    pdir.mkdir(parents=True, exist_ok=True)
    dst = pdir / f"{uuid.uuid4().hex}{_EXT_BY_MIME.get(mime, '')}"
    dst.write_bytes(content)

    rec = PaymentReceipt(
        payment_id=payment_id,
        storage_path=str(dst),
        original_filename=file.filename,
        mime_type=mime,
        file_size=len(content),
        uploaded_by=admin.id,
    )
    session.add(rec)
    await session.commit()
    # Аудит пишет AuditMiddleware (POST /payments/{id}/receipts).

    existing.append(rec)
    return [_receipt_out(r) for r in existing]


@router.get("/{payment_id}/receipts/{receipt_id}/file")
async def get_receipt_file(
    payment_id: int,
    receipt_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Отдаёт файл чека — для превью/полноэкранного просмотра во фронте."""
    rec = await session.get(PaymentReceipt, receipt_id)
    if rec is None or rec.payment_id != payment_id:
        raise HTTPException(status_code=404, detail="Чек не найден")
    if not rec.storage_path or not os.path.exists(rec.storage_path):
        raise HTTPException(status_code=404, detail="Файл не найден на диске")
    return FileResponse(
        rec.storage_path,
        media_type=rec.mime_type,
        filename=rec.original_filename or f"receipt_{receipt_id}",
    )
