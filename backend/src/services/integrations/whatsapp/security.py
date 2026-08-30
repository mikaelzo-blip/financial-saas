"""Verify raw webhook bytes before parsing any provider data."""
import hashlib
import hmac
import re


def valid_signature(body: bytes, signature: str | None, secret: str | None) -> bool:
    if not secret or not signature or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def valid_handshake(mode: str, token: str, expected: str | None) -> bool:
    return bool(expected and mode == "subscribe" and hmac.compare_digest(token.encode(), expected.encode()))
