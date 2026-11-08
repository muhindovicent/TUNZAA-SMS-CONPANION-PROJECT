"""Development gateway that never sends real SMS."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, ClassVar

from tunza.messaging.gateways.base import (
    DeliveryReport,
    DeliveryStatus,
    InboundMessage,
    SendRequest,
    SendResult,
    SmsGateway,
)
from tunza.messaging.segments import count_segments


def _coerce_status(value: Any) -> DeliveryStatus:
    try:
        return DeliveryStatus(str(value).lower())
    except ValueError:
        return DeliveryStatus.unknown


class ConsoleGateway(SmsGateway):
    """In-memory gateway for development and tests."""

    name: ClassVar[str] = "console"

    def __init__(self) -> None:
        self.sent: list[SendResult] = []
        self._counter = 0

    def send_message(self, request: SendRequest) -> SendResult:
        self._counter += 1
        result = SendResult(
            provider_message_id=f"console-{self._counter}",
            status=DeliveryStatus.queued,
            segments=count_segments(request.body).segments,
        )
        self.sent.append(result)
        return result

    def parse_delivery_report(self, payload: Mapping[str, Any]) -> DeliveryReport:
        return DeliveryReport(
            provider_message_id=str(payload.get("id", "")),
            status=_coerce_status(payload.get("status", "unknown")),
            occurred_at=_parse_datetime(payload.get("date")),
        )

    def parse_inbound(self, payload: Mapping[str, Any]) -> InboundMessage:
        return InboundMessage(
            provider_message_id=_optional_str(payload.get("id")),
            sender=str(payload.get("from", "")),
            body=str(payload.get("text", "")),
            received_at=_parse_datetime(payload.get("date")) or datetime.now(UTC),
        )


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


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
