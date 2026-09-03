"""Explicit runtime composition. Mock is the default; no provider provisioning."""
import asyncio
import logging
from src.core.config import settings
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from .mock_provider import MockWhatsAppProvider
from .meta_provider import MetaCloudWhatsAppProvider
from .webhook_service import WhatsAppWebhookService


def configured_service():
    if not settings.WHATSAPP_ADAPTER_TOKEN or not settings.WHATSAPP_TENANT_TOKENS:
        return None
    if settings.WHATSAPP_PROVIDER == "mock":
        provider = MockWhatsAppProvider()
    elif settings.WHATSAPP_PROVIDER == "meta":
        api_token = settings.WHATSAPP_API_TOKEN or settings.META_ACCESS_TOKEN
        phone_id = settings.WHATSAPP_PHONE_NUMBER_ID or settings.META_PHONE_NUMBER_ID
        graph_version = settings.WHATSAPP_GRAPH_VERSION or settings.META_GRAPH_API_VERSION or "v26.0"
        if not api_token or not phone_id:
            raise ValueError("Meta provider credentials are not configured")
        provider = MetaCloudWhatsAppProvider(api_token, phone_id, graph_version)
    else:
        raise ValueError("Unsupported WhatsApp provider")
    transport = HttpxHermesTransport(settings.WHATSAPP_SAAS_URL)
    gateway = HermesApiClient(transport, lambda: settings.WHATSAPP_ADAPTER_TOKEN.get_secret_value(), settings.WHATSAPP_SAAS_URL)
    def tenant_client(org):
        token = settings.WHATSAPP_TENANT_TOKENS.get(org)
        if not token:
            raise ValueError("Sender tenant has no machine credential")
        return HermesApiClient(transport, token.get_secret_value, settings.WHATSAPP_SAAS_URL)
    return WhatsAppWebhookService(provider, gateway, tenant_client, list(settings.WHATSAPP_TENANT_TOKENS), settings.WHATSAPP_ORG_MESSAGES_PER_MINUTE)


async def notification_loop(app):
    """Poll authoritative processing outcomes without touching database or storage."""
    while True:
        service = getattr(app.state, "whatsapp_service", None)
        if service is None:
            service = configured_service()
            if service:
                app.state.whatsapp_service = service
        if service:
            try:
                await service.deliver_pending_notifications()
            except Exception:
                # No exception strings: transports may carry sensitive URL/token data.
                logging.getLogger(__name__).warning("WhatsApp notification poll failed")
        await asyncio.sleep(10)
