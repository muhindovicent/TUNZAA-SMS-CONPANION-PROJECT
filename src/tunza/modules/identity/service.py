"""Identity, invitation, authentication and session operations."""

from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tunza.config import Settings
from tunza.db.models import Organisation, OrganisationStatus
from tunza.modules.audit.service import record_audit
from tunza.modules.identity.models import (
    PLATFORM_ROLES,
    TENANT_ROLES,
    AuthEvent,
    AuthOutcome,
    AuthSession,
    Invitation,
    InvitationApproval,
    InvitationStatus,
    MfaFactor,
    MfaKind,
    OtpChallenge,
    OtpPurpose,
    SessionStage,
    User,
    UserRole,
    UserStatus,
)
from tunza.security.csrf import new_csrf_token
from tunza.security.fields import FieldCipher
from tunza.security.passwords import (
    hash_password,
    validate_password,
    verify_dummy_password,
    verify_password,
)
from tunza.security.phone import normalise_phone
from tunza.security.totp import generate_secret, provisioning_uri, verify as verify_totp
from tunza.web.errors import ApiError

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")
PRIVILEGED_ROLES = frozenset(
    {
        UserRole.platform_owner,
        UserRole.platform_support,
        UserRole.org_admin,
        UserRole.clinical_reviewer,
        UserRole.dpo,
    }
)
APPROVAL_ROLES = frozenset(
    {
        UserRole.platform_owner,
        UserRole.platform_support,
        UserRole.org_admin,
        UserRole.clinical_reviewer,
        UserRole.dpo,
    }
)


@dataclass(frozen=True)
class RequestMeta:
    ip_hash: str | None = None
    user_agent_hash: str | None = None


@dataclass(frozen=True)
class SessionBundle:
    auth_session: AuthSession
    token: str
    csrf_token: str


@dataclass(frozen=True)
class LoginResult:
    user: User
    bundle: SessionBundle


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def required_approvals(role: UserRole) -> int:
    return 1 if role in APPROVAL_ROLES else 0


def _idle_seconds(user: User, settings: Settings) -> int:
    if user.role in PRIVILEGED_ROLES:
        return settings.session_privileged_idle_seconds
    return settings.session_idle_seconds


def _confirmed_factor(session: Session, user_id: uuid.UUID) -> MfaFactor | None:
    return session.scalar(
        select(MfaFactor)
        .where(MfaFactor.user_id == user_id, MfaFactor.confirmed_at.is_not(None))
        .order_by(MfaFactor.created_at.asc())
        .limit(1)
    )


def login_stage(session: Session, user: User) -> SessionStage:
    if user.phone_verified_at is None:
        return SessionStage.phone_verification
    if user.mfa_required:
        factor = _confirmed_factor(session, user.id)
        return SessionStage.factor_setup if factor is None else SessionStage.mfa_required
    return post_mfa_stage(user)


def post_mfa_stage(user: User) -> SessionStage:
    if user.confidentiality_accepted_at is None or user.orientation_completed_at is None:
        return SessionStage.orientation
    return SessionStage.active


def post_phone_stage(session: Session, user: User) -> SessionStage:
    if user.mfa_required:
        factor = _confirmed_factor(session, user.id)
        return SessionStage.factor_setup if factor is None else SessionStage.mfa_required
    return post_mfa_stage(user)


def create_session(
    session: Session,
    *,
    user: User,
    stage: SessionStage,
    settings: Settings,
    cipher: FieldCipher,
    meta: RequestMeta,
) -> SessionBundle:
    now = utcnow()
    token = secrets.token_urlsafe(32)
    csrf_token = new_csrf_token(settings)
    auth_session = AuthSession(
        user_id=user.id,
        org_id=user.org_id,
        token_hash=cipher.hash_token(token),
        csrf_token_hash=cipher.hash_token(csrf_token),
        stage=stage,
        idle_expires_at=now + timedelta(seconds=_idle_seconds(user, settings)),
        absolute_expires_at=now + timedelta(seconds=settings.session_absolute_seconds),
        last_seen_at=now,
        ip_hash=meta.ip_hash,
        user_agent_hash=meta.user_agent_hash,
    )
    session.add(auth_session)
    session.flush()
    return SessionBundle(auth_session=auth_session, token=token, csrf_token=csrf_token)


