"""Request-scoped authentication context and authorization decorators."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from typing import Any, TypeVar

from flask import Flask, Response, current_app, g, request

from tunza.config import Settings
from tunza.db.engine import Database
from tunza.modules.identity.models import AuthSession, SessionStage, User, UserStatus
from tunza.modules.identity.service import (
    RequestMeta,
    as_utc,
    find_session_by_token,
    revoke_session,
    utcnow,
)
from tunza.security.csrf import clear_csrf_cookie
from tunza.security.fields import FieldCipher
from tunza.web.errors import ApiError, error_response

SESSION_COOKIE = "tunza_session"
F = TypeVar("F", bound=Callable[..., Any])


def get_database() -> Database:
    return current_app.extensions["tunza.db"]


def get_settings() -> Settings:
    return current_app.extensions["tunza.settings"]


def get_cipher() -> FieldCipher:
    cipher = current_app.extensions.get("tunza.cipher")
    if cipher is None:
        cipher = FieldCipher.from_settings(get_settings())
        current_app.extensions["tunza.cipher"] = cipher
    return cipher


def request_meta() -> RequestMeta:
    cipher = get_cipher()
    remote_addr = request.remote_addr or "unknown"
    user_agent = request.headers.get("User-Agent", "")
    return RequestMeta(
        ip_hash=cipher.hash_ip(remote_addr),
        user_agent_hash=cipher.hash_user_agent(user_agent) if user_agent else None,
    )


def current_user() -> User | None:
    return g.get("current_user")


def current_session() -> AuthSession | None:
    return g.get("auth_session")


def load_auth_session() -> None:
    settings = get_settings()
    g.current_user = None
    g.auth_session = None
    g.clear_auth_cookie = False
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        auth_session = find_session_by_token(session, cipher=cipher, token=token)
        if auth_session is None or auth_session.revoked_at is not None:
            g.clear_auth_cookie = True
            return
        now = utcnow()
        if (
            as_utc(auth_session.absolute_expires_at) <= now
            or as_utc(auth_session.idle_expires_at) <= now
        ):
            revoke_session(session, auth_session, reason="expired")
            session.commit()
            g.clear_auth_cookie = True
            return
        user = session.get(User, auth_session.user_id)
        if user is None or user.status in {UserStatus.suspended, UserStatus.deactivated}:
            revoke_session(session, auth_session, reason="inactive_user")
            session.commit()
            g.clear_auth_cookie = True
            return
        if user.access_expires_at is not None and as_utc(user.access_expires_at) <= now:
            revoke_session(session, auth_session, reason="access_expired")
            session.commit()
            g.clear_auth_cookie = True
            return
        if auth_session.org_id != user.org_id:
            revoke_session(session, auth_session, reason="org_mismatch")
            session.commit()
            g.clear_auth_cookie = True
            return
        auth_session.last_seen_at = now
        idle_seconds = (
            settings.session_privileged_idle_seconds
            if user.role.value
            in {"platform_owner", "platform_support", "org_admin", "clinical_reviewer", "dpo"}
            else settings.session_idle_seconds
        )
        auth_session.idle_expires_at = now + timedelta(seconds=idle_seconds)
        session.flush()
        g.current_user = user
        g.auth_session = auth_session


def apply_session_cookies(
    response: Response, *, token: str, csrf_token: str, settings: Settings | None = None
) -> Response:
    resolved = settings or get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=resolved.session_absolute_seconds,
        secure=resolved.session_cookie_secure,
        httponly=True,
        samesite="Lax",
        path="/",
    )
    from tunza.security.csrf import set_csrf_cookie

    set_csrf_cookie(response, csrf_token, resolved)
    return response


def clear_session_cookies(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    clear_csrf_cookie(response)
    return response


def after_auth_request(response: Response) -> Response:
    if g.get("clear_auth_cookie"):
        clear_session_cookies(response)
    return response


def require_active(func: F) -> F:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        auth_session = current_session()
        if auth_session is None or current_user() is None:
            raise ApiError("authentication_required", "Sign in is required.", 401)
        if auth_session.stage is not SessionStage.active:
            response = error_response(
                "stage_required", "Finish the remaining sign-in steps.", 403
            )
            response.headers["X-Tunza-Auth-Stage"] = auth_session.stage.value
            return response
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_stage(*stages: SessionStage) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            auth_session = current_session()
            if auth_session is None or current_user() is None:
                raise ApiError("authentication_required", "Sign in is required.", 401)
            if auth_session.stage not in stages:
                response = error_response(
                    "stage_required", "Finish the remaining sign-in steps.", 403
                )
                response.headers["X-Tunza-Auth-Stage"] = auth_session.stage.value
                return response
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def require_roles(*roles: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = current_user()
            if user is None:
                raise ApiError("authentication_required", "Sign in is required.", 401)
            if user.role.value not in roles:
                raise ApiError("forbidden", "You do not have permission.", 403)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def register_auth_context(app: Flask) -> None:
    app.before_request(load_auth_session)
    app.after_request(after_auth_request)
