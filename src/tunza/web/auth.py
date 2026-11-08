"""Tenancy, identity and authentication JSON API."""

from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import select

from tunza.config import Settings
from tunza.db.engine import Database
from tunza.db.models import Organisation
from tunza.messaging.gateways.base import SendRequest, SmsGateway, SmsGatewayError
from tunza.modules.audit.models import AuditLog
from tunza.modules.audit.service import record_audit
from tunza.modules.identity import service as identity
from tunza.modules.identity.models import (
    Invitation,
    InvitationApproval,
    MfaFactor,
    OtpPurpose,
    SessionStage,
    User,
    UserRole,
    UserStatus,
)
from tunza.modules.identity.oidc import OidcError, complete_authorization, start_authorization
from tunza.modules.tenancy import service as tenancy
from tunza.modules.tenancy.models import TenantSettings
from tunza.security.csrf import CSRF_COOKIE, new_csrf_token, set_csrf_cookie
from tunza.security.fields import FieldCipher
from tunza.web.auth_context import (
    SESSION_COOKIE,
    apply_session_cookies,
    clear_session_cookies,
    current_session,
    current_user,
    get_cipher,
    get_database,
    get_settings,
    request_meta,
    require_active,
    require_roles,
    require_stage,
)
from tunza.web.errors import ApiError

bp = Blueprint("identity_api", __name__, url_prefix="/api/v1")


def _body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("invalid_json", "A JSON object is required.", 400)
    return payload


def _string(payload: dict[str, Any], name: str, *, required: bool = True) -> str | None:
    value = payload.get(name)
    if value is None:
        if required:
            raise ApiError("missing_field", f"{name} is required.", 422)
        return None
    if not isinstance(value, str):
        raise ApiError("invalid_field", f"{name} must be a string.", 422)
    return value


