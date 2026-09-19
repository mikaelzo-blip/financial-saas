"""The corrections endpoint must accept a corrected line_items list.

Regression guard: `line_items` was absent from the `allowed` whitelist, so a
reviewer editing per-line categories got a 422 and the change was lost.
"""
from src.api.v1.documents import ALLOWED_CORRECTION_FIELDS


def test_line_items_is_an_allowed_correction_field():
    assert "line_items" in ALLOWED_CORRECTION_FIELDS
