"""OIDC discovery, authorization and ID-token validation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from authlib.integrations.requests_client import OAuth2Session
from joserfc import jwt
from joserfc.jwk import KeySet

from tunza.config import AppEnv, Settings

ALLOWED_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
MAX_CLOCK_SKEW_SECONDS = 60
METADATA_TTL_SECONDS = 3600


class OidcError(RuntimeError):
    """Raised when discovery, exchange or ID-token validation fails."""


@dataclass(frozen=True)
class OidcIdentity:
    issuer: str
    subject: str
    email: str | None


@dataclass(frozen=True)
class OidcAuthorization:
    url: str
    state: str
    nonce: str
    code_verifier: str


@dataclass(frozen=True)
class _Metadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    fetched_at: float


_metadata_cache: dict[str, _Metadata] = {}


def clear_metadata_cache() -> None:
    _metadata_cache.clear()


def _validate_issuer(issuer: str, settings: Settings) -> str:
    parsed = urlparse(issuer)
    if parsed.username or parsed.password:
        raise OidcError("Issuer must not contain credentials")
    if parsed.scheme != "https" and not (
        settings.app_env in {AppEnv.development, AppEnv.test}
        and parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise OidcError("Issuer must use HTTPS")
    if not parsed.hostname:
        raise OidcError("Issuer hostname is missing")
    return issuer.rstrip("/")


def discover(issuer: str, settings: Settings) -> _Metadata:
    resolved = _validate_issuer(issuer, settings)
    cached = _metadata_cache.get(resolved)
    now = time.monotonic()
    if cached is not None and now - cached.fetched_at < METADATA_TTL_SECONDS:
        return cached
    url = f"{resolved}/.well-known/openid-configuration"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise OidcError("OIDC discovery failed") from exc
    if not isinstance(payload, dict):
        raise OidcError("OIDC discovery response is invalid")
    metadata_issuer = str(payload.get("issuer", "")).rstrip("/")
    if metadata_issuer != resolved:
        raise OidcError("OIDC issuer mismatch")
    authorization_endpoint = str(payload.get("authorization_endpoint", ""))
    token_endpoint = str(payload.get("token_endpoint", ""))
    jwks_uri = str(payload.get("jwks_uri", ""))
    for endpoint in (authorization_endpoint, token_endpoint, jwks_uri):
        endpoint_parsed = urlparse(endpoint)
        if endpoint_parsed.scheme != "https" and not (
            settings.app_env in {AppEnv.development, AppEnv.test}
            and endpoint_parsed.scheme == "http"
            and endpoint_parsed.hostname in {"localhost", "127.0.0.1"}
        ):
            raise OidcError("OIDC endpoint must use HTTPS")
    metadata = _Metadata(
        issuer=metadata_issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        jwks_uri=jwks_uri,
        fetched_at=now,
    )
    _metadata_cache[resolved] = metadata
    return metadata


def start_authorization(
    *,
    issuer: str,
    client_id: str,
    client_secret: str,
    scopes: str,
    redirect_uri: str,
    settings: Settings,
) -> OidcAuthorization:
    metadata = discover(issuer, settings)
    state = _random_token()
    nonce = _random_token()
    verifier = _random_token(48)
    client = OAuth2Session(
        client_id,
        client_secret,
        scope=scopes,
        redirect_uri=redirect_uri,
    )
    url, _ = client.create_authorization_url(
        metadata.authorization_endpoint,
        state=state,
        nonce=nonce,
        code_verifier=verifier,
    )
    return OidcAuthorization(
        url=url, state=state, nonce=nonce, code_verifier=verifier
    )


def complete_authorization(
    *,
    issuer: str,
    client_id: str,
    client_secret: str,
    code: str,
    code_verifier: str,
    expected_nonce: str,
    settings: Settings,
) -> OidcIdentity:
    metadata = discover(issuer, settings)
    client = OAuth2Session(client_id, client_secret)
    try:
        token = client.fetch_token(
            metadata.token_endpoint,
            code=code,
            code_verifier=code_verifier,
            grant_type="authorization_code",
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001 - authlib raises several request types
        raise OidcError("OIDC token exchange failed") from exc
    id_token = token.get("id_token") if isinstance(token, dict) else None
    if not isinstance(id_token, str) or not id_token:
        raise OidcError("OIDC response did not include an ID token")
    claims = _verify_id_token(
        id_token=id_token,
        metadata=metadata,
        client_id=client_id,
        expected_nonce=expected_nonce,
    )
    email_value = claims.get("email")
    email = str(email_value).strip().lower() if email_value else None
    if email is not None and claims.get("email_verified") is False:
        email = None
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise OidcError("OIDC subject is missing")
    return OidcIdentity(issuer=metadata.issuer, subject=subject, email=email)


def _verify_id_token(
    *,
    id_token: str,
    metadata: _Metadata,
    client_id: str,
    expected_nonce: str,
) -> dict[str, Any]:
    try:
        with urlopen(  # noqa: S310
            Request(metadata.jwks_uri, headers={"Accept": "application/json"}),
            timeout=10,
        ) as response:
            jwks = json.loads(response.read().decode("utf-8"))
        key_set = KeySet.import_key_set(jwks)
        token = jwt.decode(id_token, key_set, algorithms=ALLOWED_ALGORITHMS)
    except Exception as exc:  # noqa: BLE001 - joserfc raises several validation types
        raise OidcError("OIDC ID token verification failed") from exc
    claims = dict(token.claims)
    now = int(time.time())
    issuer = str(claims.get("iss", "")).rstrip("/")
    if issuer != metadata.issuer:
        raise OidcError("OIDC ID-token issuer mismatch")
    audience = claims.get("aud")
    audiences = [audience] if isinstance(audience, str) else audience
    if not isinstance(audiences, list) or client_id not in audiences:
        raise OidcError("OIDC ID-token audience mismatch")
    if len(audiences) > 1 and claims.get("azp") != client_id:
        raise OidcError("OIDC ID-token authorized party mismatch")
    expires = claims.get("exp")
    if not isinstance(expires, int) or expires < now - MAX_CLOCK_SKEW_SECONDS:
        raise OidcError("OIDC ID token has expired")
    issued = claims.get("iat")
    if not isinstance(issued, int) or issued > now + MAX_CLOCK_SKEW_SECONDS:
        raise OidcError("OIDC ID token is not yet valid")
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or nonce != expected_nonce:
        raise OidcError("OIDC nonce mismatch")
    return claims


def _random_token(length: int = 32) -> str:
    import secrets

    return secrets.token_urlsafe(length)
