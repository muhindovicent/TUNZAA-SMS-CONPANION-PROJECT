"""Organisation and tenant-settings operations."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from tunza.db.models import Organisation, OrganisationStatus
from tunza.modules.audit.service import record_audit
from tunza.modules.tenancy.models import TenantSettings
from tunza.security.fields import FieldCipher
from tunza.web.errors import ApiError

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CLOCK_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def slugify(name: str) -> str:
    normalised = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    )
    value = re.sub(r"[^a-z0-9]+", "-", normalised).strip("-")
    value = value[:63].strip("-")
    if len(value) < 3:
        raise ApiError("invalid_slug", "Organisation name is too short for a slug.", 422)
    return value


def get_organisation(session: Session, org_id: uuid.UUID) -> Organisation | None:
    return session.get(Organisation, org_id)


def create_organisation(
    session: Session,
    *,
    name: str,
    signatory_name: str,
    signatory_email: str,
    slug: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    languages: list[str] | None = None,
) -> Organisation:
    resolved_slug = (slug or slugify(name)).strip().lower()
    if not SLUG_PATTERN.fullmatch(resolved_slug) or len(resolved_slug) > 63:
        raise ApiError("invalid_slug", "Slug must contain lowercase letters, numbers and hyphens.", 422)
    if not name.strip() or len(name) > 200:
        raise ApiError("invalid_name", "Organisation name is required.", 422)
    if not signatory_name.strip() or not _looks_like_email(signatory_email):
        raise ApiError(
            "invalid_signatory",
            "Signatory name and a valid signatory email are required.",
            422,
        )
    exists = session.scalar(select(Organisation).where(Organisation.slug == resolved_slug))
    if exists is not None:
        raise ApiError("slug_taken", "That organisation slug is already in use.", 409)

    organisation = Organisation(
        slug=resolved_slug,
        name=name.strip(),
        status=OrganisationStatus.onboarding,
        signatory_name=signatory_name.strip(),
        signatory_email=signatory_email.strip().lower(),
    )
    session.add(organisation)
    session.flush()
    settings = TenantSettings(
        org_id=organisation.id,
        languages=languages or ["en", "lg"],
        updated_by_user_id=actor_user_id,
    )
    session.add(settings)
    record_audit(
        session,
        action="organisation.created",
        actor_user_id=actor_user_id,
        org_id=organisation.id,
        target_type="organisation",
        target_id=organisation.id,
        detail={"slug": organisation.slug},
    )
    session.flush()
    return organisation


def get_tenant_settings(session: Session, org_id: uuid.UUID) -> TenantSettings:
    row = session.get(TenantSettings, org_id)
    if row is None:
        row = TenantSettings(org_id=org_id)
        session.add(row)
        session.flush()
    return row


def update_tenant_settings(
    session: Session,
    *,
    org_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    changes: dict[str, object],
    cipher: FieldCipher,
) -> TenantSettings:
    row = get_tenant_settings(session, org_id)
    allowed = {
        "languages",
        "default_language",
        "timezone",
        "quiet_hours_start",
        "quiet_hours_end",
        "sender_id",
        "oidc_enabled",
        "oidc_issuer",
        "oidc_client_id",
        "oidc_client_secret",
        "oidc_allowed_domains",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ApiError("unknown_setting", "Unknown tenant setting.", 422)

    if "languages" in changes:
        languages = changes["languages"]
        if not isinstance(languages, list) or not languages or not all(
            isinstance(item, str) and re.fullmatch(r"[a-z]{2,8}", item) for item in languages
        ):
            raise ApiError("invalid_languages", "Languages must be valid codes.", 422)
        row.languages = [item.lower() for item in languages]
    if "default_language" in changes:
        value = str(changes["default_language"]).lower()
        if value not in row.languages:
            raise ApiError("invalid_language", "Default language must be enabled.", 422)
        row.default_language = value
    if "timezone" in changes:
        value = str(changes["timezone"])
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ApiError("invalid_timezone", "Unknown timezone.", 422) from None
        row.timezone = value
    for field_name in ("quiet_hours_start", "quiet_hours_end"):
        if field_name in changes:
            value = str(changes[field_name])
            if not CLOCK_PATTERN.fullmatch(value):
                raise ApiError("invalid_quiet_hours", "Quiet hours must use HH:MM.", 422)
            setattr(row, field_name, value)
    if "sender_id" in changes:
        value = changes["sender_id"]
        if value is not None and (not isinstance(value, str) or len(value) > 20):
            raise ApiError("invalid_sender_id", "Sender ID is too long.", 422)
        row.sender_id = value
    if "oidc_enabled" in changes:
        row.oidc_enabled = bool(changes["oidc_enabled"])
    for field_name in ("oidc_issuer", "oidc_client_id"):
        if field_name in changes:
            setattr(row, field_name, changes[field_name] or None)
    if "oidc_client_secret" in changes:
        secret = changes["oidc_client_secret"]
        row.oidc_client_secret_encrypted = (
            cipher.encrypt(str(secret)) if secret else None
        )
    if "oidc_allowed_domains" in changes:
        domains = changes["oidc_allowed_domains"]
        if not isinstance(domains, list) or not all(isinstance(item, str) for item in domains):
            raise ApiError("invalid_domains", "Allowed domains must be a list.", 422)
        row.oidc_allowed_domains = sorted(
            {item.strip().lower() for item in domains if item.strip()}
        )
    if row.oidc_enabled and not (row.oidc_issuer and row.oidc_client_id):
        raise ApiError("incomplete_oidc", "OIDC issuer and client ID are required.", 422)
    row.updated_by_user_id = actor_user_id
    record_audit(
        session,
        action="tenant_settings.updated",
        actor_user_id=actor_user_id,
        org_id=org_id,
        target_type="tenant_settings",
        target_id=org_id,
        detail={"fields": sorted(changes)},
    )
    session.flush()
    return row


def offboard_organisation(
    session: Session, *, org_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    organisation = session.get(Organisation, org_id)
    if organisation is None:
        raise ApiError("not_found", "Organisation not found.", 404)
    organisation.status = OrganisationStatus.offboarded
    organisation.offboarded_at = datetime.now(UTC)
    record_audit(
        session,
        action="organisation.offboarded",
        actor_user_id=actor_user_id,
        org_id=org_id,
        target_type="organisation",
        target_id=org_id,
    )
    session.flush()


def _looks_like_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()))


def trial_expiry(days: int = 30) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)
