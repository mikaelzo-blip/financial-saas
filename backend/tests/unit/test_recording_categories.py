"""Single source of truth: shared/recording-categories.json.

These tests pin the *derived* backend constants to the curated business rule.
If the shared file and the backend ever disagree, CI fails here.
"""
import json
from pathlib import Path

import pytest

from src.models.enums import CostCategory, ExpenseCategory
from src.services.recording_categories import (
    PROJECT_REQUIRED_COST_CATEGORIES,
    load_recording_categories,
)

SHARED_FILE = Path(__file__).resolve().parents[3] / "shared" / "recording-categories.json"


def test_shared_file_is_the_source_of_truth():
    # The canonical file must exist at the repo root; everything else derives from it.
    assert SHARED_FILE.exists(), f"missing canonical file: {SHARED_FILE}"


def test_loads_every_recording_category_in_order():
    entries = load_recording_categories()
    assert [e.value for e in entries] == [
        "MAT",
        "SUB",
        "TRN",
        "EQP",
        "LOG",
        "TRAVEL_OFFICE",
        "OFFICE_ADMIN",
        "OTHER_OPERATIONAL",
    ]


def test_project_required_cost_categories_matches_curated_business_rule():
    # LOG (logistics & freight) joined the project-required cost categories so
    # "JASA ANGKUT" lines can book to HPP 5101 instead of falling to 6199.
    assert PROJECT_REQUIRED_COST_CATEGORIES == {"MAT", "SUB", "TRN", "EQP", "LOG"}


def test_every_category_is_a_real_enum_member():
    for entry in load_recording_categories():
        if entry.kind == "cost":
            assert CostCategory(entry.value)
        else:
            assert ExpenseCategory(entry.value)


def test_derived_set_is_consistent_with_shared_file_contents():
    # Re-derive independently from the raw JSON: guards against a loader bug.
    raw = json.loads(SHARED_FILE.read_text(encoding="utf-8"))
    expected = {e["value"] for e in raw if e["kind"] == "cost" and e["requiresProject"]}
    assert PROJECT_REQUIRED_COST_CATEGORIES == expected


def test_fails_loud_when_file_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_recording_categories(tmp_path / "does-not-exist.json")
