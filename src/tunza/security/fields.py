"""Field encryption and keyed hashing for personal identifiers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from tunza.config import AppEnv, Settings

SCHEMA_VERSION = "v1"


def _decode_key(value: str, fallback: str) -> bytes:
    candidate = value.strip()
    try:
        decoded = base64.urlsafe_b64decode(candidate + "=" * (-len(candidate) % 4))
    except (ValueError, TypeError):
        decoded = b""
    if len(decoded) == 32:
        return decoded
    digest = hashlib.sha256(f"{fallback}:{candidate}".encode()).digest()
    return digest


def derive_key(secret: str, purpose: str) -> bytes:
    """Derive a purpose-bound key for local development and tests."""

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"tunza-local-key-v1",
        info=purpose.encode(),
    ).derive(secret.encode())


@dataclass(frozen=True)
class FieldCipher:
    """AES-256-GCM field encryption plus HMAC-SHA-256 lookup hashes."""

    field_key: bytes
    hmac_key: bytes

    @classmethod
    def from_settings(cls, settings: Settings) -> FieldCipher:
        secret = settings.secret_key.get_secret_value()
        if settings.field_encryption_key is None:
            if settings.app_env in {AppEnv.staging, AppEnv.production}:
                raise RuntimeError("FIELD_ENCRYPTION_KEY is required")
            field_key = derive_key(secret, "field-encryption")
        else:
            field_key = _decode_key(
                settings.field_encryption_key.get_secret_value(), "field-encryption"
            )
        if settings.phone_hmac_key is None:
            if settings.app_env in {AppEnv.staging, AppEnv.production}:
                raise RuntimeError("PHONE_HMAC_KEY is required")
            hmac_key = derive_key(secret, "phone-hmac")
        else:
            hmac_key = _decode_key(
                settings.phone_hmac_key.get_secret_value(), "phone-hmac"
            )
        return cls(field_key=field_key, hmac_key=hmac_key)

    @property
    def key_id(self) -> str:
        return hashlib.sha256(self.field_key).hexdigest()[:8]

    def encrypt(self, value: str) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self.field_key).encrypt(nonce, value.encode(), None)
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode().rstrip("=")
        return f"{SCHEMA_VERSION}:{self.key_id}:{payload}"

    def decrypt(self, value: str) -> str:
        version, key_id, payload = value.split(":", 2)
        if version != SCHEMA_VERSION:
            raise ValueError("Unsupported ciphertext version")
        if key_id != self.key_id:
            raise ValueError("Ciphertext uses a different key")
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        return AESGCM(self.field_key).decrypt(raw[:12], raw[12:], None).decode()

    def hmac_hex(self, value: str) -> str:
        return hmac.new(self.hmac_key, value.encode(), hashlib.sha256).hexdigest()

    def hash_token(self, token: str) -> str:
        return self.hmac_hex(f"token:{token}")

    def hash_otp(self, challenge_id: str, code: str) -> str:
        return self.hmac_hex(f"otp:{challenge_id}:{code}")

    def hash_ip(self, value: str) -> str:
        return self.hmac_hex(f"ip:{value}")

    def hash_user_agent(self, value: str) -> str:
        return self.hmac_hex(f"user-agent:{value}")
