"""Africa's Talking gateway adapter.

Callback parsing will be re-checked against current provider documentation in M6.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, ClassVar, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tunza.messaging.gateways.base import (
    DeliveryReport,
    DeliveryStatus,
    InboundMessage,
    SendRequest,
    SendResult,
    SmsGateway,
    SmsGatewayError,
)
from tunza.messaging.segments import count_segments

SANDBOX_BASE_URL = "https://api.sandbox.africastalking.com"
PRODUCTION_BASE_URL = "https://api.africastalking.com"


def _map_status(value: Any) -> DeliveryStatus:
    lowered = str(value).strip().lower()
    if lowered in {"delivered", "success", "successful"}:
        return DeliveryStatus.delivered
    if lowered in {"sent", "submitted"}:
        return DeliveryStatus.sent
    if lowered in {"queued", "pending", "buffered"}:
        return DeliveryStatus.queued
    if lowered in {"rejected", "invalid"}:
        return DeliveryStatus.rejected
    if lowered in {"failed", "failure", "undeliverable"}:
        return DeliveryStatus.failed
    return DeliveryStatus.unknown


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


class AfricasTalkingGateway(SmsGateway):
    """Africa's Talking implementation of the SmsGateway contract."""

    name: ClassVar[str] = "africastalking"

    def __init__(
        self,
        *,
        username: str,
        api_key: str,
        sender_id: str | None = None,
        sandbox: bool = True,
        base_url: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not username.strip() or not api_key.strip():
            raise ValueError("Africa's Talking username and API key are required")
        resolved_base = (base_url or (SANDBOX_BASE_URL if sandbox else PRODUCTION_BASE_URL)).rstrip(
            "/"
        )
        if not resolved_base.startswith("https://"):
            raise ValueError("Africa's Talking base URL must use HTTPS")
        self.username = username
        self._api_key = api_key
        self.sender_id = sender_id
        self.base_url = resolved_base
        self.timeout_seconds = timeout_seconds

    def send_message(self, request: SendRequest) -> SendResult:
        form: dict[str, str] = {
            "username": self.username,
            "to": request.recipient,
            "message": request.body,
        }
        sender = request.sender_id or self.sender_id
        if sender:
            form["from"] = sender

        payload = self._post("/version1/messaging", urlencode(form))
        message_data = payload.get("SMSMessageData")
        if not isinstance(message_data, Mapping):
            raise SmsGatewayError("Malformed Africa's Talking response")
        recipients = message_data.get("Recipients")
        if not isinstance(recipients, list) or not recipients:
            raise SmsGatewayError("Africa's Talking returned no recipient status")
        first = recipients[0]
        if not isinstance(first, Mapping):
            raise SmsGatewayError("Malformed Africa's Talking recipient")
        provider_message_id = str(first.get("messageId") or first.get("id") or "")
        if not provider_message_id:
            raise SmsGatewayError("Africa's Talking returned no message id")
        raw_status = str(first.get("status", ""))
        return SendResult(
            provider_message_id=provider_message_id,
            status=_map_status(raw_status),
            segments=count_segments(request.body).segments,
            raw_status=raw_status,
        )

    def parse_delivery_report(self, payload: Mapping[str, Any]) -> DeliveryReport:
        return DeliveryReport(
            provider_message_id=str(payload.get("id", "")),
            status=_map_status(payload.get("status", "unknown")),
            occurred_at=_parse_datetime(payload.get("date")),
            raw={"failure_reason": payload.get("failureReason")}
            if payload.get("failureReason")
            else {},
        )

    def parse_inbound(self, payload: Mapping[str, Any]) -> InboundMessage:
        return InboundMessage(
            provider_message_id=_optional_str(payload.get("id")),
            sender=str(payload.get("from", "")),
            body=str(payload.get("text", "")),
            received_at=_parse_datetime(payload.get("date")) or datetime.now(UTC),
            raw={"link_id": payload.get("linkId")}
            if payload.get("linkId")
            else {},
        )

    def _post(self, path: str, body: str) -> dict[str, Any]:
        request = Request(  # noqa: S310
            f"{self.base_url}{path}",
            data=body.encode("utf-8"),
            headers={
                "apiKey": self._api_key,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310  # nosec B310
                decoded = json.loads(response.read().decode("utf-8"))
        except OSError as exc:
            raise SmsGatewayError("Africa's Talking request failed") from exc
        if not isinstance(decoded, dict):
            raise SmsGatewayError("Africa's Talking returned a non-object response")
        return cast(dict[str, Any], decoded)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
