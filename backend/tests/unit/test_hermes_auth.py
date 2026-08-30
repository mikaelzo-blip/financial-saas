import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.v1.hermes import get_hermes_organization_id
from src.core.config import settings


def request_with_authorization(value: str | None) -> Request:
    headers = [] if value is None else [(b"authorization", value.encode())]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers})


@pytest.mark.asyncio
async def test_hermes_machine_credential_is_tenant_bound(monkeypatch):
    organization_id = uuid.uuid4()
    monkeypatch.setattr(settings, "HERMES_AGENT_TOKEN", "test-machine-secret")
    monkeypatch.setattr(settings, "HERMES_ORGANIZATION_ID", str(organization_id))
    assert await get_hermes_organization_id(request_with_authorization("Bearer test-machine-secret")) == organization_id


@pytest.mark.asyncio
async def test_hermes_machine_credential_rejects_missing_or_invalid_tokens(monkeypatch):
    monkeypatch.setattr(settings, "HERMES_AGENT_TOKEN", "test-machine-secret")
    monkeypatch.setattr(settings, "HERMES_ORGANIZATION_ID", str(uuid.uuid4()))
    for value in (None, "Bearer wrong"):
        with pytest.raises(HTTPException) as error:
            await get_hermes_organization_id(request_with_authorization(value))
        assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_hermes_machine_endpoint_is_disabled_without_runtime_secret(monkeypatch):
    monkeypatch.setattr(settings, "HERMES_AGENT_TOKEN", None)
    monkeypatch.setattr(settings, "HERMES_ORGANIZATION_ID", None)
    with pytest.raises(HTTPException) as error:
        await get_hermes_organization_id(request_with_authorization("Bearer ignored"))
    assert error.value.status_code == 503
