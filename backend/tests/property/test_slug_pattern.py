"""Property-based тесты для slug-генератора / валидатора через hypothesis."""
from __future__ import annotations

from hypothesis import given, strategies as st

from app.services.tracking_links import SLUG_LENGTH, SLUG_PATTERN


VALID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
INVALID_CHARS = " !@#$%^&*()=+[]{}|\\;:'\",.<>/?"


@given(st.text(alphabet=VALID_ALPHABET, min_size=4, max_size=64))
def test_valid_slugs_pass_regex(slug):
    assert SLUG_PATTERN.match(slug) is not None, f"valid slug rejected: {slug!r}"


@given(st.text(alphabet=VALID_ALPHABET, min_size=0, max_size=3))
def test_too_short_slugs_rejected(slug):
    assert SLUG_PATTERN.match(slug) is None, f"too short slug accepted: {slug!r}"


@given(st.text(alphabet=VALID_ALPHABET, min_size=65, max_size=100))
def test_too_long_slugs_rejected(slug):
    assert SLUG_PATTERN.match(slug) is None, f"too long slug accepted: {slug!r}"


@given(st.text(alphabet=INVALID_CHARS, min_size=4, max_size=64))
def test_invalid_chars_rejected(slug):
    assert SLUG_PATTERN.match(slug) is None, f"invalid chars accepted: {slug!r}"


@given(st.integers(min_value=4, max_value=64))
def test_arbitrary_length_with_valid_chars(length):
    """Любая длина в диапазоне с валидными символами должна проходить."""
    slug = "a" * length
    assert SLUG_PATTERN.match(slug) is not None


def test_default_slug_length_is_eight():
    assert SLUG_LENGTH == 8
