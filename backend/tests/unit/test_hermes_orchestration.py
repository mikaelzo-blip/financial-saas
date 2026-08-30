import uuid

import pytest

from src.schemas.hermes import HermesSubmissionRequest
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from src.services.hermes.retry import HermesApiError, is_retryable


class RetryingTransport:
    def __init__(self, failures: list[HermesApiError]):
        self.failures = failures
        self.calls: list[tuple[str, str]] = []

    async def upload_document(self, *, authorization, idempotency_key, file_name, mime_type, content, document_type="UNKNOWN"):
        self.calls.append((authorization, idempotency_key))
        if self.failures:
            raise self.failures.pop(0)
        return {"id": str(uuid.uuid4()), "document_code": "DOC-2026-000001", "processing_status": "REVIEW_REQUIRED"}


@pytest.mark.asyncio
async def test_orchestrator_retries_only_transient_api_failures_with_same_key():
    transport = RetryingTransport([HermesApiError(status_code=503)])
    client = HermesApiClient(transport, lambda: "runtime-only-token", "https://saas.test")
    request = HermesSubmissionRequest(idempotency_key="logical-evidence-submission-0003")
    outcome = await client.submit_document(request, file_name="evidence.pdf", mime_type="application/pdf", content=b"x")
    assert outcome.review_required is True
    assert transport.calls == [
        ("Bearer runtime-only-token", request.idempotency_key),
        ("Bearer runtime-only-token", request.idempotency_key),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 409, 422])
async def test_orchestrator_never_retries_control_outcomes(status_code):
    transport = RetryingTransport([HermesApiError(status_code=status_code)])
    client = HermesApiClient(transport, lambda: "runtime-only-token", "https://saas.test")
    with pytest.raises(HermesApiError):
        await client.submit_document(
            HermesSubmissionRequest(idempotency_key="logical-evidence-submission-0004"),
            file_name="evidence.pdf", mime_type="application/pdf", content=b"x",
        )
    assert len(transport.calls) == 1
    assert is_retryable(HermesApiError(status_code=status_code)) is False


def test_hermes_orchestration_package_has_no_database_or_accounting_dependencies():
    from pathlib import Path

    package = Path(__file__).parents[2] / "src" / "services" / "hermes"
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
    forbidden = ("src.core.database", "src.models", "DocumentService", "TransactionService", "Journal")
    assert not any(value in source for value in forbidden)
    assert not hasattr(HermesApiClient, "approve")
    assert not hasattr(HermesApiClient, "post")


def test_hermes_client_rejects_non_https_api_urls():
    transport = RetryingTransport([])
    with pytest.raises(ValueError, match="HTTPS"):
        HermesApiClient(transport, lambda: "runtime-only-token", "http://localhost")
    with pytest.raises(ValueError, match="HTTPS"):
        HttpxHermesTransport("http://localhost")
