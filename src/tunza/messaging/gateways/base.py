"""Provider-agnostic SMS gateway contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar


class DeliveryStatus(StrEnum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    rejected = "rejected"
    unknown = "unknown"


class SmsGatewayError(RuntimeError):
    """Raised when a provider rejects or cannot process a message."""


@dataclass(frozen=True, slots=True)
class SendRequest:
    recipient: str
    body: str
    sender_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class SendResult:
    provider_message_id: str
    status: DeliveryStatus
    segments: int
    raw_status: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    provider_message_id: str
    status: DeliveryStatus
    occurred_at: datetime | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InboundMessage:
    provider_message_id: str | None
    sender: str
    body: str
    received_at: datetime
    raw: Mapping[str, Any] = field(default_factory=dict)


class SmsGateway(ABC):
    """Contract every SMS provider adapter must satisfy."""

    name: ClassVar[str]

    @abstractmethod
    def send_message(self, request: SendRequest) -> SendResult:
        """Send one message and return the provider acknowledgement."""

    @abstractmethod
    def parse_delivery_report(self, payload: Mapping[str, Any]) -> DeliveryReport:
        """Normalise a provider delivery callback."""

    @abstractmethod
    def parse_inbound(self, payload: Mapping[str, Any]) -> InboundMessage:
        """Normalise a provider inbound-message callback."""
