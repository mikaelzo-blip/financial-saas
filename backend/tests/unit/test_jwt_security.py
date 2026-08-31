from datetime import timedelta
import pytest
from src.core.security import create_access_token, decode_access_token


def test_jwt_encode_decode_round_trip():
    token = create_access_token("user-123", {"organization_id": "org-456"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["organization_id"] == "org-456"


def test_expired_or_tampered_jwt_returns_none():
    expired = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(expired) is None
    valid = create_access_token("user-123")
    assert decode_access_token(valid + "tamper") is None
