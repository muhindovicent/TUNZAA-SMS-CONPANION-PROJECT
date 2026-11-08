from __future__ import annotations

from tunza.logging import redact_sensitive


def test_redact_sensitive_replaces_personal_and_secret_values() -> None:
    event = {
        "event": "patient.registered",
        "phone": "+256700000001",
        "phone_number": "+256700000001",
        "name": "Test Woman",
        "body": "Your next visit is due",
        "password": "not-a-real-password",
        "token": "not-a-real-token",
        "otp_code": "123456",
        "message_id": "abc-123",
        "org_id": "00000000-0000-0000-0000-000000000001",
    }
    redacted = redact_sensitive(None, "info", dict(event))
    assert redacted["event"] == "patient.registered"
    assert redacted["message_id"] == "abc-123"
    assert redacted["org_id"] == "00000000-0000-0000-0000-000000000001"
    assert redacted["phone"] == "[redacted]"
    assert redacted["phone_number"] == "[redacted]"
    assert redacted["name"] == "[redacted]"
    assert redacted["body"] == "[redacted]"
    assert redacted["password"] == "[redacted]"
    assert redacted["token"] == "[redacted]"
    assert redacted["otp_code"] == "[redacted]"


def test_redact_sensitive_does_not_mutate_the_caller_dictionary() -> None:
    event = {"phone": "+256700000001"}
    redacted = redact_sensitive(None, "info", dict(event))
    assert event["phone"] == "+256700000001"
    assert redacted["phone"] == "[redacted]"
