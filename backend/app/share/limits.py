"""Лимиты Telegram Bot API + пайплайна загрузки медиа.

Эти значения — фактический потолок, при превышении которого Telegram
вернёт 4xx и сообщение не уедет. Используются при валидации upload
(заранее отказываем пользователю) и в worker'е отправки (решаем, можно
ли слать напрямую через Bot API или нужен fallback).

Источник правды для значений: https://core.telegram.org/bots/api
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Bot API лимиты (на каждое отдельное сообщение / медиа в group)
# ─────────────────────────────────────────────────────────────────────────────

# sendPhoto принимает до 10 MB; Telegram сжимает фото при отправке.
PHOTO_LIMIT_BYTES = 10 * 1024 * 1024  # 10 MB

# sendVideo / sendAudio / sendDocument / sendAnimation / sendVoice — до 50 MB
# на стандартном api.telegram.org. Local Bot API позволяет до 2 GB, но это
# отдельная инфраструктура и в Grammy сейчас не используется.
GENERIC_LIMIT_BYTES = 50 * 1024 * 1024  # 50 MB

# Максимум элементов в media-group (sendMediaGroup). Принудительный лимит
# Telegram. На фронте upload-формы и при reorder это значение тоже не
# должно превышаться.
MEDIA_GROUP_MAX = 10

# Caption под одиночным медиа или альбомом. Чистый текст без HTML-разметки;
# теги обычно не считаются, но для перестраховки оставляем запас.
CAPTION_MAX_LENGTH = 1024

# Полноценное текстовое сообщение (sendMessage) — до 4096 символов.
TEXT_MAX_LENGTH = 4096

# ─────────────────────────────────────────────────────────────────────────────
# Загрузка
# ─────────────────────────────────────────────────────────────────────────────

# Жёсткий потолок на загружаемый файл. Свыше — отказ ещё до записи на диск.
# Совпадает с DB-CHECK на funnel_step_media.file_size.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


# ─────────────────────────────────────────────────────────────────────────────
# MIME → media type
# ─────────────────────────────────────────────────────────────────────────────

IMAGE_MIMES: frozenset[str] = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
})
ANIMATION_MIMES: frozenset[str] = frozenset({
    "image/gif",
})
VIDEO_MIMES: frozenset[str] = frozenset({
    "video/mp4",
    "video/quicktime",
    "video/webm",
})
AUDIO_MIMES: frozenset[str] = frozenset({
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
})


def infer_media_type(mime: str) -> str:
    """Возвращает один из: photo | animation | video | audio | document."""
    if mime in IMAGE_MIMES:
        return "photo"
    if mime in ANIMATION_MIMES:
        return "animation"
    if mime in VIDEO_MIMES:
        return "video"
    if mime in AUDIO_MIMES:
        return "audio"
    return "document"


def exceeds_send_limit(media_type: str, file_size: int, *, has_file_id: bool = False) -> bool:
    """True если файл слишком большой для прямой отправки в Telegram.

    Если у файла уже есть `telegram_file_id` — он живёт на CDN Telegram,
    лимит на него больше не действует (переиспользуется бесплатно).
    """
    if has_file_id:
        return False
    if media_type == "photo":
        return file_size > PHOTO_LIMIT_BYTES
    return file_size > GENERIC_LIMIT_BYTES
