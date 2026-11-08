from __future__ import annotations

import pytest

from tunza.messaging.gateways.africastalking import AfricasTalkingGateway
from tunza.messaging.gateways.base import DeliveryStatus, SendRequest
from tunza.messaging.gateways.console import ConsoleGateway


def test_console_gateway_sends_and_counts_segments() -> None:
    gateway = ConsoleGateway()
    result = gateway.send_message(SendRequest(recipient="+256700000001", body="hello"))
    assert result.provider_message_id == "console-1"
    assert result.status is DeliveryStatus.queued
    assert result.segments == 1
    assert len(gateway.sent) == 1


def test_console_gateway_counts_multipart_unicode() -> None:
    gateway = ConsoleGateway()
    result = gateway.send_message(SendRequest(recipient="+256700000001", body="你" * 71))
    assert result.segments == 2


def test_console_gateway_parses_delivery_report() -> None:
    gateway = ConsoleGateway()
    report = gateway.parse_delivery_report({"id": "abc", "status": "Delivered"})
    assert report.provider_message_id == "abc"
    assert report.status is DeliveryStatus.delivered


def test_console_gateway_parses_inbound_message() -> None:
    gateway = ConsoleGateway()
    message = gateway.parse_inbound(
        {"id": "in-1", "from": "+256700000001", "text": "STOP", "date": "2026-10-31T10:00:00Z"}
    )
    assert message.provider_message_id == "in-1"
    assert message.body == "STOP"
    assert message.received_at.tzinfo is not None


def test_africastalking_requires_credentials() -> None:
    with pytest.raises(ValueError):
        AfricasTalkingGateway(username="", api_key="key")
    with pytest.raises(ValueError):
        AfricasTalkingGateway(username="tunza", api_key="")


def test_africastalking_requires_https_base_url() -> None:
    with pytest.raises(ValueError):
        AfricasTalkingGateway(
            username="tunza",
            api_key="key",
            base_url="http://api.africastalking.com",
        )