def rotate_session(
    session: Session,
    *,
    auth_session: AuthSession,
    user: User,
    stage: SessionStage,
    settings: Settings,
    cipher: FieldCipher,
    meta: RequestMeta,
) -> SessionBundle:
    if auth_session.revoked_at is not None:
        raise ApiError("session_revoked", "Session is no longer valid.", 401)
    now = utcnow()
    token = secrets.token_urlsafe(32)
    csrf_token = new_csrf_token(settings)
    auth_session.token_hash = cipher.hash_token(token)
    auth_session.csrf_token_hash = cipher.hash_token(csrf_token)
    auth_session.stage = stage
    auth_session.last_seen_at = now
    auth_session.idle_expires_at = now + timedelta(seconds=_idle_seconds(user, settings))
    if meta.ip_hash is not None:
        auth_session.ip_hash = meta.ip_hash
    if meta.user_agent_hash is not None:
        auth_session.user_agent_hash = meta.user_agent_hash
    session.flush()
    return SessionBundle(auth_session=auth_session, token=token, csrf_token=csrf_token)


def revoke_session(
    session: Session, auth_session: AuthSession, *, reason: str
) -> None:
    if auth_session.revoked_at is None:
        auth_session.revoked_at = utcnow()
        auth_session.revoked_reason = reason[:64]
        session.flush()


def revoke_user_sessions(
    session: Session,
    *,
    user_id: uuid.UUID,
    reason: str,
    except_session_id: uuid.UUID | None = None,
) -> None:
    now = utcnow()
    rows = session.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()
    for row in rows:
        if except_session_id is not None and row.id == except_session_id:
            continue
        row.revoked_at = now
        row.revoked_reason = reason[:64]
    session.flush()


def find_session_by_token(
    session: Session, *, cipher: FieldCipher, token: str
) -> AuthSession | None:
    return session.scalar(
        select(AuthSession).where(AuthSession.token_hash == cipher.hash_token(token))
    )


def check_login_ip_limit(
    session: Session, *, ip_hash: str | None, settings: Settings
) -> None:
    if ip_hash is None:
        return
    cutoff = utcnow() - timedelta(seconds=settings.login_ip_window_seconds)
    attempts = session.scalar(
        select(func.count())
        .select_from(AuthEvent)
        .where(
            AuthEvent.ip_hash == ip_hash,
            AuthEvent.event_type == "login",
            AuthEvent.outcome.in_(
                [AuthOutcome.failure, AuthOutcome.denied, AuthOutcome.locked]
            ),
            AuthEvent.created_at >= cutoff,
        )
    )
    if attempts is not None and attempts >= settings.login_ip_limit:
        raise ApiError(
            "rate_limited", "Too many login attempts. Try again later.", 429
        )


def _record_auth_event(
    session: Session,
    *,
    event_type: str,
    outcome: AuthOutcome,
    user: User | None,
    meta: RequestMeta,
    detail: str | None = None,
) -> None:
    session.add(
        AuthEvent(
            org_id=user.org_id if user else None,
            user_id=user.id if user else None,
            event_type=event_type,
            outcome=outcome,
            ip_hash=meta.ip_hash,
            user_agent_hash=meta.user_agent_hash,
            detail=detail,
        )
    )