def _user_dict(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "org_id": str(user.org_id) if user.org_id else None,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "status": user.status.value,
        "mfa_required": user.mfa_required,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _session_dict(user: User, bundle: identity.SessionBundle) -> dict[str, Any]:
    return {
        "stage": bundle.auth_session.stage.value,
        "user": _user_dict(user),
    }


def _invitation_dict(
    session: Any, invitation: Invitation, *, include_approvals: bool = True
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": str(invitation.id),
        "org_id": str(invitation.org_id) if invitation.org_id else None,
        "role": invitation.role.value,
        "status": invitation.status.value,
        "required_approvals": invitation.required_approvals,
        "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
        "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
    }
    if include_approvals:
        result["approvals"] = session.scalar(
            select(InvitationApproval).where(
                InvitationApproval.invitation_id == invitation.id
            )
        ) is not None
    return result


def _sms_gateway() -> SmsGateway:
    return request.app.extensions["tunza.sms"]


def _send_sms(recipient: str, body: str) -> None:
    try:
        _sms_gateway().send_message(SendRequest(recipient=recipient, body=body))
    except SmsGatewayError as exc:
        raise ApiError("sms_failed", "Could not send the SMS. Try again.", 502) from exc


def _send_invitation_sms(invitation: Invitation, token: str, cipher: FieldCipher) -> None:
    settings = get_settings()
    recipient = cipher.decrypt(invitation.phone_encrypted)
    link = f"{settings.public_base_url.rstrip('/')}/invite#{token}"
    organisation = invitation.org_id and invitation.org_id
    org_name = "Tunza"
    if organisation:
        database = get_database()
        with database.session_factory() as session:
            org = session.get(Organisation, organisation)
            if org is not None:
                org_name = org.name
    _send_sms(
        recipient,
        f"{org_name} invited you to Tunza. Open {link} to finish setting up your account.",
    )


@bp.get("/auth/csrf")
def csrf_token() -> Response:
    settings = get_settings()
    token = new_csrf_token(settings)
    auth_session = current_session()
    if auth_session is not None:
        cipher = get_cipher()
        database = get_database()
        with database.session_factory() as session:
            row = session.get(type(auth_session), auth_session.id)
            if row is not None:
                row.csrf_token_hash = cipher.hash_token(token)
                session.commit()
    response = jsonify({"csrf_token": token})
    response.headers["Cache-Control"] = "no-store"
    set_csrf_cookie(response, token, settings)
    return response


@bp.post("/auth/login")
def login() -> Response:
    payload = _body()
    username = _string(payload, "username") or ""
    password = _string(payload, "password") or ""
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        if current_session() is not None:
            existing = session.get(type(current_session()), current_session().id)
            if existing is not None:
                identity.revoke_session(session, existing, reason="new_login")
                session.commit()
        result = identity.login(
            session,
            settings=settings,
            cipher=cipher,
            username=username,
            password=password,
            meta=request_meta(),
        )
        response = jsonify(_session_dict(result.user, result.bundle))
    response.headers["Cache-Control"] = "no-store"
    return apply_session_cookies(
        response,
        token=result.bundle.token,
        csrf_token=result.bundle.csrf_token,
        settings=settings,
    )


@bp.post("/auth/logout")
def logout() -> Response:
    database = get_database()
    auth_session = current_session()
    if auth_session is not None:
        with database.session_factory() as session:
            row = session.get(type(auth_session), auth_session.id)
            if row is not None:
                identity.revoke_session(session, row, reason="logout")
                record_audit(
                    session,
                    action="auth.logout",
                    actor_user_id=row.user_id,
                    org_id=row.org_id,
                    target_type="session",
                    target_id=row.id,
                )
                session.commit()
    response = Response(status=204)
    return clear_session_cookies(response)


@bp.get("/auth/me")
def me() -> Response:
    user = current_user()
    auth_session = current_session()
    if user is None or auth_session is None:
        raise ApiError("authentication_required", "Sign in is required.", 401)
    response = jsonify(
        {
            "stage": auth_session.stage.value,
            "user": _user_dict(user),
            "mfa_required": user.mfa_required,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/auth/phone/send-otp")
@require_stage(SessionStage.phone_verification)
def send_phone_otp() -> Response:
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        user = _reload_user(session)
        code, _challenge = identity.issue_otp(
            session,
            user=user,
            purpose=OtpPurpose.phone_verification,
            settings=settings,
            cipher=cipher,
            meta=request_meta(),
        )
        _send_sms(
            identity.decrypt_phone(user, cipher),
            f"Your Tunza verification code is {code}. It expires in "
            f"{settings.otp_ttl_seconds // 60} minutes.",
        )
        session.commit()
    return jsonify({"sent": True})


@bp.post("/auth/phone/verify")
@require_stage(SessionStage.phone_verification)
def verify_phone() -> Response:
    payload = _body()
    code = _string(payload, "code") or ""
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        user = _reload_user(session)
        identity.verify_otp(
            session,
            user=user,
            purpose=OtpPurpose.phone_verification,
            code=code,
            cipher=cipher,
            meta=request_meta(),
        )
        user.phone_verified_at = identity.utcnow()
        user.status = (
            UserStatus.active
            if user.confidentiality_accepted_at and user.orientation_completed_at
            else UserStatus.pending_orientation
        )
        stage = identity.post_phone_stage(session, user)
        bundle = identity.rotate_session(
            session,
            auth_session=_reload_session(session),
            user=user,
            stage=stage,
            settings=settings,
            cipher=cipher,
            meta=request_meta(),
        )
        record_audit(
            session,
            action="auth.phone_verified",
            actor_user_id=user.id,
            org_id=user.org_id,
            target_type="user",
            target_id=user.id,
        )
        session.commit()
        response = jsonify(_session_dict(user, bundle))
    return apply_session_cookies(
        response, token=bundle.token, csrf_token=bundle.csrf_token, settings=settings
    )


@bp.post("/auth/mfa/sms/send")
@require_stage(SessionStage.mfa_required, SessionStage.factor_setup)
def send_sms_mfa() -> Response:
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        user = _reload_user(session)
        if current_session().stage is SessionStage.factor_setup:
            identity.create_sms_factor(session, user=user)
        code, _challenge = identity.issue_otp(
            session,
            user=user,
            purpose=OtpPurpose.login_mfa,
            settings=settings,
            cipher=cipher,
            meta=request_meta(),
        )
        _send_sms(
            identity.decrypt_phone(user, cipher),
            f"Your Tunza sign-in code is {code}. It expires in "
            f"{settings.otp_ttl_seconds // 60} minutes.",
        )
        session.commit()
    return jsonify({"sent": True})


@bp.post("/auth/mfa/sms/verify")
@require_stage(SessionStage.mfa_required, SessionStage.factor_setup)
def verify_sms_mfa() -> Response:
    payload = _body()
    code = _string(payload, "code") or ""
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        user = _reload_user(session)
        identity.verify_otp(
            session,
            user=user,
            purpose=OtpPurpose.login_mfa,
            code=code,
            cipher=cipher,
            meta=request_meta(),
        )
        identity.create_sms_factor(session, user=user)
        bundle = identity.rotate_session(
            session,
            auth_session=_reload_session(session),
            user=user,
            stage=identity.post_mfa_stage(user),
            settings=settings,
            cipher=cipher,
            meta=request_meta(),
        )
        record_audit(
            session,
            action="auth.mfa_sms_verified",
            actor_user_id=user.id,
            org_id=user.org_id,
            target_type="user",
            target_id=user.id,
        )
        session.commit()
        response = jsonify(_session_dict(user, bundle))
    return apply_session_cookies(
        response, token=bundle.token, csrf_token=bundle.csrf_token, settings=settings
    )


@bp.post("/auth/mfa/totp/start")
@require_stage(SessionStage.factor_setup, SessionStage.active)
def start_totp() -> Response:
    database = get_database()
    with database.session_factory() as session:
        user = _reload_user(session)
        _factor, uri = identity.start_totp_factor(session, user=user, cipher=get_cipher())
        record_audit(
            session,
            action="auth.totp_setup_started",
            actor_user_id=user.id,
            org_id=user.org_id,
            target_type="user",
            target_id=user.id,
        )
        session.commit()
    response = jsonify({"otpauth_uri": uri})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/auth/mfa/totp/confirm")
@require_stage(SessionStage.factor_setup, SessionStage.mfa_required, SessionStage.active)
def confirm_totp() -> Response:
    payload = _body()
    code = _string(payload, "code") or ""
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        user = _reload_user(session)
        stage = current_session().stage
        if stage is SessionStage.mfa_required:
            identity.verify_totp_factor(session, user=user, code=code, cipher=cipher)
        else:
            identity.confirm_totp_factor(session, user=user, code=code, cipher=cipher)
        bundle = identity.rotate_session(
            session,
            auth_session=_reload_session(session),
            user=user,
            stage=identity.post_mfa_stage(user)
            if stage is not SessionStage.active
            else SessionStage.active,
            settings=settings,
            cipher=cipher,
            meta=request_meta(),
        )
        record_audit(
            session,
            action="auth.totp_confirmed",
            actor_user_id=user.id,
            org_id=user.org_id,
            target_type="user",
            target_id=user.id,
        )
        session.commit()
        response = jsonify(_session_dict(user, bundle))
    return apply_session_cookies(
        response, token=bundle.token, csrf_token=bundle.csrf_token, settings=settings
    )


@bp.post("/auth/orientation")
@require_stage(SessionStage.orientation)
def accept_orientation() -> Response:
    payload = _body()
    accepted = payload.get("accepted")
    if not isinstance(accepted, bool):
        raise ApiError("invalid_field", "accepted must be true or false.", 422)
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        user = _reload_user(session)
        bundle = identity.complete_orientation(
            session,
            user=user,
            auth_session=_reload_session(session),
            settings=settings,
            cipher=cipher,
            meta=request_meta(),
            accepted=accepted,
        )
        response = jsonify(_session_dict(user, bundle))
    return apply_session_cookies(
        response, token=bundle.token, csrf_token=bundle.csrf_token, settings=settings
    )


@bp.post("/invitations/inspect")
def inspect_invitation() -> Response:
    payload = _body()
    token = _string(payload, "token") or ""
    database = get_database()
    with database.session_factory() as session:
        info = identity.inspect_invitation(
            session, token=token, cipher=get_cipher()
        )
    return jsonify({"invitation": info})


@bp.post("/invitations/accept")
def accept_invitation() -> Response:
    payload = _body()
    token = _string(payload, "token") or ""
    username = _string(payload, "username") or ""
    password = _string(payload, "password") or ""
    email = _string(payload, "email", required=False)
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        result = identity.accept_invitation(
            session,
            token=token,
            username=username,
            password=password,
            email=email,
            settings=settings,
            cipher=cipher,
            meta=request_meta(),
        )
        response = jsonify(_session_dict(result.user, result.bundle))
        response.status_code = 201
    return apply_session_cookies(
        response,
        token=result.bundle.token,
        csrf_token=result.bundle.csrf_token,
        settings=settings,
    )


@bp.post("/invitations")
@require_active
@require_roles("platform_owner", "org_admin")
def create_invitation() -> Response:
    payload = _body()
    try:
        role = UserRole(_string(payload, "role") or "")
    except ValueError:
        raise ApiError("invalid_role", "Unknown role.", 422) from None
    phone = _string(payload, "phone") or ""
    org_value = payload.get("org_id")
    if org_value is not None and not isinstance(org_value, str):
        raise ApiError("invalid_org", "org_id must be a string.", 422)
    org_id = _uuid_or_none(org_value)
    evidence = _string(payload, "evidence", required=False)
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        invitation, token = identity.create_invitation(
            session,
            actor=actor,
            role=role,
            phone=phone,
            org_id=org_id,
            evidence=evidence,
            settings=settings,
            cipher=cipher,
        )
        response_body = _invitation_dict(session, invitation)
        session.commit()
        if invitation.status.value == "approved":
            _send_invitation_sms(invitation, token, cipher)
    response = jsonify({"invitation": response_body})
    response.status_code = 201
    return response


@bp.get("/invitations")
@require_active
@require_roles("platform_owner", "org_admin")
def list_invitations() -> Response:
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        query = select(Invitation).order_by(Invitation.created_at.desc())
        if actor.role is UserRole.org_admin:
            query = query.where(Invitation.org_id == actor.org_id)
        else:
            org_id = request.args.get("org_id")
            if org_id:
                query = query.where(Invitation.org_id == _uuid_or_none(org_id))
        rows = list(session.scalars(query).all())
        return jsonify(
            {"invitations": [_invitation_dict(session, row) for row in rows]}
        )


@bp.post("/invitations/<uuid:invitation_id>/approve")
@require_active
@require_roles("platform_owner", "org_admin")
def approve_invitation(invitation_id: uuid.UUID) -> Response:
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        invitation, approved, token = identity.approve_invitation(
            session,
            actor=actor,
            invitation_id=invitation_id,
            settings=settings,
            cipher=cipher,
        )
        body = _invitation_dict(session, invitation)
        body["approved"] = approved
        session.commit()
        if approved and token is not None:
            _send_invitation_sms(invitation, token, cipher)
    return jsonify({"invitation": body})


@bp.post("/invitations/<uuid:invitation_id>/revoke")
@require_active
@require_roles("platform_owner", "org_admin")
def revoke_invitation(invitation_id: uuid.UUID) -> Response:
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        invitation = identity.revoke_invitation(
            session, actor=actor, invitation_id=invitation_id
        )
        body = _invitation_dict(session, invitation)
        session.commit()
    return jsonify({"invitation": body})


@bp.post("/invitations/<uuid:invitation_id>/resend")
@require_active
@require_roles("platform_owner", "org_admin")
def resend_invitation(invitation_id: uuid.UUID) -> Response:
    settings = get_settings()
    cipher = get_cipher()
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        invitation = session.get(Invitation, invitation_id)
        if invitation is None:
            raise ApiError("not_found", "Invitation not found.", 404)
        if invitation.status.value != "approved":
            raise ApiError("invalid_state", "Only approved invitations can be resent.", 409)
        allowed = actor.role is UserRole.platform_owner or (
            actor.role is UserRole.org_admin and actor.org_id == invitation.org_id
        )
        if not allowed:
            raise ApiError("forbidden", "You may not resend this invitation.", 403)
        import secrets

        token = secrets.token_urlsafe(32)
        invitation.token_hash = cipher.hash_token(token)
        invitation.expires_at = identity.utcnow() + __import__("datetime").timedelta(
            hours=settings.invitation_ttl_hours
        )
        record_audit(
            session,
            action="invitation.resent",
            actor_user_id=actor.id,
            org_id=invitation.org_id,
            target_type="invitation",
            target_id=invitation.id,
        )
        session.commit()
        _send_invitation_sms(invitation, token, cipher)
    return jsonify({"sent": True})


@bp.get("/users")
@require_active
@require_roles("platform_owner", "org_admin")
def list_users() -> Response:
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        org_id = _uuid_or_none(request.args.get("org_id"))
        users = identity.list_users(session, actor=actor, org_id=org_id)
        return jsonify({"users": [_user_dict(user) for user in users]})


@bp.get("/users/<uuid:user_id>")
@require_active
@require_roles("platform_owner", "org_admin")
def get_user(user_id: uuid.UUID) -> Response:
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        user = identity.get_user_for_actor(session, actor=actor, user_id=user_id)
        return jsonify({"user": _user_dict(user)})


@bp.post("/users/<uuid:user_id>/status")
@require_active
@require_roles("platform_owner", "org_admin")
def change_user_status(user_id: uuid.UUID) -> Response:
    payload = _body()
    try:
        status = UserStatus(_string(payload, "status") or "")
    except ValueError:
        raise ApiError("invalid_status", "Unknown status.", 422) from None
    if status not in {UserStatus.active, UserStatus.suspended, UserStatus.deactivated}:
        raise ApiError("invalid_status", "That status cannot be set here.", 422)
    reason = _string(payload, "reason", required=False)
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        target = identity.get_user_for_actor(session, actor=actor, user_id=user_id)
        identity.set_user_status(
            session, actor=actor, user=target, status=status, reason=reason
        )
        body = _user_dict(target)
        session.commit()
    return jsonify({"user": body})


@bp.get("/organisations")
@require_active
@require_roles("platform_owner", "org_admin")
def list_organisations() -> Response:
    database = get_database()
    with database.session_factory() as session:
        actor = _reload_user(session)
        if actor.role is UserRole.platform_owner:
            rows = session.scalars(select(Organisation).order_by(Organisation.name)).all()
        else:
            rows = (
                [session.get(Organisation, actor.org_id)] if actor.org_id else []
            )
        return jsonify(
            {"organisations": [_organisation_dict(row) for row in rows if row is not None]}
        )


@bp.post("/organisations")
@require_active
@require_roles("platform_owner")
def create_organisation() -> Response:
    payload = _body()
    try:
        organisation = tenancy.create_organisation(
            __import__("tunza.web.auth_context", fromlist=["get_database"])
            .get_database()
            .session_factory()
            .__enter__(),
            name=_string(payload, "name") or "",
            signatory_name=_string(payload, "signatory_name") or "",
            signatory_email=_string(payload, "signatory_email") or "",
            slug=_string(payload, "slug", required=False),
            actor_user_id=current_user().id,
            languages=payload.get("languages")
            if isinstance(payload.get("languages"), list)
            else None,
        )
    except Exception:
        raise
    finally:
        pass
    return jsonify({"organisation": _organisation_dict(organisation)})


def _organisation_dict(organisation: Organisation) -> dict[str, Any]:
    return {
        "id": str(organisation.id),
        "slug": organisation.slug,
        "name": organisation.name,
        "status": organisation.status.value,
        "signatory_name": organisation.signatory_name,
        "signatory_email": organisation.signatory_email,
        "offboarded_at": organisation.offboarded_at.isoformat()
        if organisation.offboarded_at
        else None,
    }


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ApiError("invalid_id", "Invalid identifier.", 422) from None


def _reload_user(session: Any) -> User:
    user = current_user()
    if user is None:
        raise ApiError("authentication_required", "Sign in is required.", 401)
    row = session.get(User, user.id)
    if row is None:
        raise ApiError("authenticated_user_missing", "Account is not available.", 401)
    return row


def _reload_session(session: Any) -> Any:
    auth_session = current_session()
    if auth_session is None:
        raise ApiError("authentication_required", "Sign in is required.", 401)
    row = session.get(type(auth_session), auth_session.id)
    if row is None:
        raise ApiError("session_missing", "Session is no longer valid.", 401)
    return row
