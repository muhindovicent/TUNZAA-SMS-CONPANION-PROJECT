"""Password policy and Argon2id hashing."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12

COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "1234567890123",
        "12345678901234",
        "123456789012345",
        "password1234",
        "password12345",
        "password123456",
        "qwertyuiop12",
        "qwerty123456",
        "letmein12345",
        "welcome12345",
        "admin1234567",
        "changeme1234",
        "iloveyou1234",
        "monkey123456",
        "dragon123456",
        "football1234",
        "baseball1234",
        "sunshine1234",
        "princess1234",
        "trustno1234",
        "abc123456789",
        "passwordpassword",
        "passw0rdpassw0rd",
        "tunza1234567",
        "tunza12345678",
        "kampala12345",
        "uganda123456",
        "maternal1234",
        "pregnancy123",
        "mother123456",
        "baby12345678",
        "hospital1234",
        "clinic123456",
        "doctor123456",
        "nurse1234567",
        "vht123456789",
        "facility1234",
        "supervisor12",
        "reviewer1234",
        "partner12345",
        "administrator",
        "administrator1",
        "letmeinplease",
        "winter2026!!",
        "summer2026!!",
        "spring2026!!",
        "autumn2026!!",
        "january2026!",
        "february2026",
        "march2026!!!",
        "april2026!!!",
        "may2026!!!!!",
        "june2026!!!!",
        "july2026!!!!",
        "august2026!!",
        "september26!",
        "october2026!",
        "november2026",
        "december2026",
        "qwerty!@#$12",
        "1qaz2wsx3edc",
        "zaq12wsxcde3",
        "!qaz@wsx#edc",
        "password!@#$",
        "p@ssw0rd!234",
        "correcthorsebatterystaple",
        "thisisapassword",
        "thisisnottasecure",
        "dontuse12345",
    }
)

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("tunza-not-a-real-password")


def validate_password(password: str, username: str) -> str | None:
    """Return a safe, user-facing policy message, or None when acceptable."""

    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    lowered = password.casefold()
    if lowered in COMMON_PASSWORDS:
        return "Choose a less common password."
    if username and username.casefold() in lowered:
        return "Password must not contain the username."
    if len(set(password)) < 4:
        return "Choose a password with more variety."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy_password(password: str) -> None:
    """Spend comparable Argon2 time when the account does not exist."""

    try:
        _hasher.verify(_DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
