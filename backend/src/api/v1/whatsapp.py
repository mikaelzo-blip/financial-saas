"""Public webhook boundary. Adapter dispatch never receives a database session."""
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from src.core.config import settings
from src.services.integrations.whatsapp.security import valid_handshake, valid_signature
from src.services.hermes.retry import HermesApiError
from src.services.integrations.whatsapp.provider import ProviderError

router = APIRouter(prefix="/integrations/whatsapp", tags=["WhatsApp"])


@router.get("/webhook", response_class=PlainTextResponse)
async def handshake(request: Request):
    token = settings.WHATSAPP_VERIFY_TOKEN or settings.META_VERIFY_TOKEN
    if not valid_handshake(request.query_params.get("hub.mode", ""), request.query_params.get("hub.verify_token", ""), token.get_secret_value() if token else None):
        raise HTTPException(403, "Invalid webhook verification")
    return request.query_params.get("hub.challenge", "")


@router.post("/webhook")
async def webhook(request: Request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1024 * 1024:
            raise HTTPException(413, "Webhook payload too large")
    secret = settings.WHATSAPP_WEBHOOK_APP_SECRET or settings.META_APP_SECRET
    if not valid_signature(bytes(body), request.headers.get("X-Hub-Signature-256"), secret.get_secret_value() if secret else None):
        raise HTTPException(401, "Invalid webhook signature")
    service = getattr(request.app.state, "whatsapp_service", None)
    if service is None:
        from src.services.integrations.whatsapp.runtime import configured_service
        service = configured_service()
        if service is None:
            raise HTTPException(503, "WhatsApp adapter is not configured")
        request.app.state.whatsapp_service = service
    try:
        events = service.provider.parse(json.loads(body))
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        raise HTTPException(422, "Invalid WhatsApp payload") from None
    try:
        for event in events:
            await service.handle(event)
    except (HermesApiError, ProviderError, ValueError):
        raise HTTPException(503, "WhatsApp delivery temporarily unavailable") from None
    return {"status": "success"}
