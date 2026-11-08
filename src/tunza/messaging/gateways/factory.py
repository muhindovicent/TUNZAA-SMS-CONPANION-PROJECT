"""Build the configured SMS gateway."""

from __future__ import annotations

from tunza.config import SmsProviderName, Settings
from tunza.messaging.gateways.africastalking import AfricasTalkingGateway
from tunza.messaging.gateways.base import SmsGateway
from tunza.messaging.gateways.console import ConsoleGateway


def build_gateway(settings: Settings) -> SmsGateway:
    if settings.sms_provider is SmsProviderName.africastalking:
        if settings.africastalking_api_key is None:
            raise RuntimeError("AFRICASTALKING_API_KEY is required")
        return AfricasTalkingGateway(
            username=settings.africastalking_username or "",
            api_key=settings.africastalking_api_key.get_secret_value(),
            sender_id=settings.africastalking_sender_id,
            sandbox=settings.africastalking_sandbox,
            base_url=settings.africastalking_base_url,
        )
    return ConsoleGateway()