def login(
    session: Session,
    *,
    settings: Settings,
    cipher: FieldCipher,
    username: str,
    password: str,
    meta: RequestMeta,
) -> LoginResult:
    check_login_ip_limit(session, ip_hash=meta.ip_hash, settings=settings)
    user = session.scalar(
        select(User).where(func.lower(User.username) == username.strip().lower())
    )
    if user is None:
        verify_dummy_password(password)
        _record_auth_event(
            session,
            event_type="login",
            outcome=AuthOutcome.failure,
            user=None,
            meta=meta,
            detail="unknown_user",
        )
        session.commit()
        raise ApiError("invalid_credentials", "Invalid username or password.", 401)

    now = utcnow()
    if user.locked_until is not None and as_utc(user.locked_until) > now:
        _record_auth_event(
            session,
            event_type="login",
            outcome=AuthOutcome.locked,
            user=user,
            meta=meta,
            detail="locked",
        )
        session.commit()
        raise ApiError("account_locked", "Account is temporarily locked.", 423)

    if user.status in {UserStatus.suspended, UserStatus.deactivated}:
        _record_auth_event(
            session,
            event_type="login",
            outcome=AuthOutcome.denied,
            user=user,
            meta=meta,
            detail=user.status.value,
        )
        session.commit()
        raise ApiError("account_unavailable", "Account is not available.", 403)

    if not verify_password(user.password_hash, password):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_failures:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            outcome = AuthOutcome.locked
        else:
            outcome = AuthOutcome.failure
        _record_auth_event(
            session,
            event_type="login",
            outcome=outcome,
            user=user,
            meta=meta,
            detail="bad_password",
        )
        record_audit(
            session,
            action="auth.login_failed",
            actor_user_id=user.id,
            org_id=user.org_id,
            target_type="user",
            target_id=user.id,
            ip_hash=meta.ip_hash,
            user_agent_hash=meta.user_agent_hash,
        )
        session.commit()
        if outcome is AuthOutcome.locked:
            raise ApiError("account_locked", "Account is temporarily locked.", 423)
        raise ApiError("invalid_credentials", "Invalid username or password.", 401)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    stage = login_stage(session, user)
    bundle = create_session(
        session,
        user=user,
        stage=stage,
        settings=settings,
        cipher=cipher,
        meta=meta,
    )
    _record_auth_event(
        session,
        event_type="login",
        outcome=AuthOutcome.success,
        user=user,
        meta=meta,
    )
    record_audit(
        session,
        action="auth.login",
        actor_user_id=user.id,
        org_id=user.org_id,
        target_type="user",
        target_id=user.id,
        ip_hash=meta.ip_hash,
        user_agent_hash=meta.user_agent_hash,
        detail={"stage": stage.value, "mfa": user.mfa_required},
    )
    session.commit()
    return LoginResult(user=user, bundle=bundle)


