import httpx
import pytest

from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from src.services.hermes.retry import HermesApiError
from src.schemas.hermes import HermesSubmissionRequest


@pytest.mark.parametrize("status,attempts", [(503, 3), (401, 1), (403, 1), (422, 1)])
async def test_bounded_retry_keeps_same_credential_and_idempotency_key(status, attempts):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    transport = HttpxHermesTransport("https://saas.test", transport=httpx.MockTransport(handler))
    client = HermesApiClient(transport, lambda: "test-tenant", "https://saas.test")
    with pytest.raises(HermesApiError):
        await client.submit_document(HermesSubmissionRequest(idempotency_key="wa-msg-retry-00001"), file_name="nota.pdf", mime_type="application/pdf", content=b"%PDF-1.4")
    assert len(calls) == attempts
    assert {call.headers["Idempotency-Key"] for call in calls} == {"wa-msg-retry-00001"}
    assert {call.headers["Authorization"] for call in calls} == {"Bearer test-tenant"}


async def test_transport_error_is_safe_and_bounded():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("sensitive transport details", request=request)
    transport = HttpxHermesTransport("https://saas.test", transport=httpx.MockTransport(handler))
    client = HermesApiClient(transport, lambda: "secret-not-in-errors", "https://saas.test")
    with pytest.raises(HermesApiError) as caught:
        await client.channel_request("status", {"phone_number": "+6281234567890"})
    assert len(calls) == 3
    assert "secret-not-in-errors" not in str(caught.value)
