"""Explicit runtime composition. Mock is the default; no provider provisioning."""
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
        if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            raise ValueError("Meta provider credentials are not configured")
        provider = MetaCloudWhatsAppProvider(settings.WHATSAPP_API_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID, settings.WHATSAPP_GRAPH_VERSION)
    else:
        raise ValueError("Unsupported WhatsApp provider")
    transport = HttpxHermesTransport(settings.WHATSAPP_SAAS_URL)
    gateway = HermesApiClient(transport, lambda: settings.WHATSAPP_ADAPTER_TOKEN.get_secret_value(), settings.WHATSAPP_SAAS_URL)
    def tenant_client(org):
        token = settings.WHATSAPP_TENANT_TOKENS.get(org)
        if not token:
            raise ValueError("Sender tenant has no machine credential")
        return HermesApiClient(transport, token.get_secret_value, settings.WHATSAPP_SAAS_URL)
    return WhatsAppWebhookService(provider, gateway, tenant_client)
