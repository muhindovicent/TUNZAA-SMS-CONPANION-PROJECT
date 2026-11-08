"""Double-submit CSRF protection bound to server-side sessions."""

from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

from flask import Response, g, request

from tunza.config import Settings
from tunza.security.fields import FieldCipher

CSRF_COOKIE = "tunza_csrf"
CSRF_HEADER = "X-CSRF-Token"
CSRF_FORM_FIELD = "csrf_token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def new_csrf_token(settings: Settings) -> str:
    token = secrets.token_urlsafe(32)
    signature = hmac.new(
        settings.secret_key.get_secret_value().encode(), token.encode(), sha256
    ).hexdigest()
    return f"{token}.{signature}"


def valid_csrf_token(settings: Settings, value: str | None) -> bool:
    if not value or "." not in value:
        return False
    token, signature = value.rsplit(".", 1)
    expected = hmac.new(
        settings.secret_key.get_secret_value().encode(), token.encode(), sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=settings.session_absolute_seconds,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="Lax",
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(CSRF_COOKIE, path="/")


def enforce_csrf(settings: Settings) -> Response | None:
    """Reject unsafe requests without a valid double-submit and session token."""

    if request.method in SAFE_METHODS:
        return None
    supplied = request.headers.get(CSRF_HEADER) or request.form.get(CSRF_FORM_FIELD)
    cookie = request.cookies.get(CSRF_COOKIE)
    if not supplied or not cookie:
        return _reject()
    if not hmac.compare_digest(supplied, cookie):
        return _reject()
    if not valid_csrf_token(settings, supplied):
        return _reject()
    session = g.get("auth_session")
    if session is not None:
        cipher = FieldCipher.from_settings(settings)
        if not hmac.compare_digest(cipher.hash_token(supplied), session.csrf_token_hash):
            return _reject()
    return None


def _reject() -> Response:
    from tunza.web.errors import error_response

    return error_response("csrf_invalid", "CSRF token missing or invalid.", 403)
