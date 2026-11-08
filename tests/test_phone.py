from __future__ import annotations

import pytest

from tunza.security.phone import hmac_phone_hash, mask_phone, normalise_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+256 700 000 001", "+256700000001"),
        ("0700000001", "+256700000001"),
        ("256700000001", "+256700000001"),
        ("00256700000001", "+256700000001"),
    ],
)
def test_normalise_phone(raw: str, expected: str) -> None:
    assert normalise_phone(raw) == expected


def test_normalise_phone_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        normalise_phone("no digits here")


def test_mask_phone_does_not_expose_the_number() -> None:
    masked = mask_phone("+256700000001")
    assert masked.startswith("+256")
    assert masked.endswith("001")
    assert masked.count("*") == 6


def test_hmac_phone_hash_is_deterministic_and_secret_bound() -> None:
    first = hmac_phone_hash("0700000001", "secret-a")
    second = hmac_phone_hash("+256700000001", "secret-a")
    different = hmac_phone_hash("0700000001", "secret-b")
    assert first == second
    assert first != different
    assert len(first) == 64
