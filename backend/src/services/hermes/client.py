"""Replaceable authenticated HTTPS SaaS client used by Hermes orchestration."""
from typing import Callable, Protocol
from urllib.parse import urlparse

import httpx

from src.schemas.hermes import HermesDocumentOutcome, HermesSubmissionRequest
from src.services.hermes.retry import retry_submission


class HermesTransport(Protocol):
    """The only dependency an orchestration job may use to reach the SaaS."""

    async def upload_document(
        self, *, authorization: str, idempotency_key: str, file_name: str,
        mime_type: str, content: bytes, document_type: str = "UNKNOWN",
    ) -> dict: ...


class HttpxHermesTransport:
    """Default network adapter; it makes no database, storage, or ledger calls."""

    def __init__(self, api_base_url: str, *, timeout_seconds: float = 20.0):
        if urlparse(api_base_url).scheme != "https":
            raise ValueError("Hermes SaaS API base URL must use HTTPS")
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def upload_document(
        self, *, authorization: str, idempotency_key: str, file_name: str,
        mime_type: str, content: bytes, document_type: str = "UNKNOWN",
    ) -> dict:
        try:
            async with httpx.AsyncClient(base_url=self._api_base_url, timeout=self._timeout_seconds) as client:
                response = await client.post(
                    "/api/v1/hermes/documents/upload",
                    headers={"Authorization": authorization, "Idempotency-Key": idempotency_key},
                    data={"document_type": document_type},
                    files={"file": (file_name, content, mime_type)},
                )
        except httpx.TransportError as error:
            raise HermesApiError() from error
        if response.is_error:
            raise HermesApiError(status_code=response.status_code, code="SAAS_API_ERROR")
        return response.json()


class HermesApiClient:
    """API-only client; it intentionally has no ORM, storage, or posting methods."""

    def __init__(self, transport: HermesTransport, token_supplier: Callable[[], str], api_base_url: str):
        if urlparse(api_base_url).scheme != "https":
            raise ValueError("Hermes SaaS API base URL must use HTTPS")
        self._transport = transport
        self._token_supplier = token_supplier

    async def submit_document(
        self, request: HermesSubmissionRequest, *, file_name: str, mime_type: str,
        content: bytes, document_type: str = "UNKNOWN",
    ) -> HermesDocumentOutcome:
        """Submit once logically, retaining only API response metadata."""
        async def send() -> HermesDocumentOutcome:
            payload = await self._transport.upload_document(
                authorization=f"Bearer {self._token_supplier()}",
                idempotency_key=request.idempotency_key,
                file_name=file_name,
                mime_type=mime_type,
                content=content,
                document_type=document_type,
            )
            return HermesDocumentOutcome(
                document_id=payload["id"],
                document_code=payload["document_code"],
                processing_status=payload["processing_status"],
                correlation_id=payload.get("correlation_id"),
                review_required=payload["processing_status"] == "REVIEW_REQUIRED",
            )

        return await retry_submission(send)