def issue_otp(
    session: Session,
    *,
    user: User,
    purpose: OtpPurpose,
    settings: Settings,
    cipher: FieldCipher,
    meta: RequestMeta,
) -> tuple[str, OtpChallenge]:
    now = utcnow()
    latest = session.scalar(
        select(OtpChallenge)
        .where(
            OtpChallenge.user_id == user.id,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
        )
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    if latest is not None and as_utc(latest.created_at) > now - timedelta(
        seconds=settings.otp_resend_seconds
    ):
        raise ApiError("otp_too_soon", "Wait before requesting another code.", 429)
    for challenge in session.scalars(
        select(OtpChallenge).where(
            OtpChallenge.user_id == user.id,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
        )
    ):
        challenge.consumed_at = now
    code = "000000" if settings.dev_console_otp else f"{secrets.randbelow(1_000_000):06d}"
    challenge = OtpChallenge(
        user_id=user.id,
        purpose=purpose,
        code_hash="",
        max_attempts=settings.otp_max_attempts,
        expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
        ip_hash=meta.ip_hash,
        created_at=now,
    )
    session.add(challenge)
    session.flush()
    challenge.code_hash = cipher.hash_otp(str(challenge.id), code)
    session.flush()
    return code, challenge


def verify_otp(
    session: Session,
    *,
    user: User,
    purpose: OtpPurpose,
    code: str,
    cipher: FieldCipher,
    meta: RequestMeta,
) -> OtpChallenge:
    now = utcnow()
    challenge = session.scalar(
        select(OtpChallenge)
        .where(
            OtpChallenge.user_id == user.id,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
        )
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    if challenge is None:
        raise ApiError("invalid_otp", "The code is invalid or has expired.", 401)
    if as_utc(challenge.expires_at) <= now or challenge.attempts >= challenge.max_attempts:
        challenge.consumed_at = now
        session.commit()
        raise ApiError("invalid_otp", "The code is invalid or has expired.", 401)
    expected = cipher.hash_otp(str(challenge.id), code.strip())
    if not secrets.compare_digest(expected, challenge.code_hash):
        challenge.attempts += 1
        if challenge.attempts >= challenge.max_attempts:
            challenge.consumed_at = now
        _record_auth_event(
            session,
            event_type="otp",
            outcome=AuthOutcome.failure,
            user=user,
            meta=meta,
            detail=purpose.value,
        )
        session.commit()
        raise ApiError("invalid_otp", "The code is invalid or has expired.", 401)
    challenge.consumed_at = now
    session.flush()
    return challenge


def create_sms_factor(session: Session, *, user: User) -> MfaFactor:
    existing = session.scalar(
        select(MfaFactor).where(MfaFactor.user_id == user.id, MfaFactor.kind == MfaKind.sms)
    )
    if existing is None:
        existing = MfaFactor(
            user_id=user.id,
            kind=MfaKind.sms,
            label="SMS",
            confirmed_at=utcnow(),
        )
        session.add(existing)
        session.flush()
    elif existing.confirmed_at is None:
        existing.confirmed_at = utcnow()
        session.flush()
    return existing


def start_totp_factor(
    session: Session,
    *,
    user: User,
    cipher: FieldCipher,
) -> tuple[MfaFactor, str]:
    secret = generate_secret()
    factor = session.scalar(
        select(MfaFactor).where(
            MfaFactor.user_id == user.id, MfaFactor.kind == MfaKind.totp
        )
    )
    if factor is not None and factor.confirmed_at is not None:
        raise ApiError("factor_exists", "An authenticator app is already configured.", 409)
    if factor is None:
        factor = MfaFactor(user_id=user.id, kind=MfaKind.totp, label="Authenticator")
        session.add(factor)
    factor.secret_encrypted = cipher.encrypt(secret)
    factor.confirmed_at = None
    session.flush()
    return factor, provisioning_uri(secret, user.username)


def confirm_totp_factor(
    session: Session,
    *,
    user: User,
    code: str,
    cipher: FieldCipher,
) -> MfaFactor:
    factor = session.scalar(
        select(MfaFactor).where(
            MfaFactor.user_id == user.id,
            MfaFactor.kind == MfaKind.totp,
            MfaFactor.confirmed_at.is_(None),
        )
    )
    if factor is None or factor.secret_encrypted is None:
        raise ApiError("factor_missing", "Start authenticator setup first.", 409)
    secret = cipher.decrypt(factor.secret_encrypted)
    if not verify_totp(secret, code):
        raise ApiError("invalid_totp", "The authenticator code is invalid.", 401)
    factor.confirmed_at = utcnow()
    factor.last_used_at = utcnow()
    session.flush()
    return factor


def verify_totp_factor(
    session: Session,
    *,
    user: User,
    code: str,
    cipher: FieldCipher,
) -> MfaFactor:
    factor = _confirmed_factor(session, user.id)
    if factor is None or factor.kind is not MfaKind.totp or factor.secret_encrypted is None:
        raise ApiError("factor_missing", "No authenticator factor is configured.", 409)
    secret = cipher.decrypt(factor.secret_encrypted)
    if not verify_totp(secret, code):
        raise ApiError("invalid_totp", "The authenticator code is invalid.", 401)
    factor.last_used_at = utcnow()
    session.flush()
    return factor


def decrypt_phone(user: User, cipher: FieldCipher) -> str:
    return cipher.decrypt(user.phone_encrypted)


def complete_orientation(
    session: Session,
    *,
    user: User,
    auth_session: AuthSession,
    settings: Settings,
    cipher: FieldCipher,
    meta: RequestMeta,
    accepted: bool,
) -> SessionBundle:
    if not accepted:
        raise ApiError(
            "acknowledgement_required",
            "You must acknowledge the confidentiality and orientation terms.",
            422,
        )
    now = utcnow()
    user.confidentiality_accepted_at = user.confidentiality_accepted_at or now
    user.orientation_completed_at = user.orientation_completed_at or now
    if user.status is UserStatus.pending_orientation:
        user.status = UserStatus.active
    bundle = rotate_session(
        session,
        auth_session=auth_session,
        user=user,
        stage=SessionStage.active,
        settings=settings,
        cipher=cipher,
        meta=meta,
    )
    record_audit(
        session,
        action="auth.orientation_accepted",
        actor_user_id=user.id,
        org_id=user.org_id,
        target_type="user",
        target_id=user.id,
    )
    session.commit()
    return bundle


def create_invitation(
    session: Session,
    *,
    actor: User,
    role: UserRole,
    phone: str,
    org_id: uuid.UUID | None,
    evidence: str | None,
    settings: Settings,
    cipher: FieldCipher,
) -> tuple[Invitation, str]:
    if actor.role is not UserRole.platform_owner and actor.role is not UserRole.org_admin:
        raise ApiError("forbidden", "You may not create invitations.", 403)
    if role in PLATFORM_ROLES:
        if actor.role is not UserRole.platform_owner:
            raise ApiError("forbidden", "Only a platform owner may invite this role.", 403)
        if org_id is not None:
            raise ApiError("invalid_org", "Platform roles must not belong to a tenant.", 422)
    else:
        if org_id is None:
            raise ApiError("org_required", "Tenant invitations require an organisation.", 422)
        if actor.role is UserRole.org_admin and actor.org_id != org_id:
            raise ApiError("forbidden", "You may only invite into your organisation.", 403)
        organisation = session.get(Organisation, org_id)
        if organisation is None or organisation.status is OrganisationStatus.offboarded:
            raise ApiError("invalid_org", "Organisation is not available.", 422)
    normalised = normalise_phone(phone)
    phone_hash = cipher.hmac_hex(normalised)
    if session.scalar(select(User).where(User.phone_hash == phone_hash)) is not None:
        raise ApiError("account_exists", "An account already uses this phone number.", 409)
    pending = session.scalar(
        select(Invitation).where(
            Invitation.phone_hash == phone_hash,
            Invitation.org_id == org_id,
            Invitation.status.in_(
                [InvitationStatus.pending_approval, InvitationStatus.approved]
            ),
        )
    )
    if pending is not None:
        raise ApiError("invitation_exists", "An invitation is already pending.", 409)
    approvals = required_approvals(role)
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        org_id=org_id,
        role=role,
        phone_hash=phone_hash,
        phone_encrypted=cipher.encrypt(normalised),
        token_hash=cipher.hash_token(token),
        status=InvitationStatus.pending_approval if approvals else InvitationStatus.approved,
        requested_by_user_id=actor.id,
        required_approvals=approvals,
        evidence=evidence,
        expires_at=(
            utcnow() + timedelta(hours=settings.invitation_ttl_hours)
            if approvals == 0
            else None
        ),
    )
    session.add(invitation)
    session.flush()
    record_audit(
        session,
        action="invitation.created",
        actor_user_id=actor.id,
        org_id=org_id,
        target_type="invitation",
        target_id=invitation.id,
        detail={"role": role.value, "approvals_required": approvals},
    )
    return invitation, token


def inspect_invitation(
    session: Session, *, token: str, cipher: FieldCipher
) -> dict[str, object]:
    invitation = _invitation_for_token(session, token=token, cipher=cipher, lock=False)
    _ensure_invitation_usable(session, invitation)
    organisation = session.get(Organisation, invitation.org_id) if invitation.org_id else None
    return {
        "role": invitation.role.value,
        "organisation": organisation.name if organisation else None,
        "expires_at": as_utc(invitation.expires_at).isoformat()
        if invitation.expires_at
        else None,
    }


def accept_invitation(
    session: Session,
    *,
    token: str,
    username: str,
    password: str,
    email: str | None,
    settings: Settings,
    cipher: FieldCipher,
    meta: RequestMeta,
) -> LoginResult:
    invitation = _invitation_for_token(session, token=token, cipher=cipher, lock=True)
    _ensure_invitation_usable(session, invitation)
    if invitation.accepted_user_id is not None:
        raise ApiError("invitation_used", "This invitation has already been used.", 409)
    if not USERNAME_PATTERN.fullmatch(username):
        raise ApiError("invalid_username", "Choose a valid username.", 422)
    username = username.strip()
    if session.scalar(select(User).where(func.lower(User.username) == username.lower())):
        raise ApiError("username_taken", "That username is already in use.", 409)
    password_error = validate_password(password, username)
    if password_error:
        raise ApiError("weak_password", password_error, 422)
    if email is not None:
        email = email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ApiError("invalid_email", "Email address is invalid.", 422)
    user = User(
        org_id=invitation.org_id,
        username=username,
        email=email,
        role=invitation.role,
        status=UserStatus.pending_orientation,
        password_hash=hash_password(password),
        password_changed_at=utcnow(),
        phone_hash=invitation.phone_hash,
        phone_encrypted=invitation.phone_encrypted,
        phone_verified_at=utcnow(),
    )
    session.add(user)
    session.flush()
    if user.mfa_required:
        create_sms_factor(session, user=user)
    invitation.status = InvitationStatus.accepted
    invitation.accepted_user_id = user.id
    invitation.accepted_at = utcnow()
    bundle = create_session(
        session,
        user=user,
        stage=SessionStage.orientation,
        settings=settings,
        cipher=cipher,
        meta=meta,
    )
    record_audit(
        session,
        action="invitation.accepted",
        actor_user_id=user.id,
        org_id=user.org_id,
        target_type="invitation",
        target_id=invitation.id,
        detail={"role": user.role.value},
    )
    session.commit()
    return LoginResult(user=user, bundle=bundle)


def approve_invitation(
    session: Session,
    *,
    actor: User,
    invitation_id: uuid.UUID,
    settings: Settings,
    cipher: FieldCipher,
) -> tuple[Invitation, bool, str | None]:
    invitation = session.scalar(
        select(Invitation).where(Invitation.id == invitation_id).with_for_update()
    )
    if invitation is None:
        raise ApiError("not_found", "Invitation not found.", 404)
    if invitation.status is not InvitationStatus.pending_approval:
        raise ApiError("invalid_state", "Invitation is not awaiting approval.", 409)
    if actor.id == invitation.requested_by_user_id:
        raise ApiError("self_approval", "Requesters may not approve their own invitation.", 403)
    if invitation.role in PLATFORM_ROLES:
        if actor.role is not UserRole.platform_owner:
            raise ApiError("forbidden", "Only a platform owner may approve this role.", 403)
    else:
        if actor.role is UserRole.platform_owner:
            pass
        elif actor.role is UserRole.org_admin and actor.org_id == invitation.org_id:
            pass
        else:
            raise ApiError("forbidden", "You may not approve this invitation.", 403)
    existing = session.scalar(
        select(InvitationApproval).where(
            InvitationApproval.invitation_id == invitation.id,
            InvitationApproval.approver_id == actor.id,
        )
    )
    if existing is not None:
        raise ApiError("already_approved", "You already approved this invitation.", 409)
    session.add(
        InvitationApproval(
            invitation_id=invitation.id,
            approver_id=actor.id,
            approver_role=actor.role,
        )
    )
    session.flush()
    count = session.scalar(
        select(func.count())
        .select_from(InvitationApproval)
        .where(InvitationApproval.invitation_id == invitation.id)
    )
    approved = bool(count is not None and count >= invitation.required_approvals)
    raw_token: str | None = None
    if approved:
        invitation.status = InvitationStatus.approved
        invitation.expires_at = utcnow() + timedelta(hours=settings.invitation_ttl_hours)
        raw_token = secrets.token_urlsafe(32)
        invitation.token_hash = cipher.hash_token(raw_token)
    record_audit(
        session,
        action="invitation.approved" if approved else "invitation.approval_recorded",
        actor_user_id=actor.id,
        org_id=invitation.org_id,
        target_type="invitation",
        target_id=invitation.id,
        detail={"role": invitation.role.value},
    )
    session.flush()
    return invitation, approved, raw_token


def revoke_invitation(
    session: Session, *, actor: User, invitation_id: uuid.UUID
) -> Invitation:
    invitation = session.get(Invitation, invitation_id)
    if invitation is None:
        raise ApiError("not_found", "Invitation not found.", 404)
    if invitation.status is InvitationStatus.accepted:
        raise ApiError("invalid_state", "Accepted invitations cannot be revoked.", 409)
    if invitation.status is InvitationStatus.revoked:
        return invitation
    allowed = actor.role is UserRole.platform_owner or (
        actor.role is UserRole.org_admin and actor.org_id == invitation.org_id
    )
    if not allowed:
        raise ApiError("forbidden", "You may not revoke this invitation.", 403)
    invitation.status = InvitationStatus.revoked
    invitation.revoked_at = utcnow()
    record_audit(
        session,
        action="invitation.revoked",
        actor_user_id=actor.id,
        org_id=invitation.org_id,
        target_type="invitation",
        target_id=invitation.id,
    )
    session.flush()
    return invitation


def _invitation_for_token(
    session: Session, *, token: str, cipher: FieldCipher, lock: bool
) -> Invitation:
    query = select(Invitation).where(Invitation.token_hash == cipher.hash_token(token))
    if lock:
        query = query.with_for_update()
    invitation = session.scalar(query)
    if invitation is None:
        raise ApiError("invalid_invitation", "Invitation is invalid or has expired.", 404)
    return invitation


def _ensure_invitation_usable(session: Session, invitation: Invitation) -> None:
    now = utcnow()
    if invitation.status is InvitationStatus.revoked:
        raise ApiError("invalid_invitation", "Invitation is invalid or has expired.", 404)
    if invitation.status is InvitationStatus.accepted:
        raise ApiError("invitation_used", "This invitation has already been used.", 409)
    if invitation.status is InvitationStatus.expired:
        raise ApiError("invalid_invitation", "Invitation is invalid or has expired.", 404)
    if invitation.status is InvitationStatus.pending_approval:
        raise ApiError("pending_approval", "Invitation is awaiting approval.", 403)
    if invitation.expires_at is None or as_utc(invitation.expires_at) <= now:
        invitation.status = InvitationStatus.expired
        session.commit()
        raise ApiError("invalid_invitation", "Invitation is invalid or has expired.", 404)


def set_user_status(
    session: Session,
    *,
    actor: User,
    user: User,
    status: UserStatus,
    reason: str | None = None,
) -> User:
    if actor.id == user.id:
        raise ApiError("self_action", "You may not change your own status.", 403)
    if user.role in PLATFORM_ROLES:
        if actor.role is not UserRole.platform_owner:
            raise ApiError("forbidden", "Only a platform owner may change this account.", 403)
    elif actor.role is UserRole.platform_owner:
        pass
    elif actor.role is UserRole.org_admin and actor.org_id == user.org_id:
        pass
    else:
        raise ApiError("forbidden", "You may not change this account.", 403)
    user.status = status
    if status is UserStatus.deactivated:
        user.deactivated_at = utcnow()
    if status is UserStatus.active:
        user.deactivated_at = None
    revoke_user_sessions(session, user_id=user.id, reason=status.value)
    record_audit(
        session,
        action="user.status_changed",
        actor_user_id=actor.id,
        org_id=user.org_id,
        target_type="user",
        target_id=user.id,
        detail={"status": status.value, "reason": reason[:64] if reason else None},
    )
    session.flush()
    return user


def list_users(
    session: Session, *, actor: User, org_id: uuid.UUID | None = None
) -> list[User]:
    query = select(User).order_by(User.created_at.desc())
    if actor.role is UserRole.platform_owner:
        if org_id is not None:
            query = query.where(User.org_id == org_id)
    elif actor.org_id is not None:
        query = query.where(User.org_id == actor.org_id)
    else:
        return []
    return list(session.scalars(query).all())


def get_user_for_actor(
    session: Session, *, actor: User, user_id: uuid.UUID
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ApiError("not_found", "User not found.", 404)
    if actor.role is UserRole.platform_owner:
        return user
    if actor.org_id is not None and user.org_id == actor.org_id:
        return user
    raise ApiError("not_found", "User not found.", 404)


def create_platform_owner(
    session: Session,
    *,
    username: str,
    password: str,
    phone: str,
    email: str | None,
    cipher: FieldCipher,
    actor_user_id: uuid.UUID | None = None,
) -> User:
    if not USERNAME_PATTERN.fullmatch(username):
        raise ApiError("invalid_username", "Choose a valid username.", 422)
    password_error = validate_password(password, username)
    if password_error:
        raise ApiError("weak_password", password_error, 422)
    normalised = normalise_phone(phone)
    phone_hash = cipher.hmac_hex(normalised)
    if session.scalar(select(User).where(User.phone_hash == phone_hash)):
        raise ApiError("account_exists", "An account already uses this phone number.", 409)
    user = User(
        org_id=None,
        username=username.strip(),
        email=email.strip().lower() if email else None,
        role=UserRole.platform_owner,
        status=UserStatus.active,
        password_hash=hash_password(password),
        password_changed_at=utcnow(),
        phone_hash=phone_hash,
        phone_encrypted=cipher.encrypt(normalised),
        phone_verified_at=utcnow(),
        confidentiality_accepted_at=utcnow(),
        orientation_completed_at=utcnow(),
    )
    session.add(user)
    session.flush()
    record_audit(
        session,
        action="user.platform_owner_created",
        actor_user_id=actor_user_id,
        org_id=None,
        target_type="user",
        target_id=user.id,
    )
    session.commit()
    return user
