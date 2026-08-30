import io
import hashlib
import pytest
from src.services.document_service import compute_sha256


def test_sha256_computation_determinism():
    """Verify SHA-256 file hash computation is deterministic and accurate."""
    content = b"Sample Invoice Content For Contractor Financial System 2026"
    expected_hash = hashlib.sha256(content).hexdigest()

    file_obj = io.BytesIO(content)
    computed_hash = compute_sha256(file_obj)

    assert computed_hash == expected_hash
    assert len(computed_hash) == 64
