"""Minimal RFC 6238 TOTP support without an extra runtime dependency."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
PERIOD_SECONDS = 30


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _decode_secret(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def code_at(secret: str, timestamp: int) -> str:
    counter = timestamp // PERIOD_SECONDS
    digest = hmac.new(
        _decode_secret(secret), struct.pack(">Q", counter), hashlib.sha1
    ).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10**DIGITS):0{DIGITS}d}"


def verify(secret: str, code: str, at_time: int | None = None, window: int = 1) -> bool:
    supplied = code.strip().replace(" ", "")
    if len(supplied) != DIGITS or not supplied.isdigit():
        return False
    now = int(time.time() if at_time is None else at_time)
    for offset in range(-window, window + 1):
        if hmac.compare_digest(code_at(secret, now + offset * PERIOD_SECONDS), supplied):
            return True
    return False


def provisioning_uri(secret: str, username: str, issuer: str = "Tunza") -> str:
    label = quote(f"{issuer}:{username}")
    return (
        f"otpauth://totp/{label}?secret={secret}"
        f"&issuer={quote(issuer)}&digits={DIGITS}&period={PERIOD_SECONDS}"
    )
