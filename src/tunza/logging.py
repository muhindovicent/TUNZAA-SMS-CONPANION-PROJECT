"""Structured logging with personal-data redaction."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

from tunza.config import AppEnv, Settings

SENSITIVE_KEY_PARTS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "otp",
        "api_key",
        "authorization",
        "cookie",
        "session",
        "phone",
        "msisdn",
        "name",
        "body",
        "message_text",
        "guardian",
    }
)
SAFE_KEYS = frozenset(
    {
        "event",
        "logger",
        "level",
        "timestamp",
        "service",
        "module",
        "request_id",
        "org_id",
        "user_id",
        "role",
        "action",
        "object_type",
        "object_id",
        "outcome",
        "ip",
        "user_agent_hash",
        "job_name",
        "duration_ms",
    }
)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    if lowered in SAFE_KEYS:
        return False
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_sensitive(
    logger: Any,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Replace values under sensitive keys before rendering a log event."""

    for key in list(event_dict):
        if _is_sensitive(key):
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog once per process."""

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_sensitive,
    ]
    if settings.app_env in {AppEnv.development, AppEnv.test}:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level, format="%(message)s")
