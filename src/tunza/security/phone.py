"""Phone normalisation, masking and HMAC lookup hashing."""

from __future__ import annotations

import hashlib
import hmac

UGANDA_COUNTRY_CODE = "256"
UGANDA_LOCAL_LENGTH = 10


def normalise_phone(value: str) -> str:
    """Return an E.164-style Ugandan number from common input formats."""

    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        raise ValueError("Phone number has no digits")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == UGANDA_LOCAL_LENGTH and digits.startswith("0"):
        digits = UGANDA_COUNTRY_CODE + digits[1:]
    return f"+{digits}"


def mask_phone(value: str) -> str:
    """Mask all but a short prefix and the last three digits."""

    cleaned = value.strip()
    if len(cleaned) <= 6:
        return "*" * len(cleaned)
    prefix_length = 4 if cleaned.startswith("+") else 3
    hidden = len(cleaned) - prefix_length - 3
    return f"{cleaned[:prefix_length]}{'*' * hidden}{cleaned[-3:]}"


def hmac_phone_hash(value: str, secret: str) -> str:
    """Return a deterministic hash for equality lookups without storing plaintext."""

    normalised = normalise_phone(value)
    return hmac.new(secret.encode("utf-8"), normalised.encode("utf-8"), hashlib.sha256).hexdigest()
