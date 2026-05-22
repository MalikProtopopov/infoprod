"""Юнит-тесты модуля core/security: bcrypt + JWT."""
from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_bcrypt_string(self):
        h = hash_password("secret123")
        assert h.startswith("$2b$") or h.startswith("$2a$")
        assert len(h) >= 60

    def test_verify_correct_password(self):
        h = hash_password("MyP@ssw0rd!")
        assert verify_password("MyP@ssw0rd!", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("right")
        assert verify_password("wrong", h) is False

    def test_verify_empty_password(self):
        h = hash_password("right")
        assert verify_password("", h) is False

    def test_verify_handles_invalid_hash(self):
        # passlib возвращает False, не raise
        assert verify_password("any", "not-a-real-hash") is False

    def test_two_hashes_of_same_password_differ(self):
        # bcrypt salt должен делать каждый хеш уникальным
        assert hash_password("abc") != hash_password("abc")


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(subject="admin")
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "admin"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_decode_invalid_token_returns_none(self):
        assert decode_token("not.a.valid.jwt") is None

    def test_decode_garbage_returns_none(self):
        assert decode_token("") is None
        assert decode_token("aaaa") is None

    def test_token_custom_ttl(self):
        from datetime import datetime, timezone

        # ttl=1 минута — exp близок к now + 60
        token = create_access_token(subject="x", expires_minutes=1)
        decoded = decode_token(token)
        assert decoded is not None
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        assert 55 < decoded["exp"] - now_ts <= 60
