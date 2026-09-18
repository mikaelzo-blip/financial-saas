import uuid
from decimal import Decimal
import pytest

from src.models.enums import CostCategory, ExpenseCategory
from src.services.documents.expense_classifier import classify_expense, ExpenseClassificationResult


def test_project_fuel_transport():
    """Section 30: 'Bensin antar barang proyek Ancol' -> Direct project cost (TRN)."""
    ancol_id = uuid.uuid4()
    result = classify_expense(
        raw_description="Bensin antar barang proyek Ancol",
        caption="Bensin antar barang proyek Ancol",
        matched_project_id=ancol_id,
    )
    assert result.management_category == "Transportasi Proyek / BBM Proyek"
    assert result.cost_category == CostCategory.TRN
    assert result.expense_category is None
    assert result.project_id == ancol_id
    assert "5101" in (result.proposed_account_or_rule or "")
    assert not result.review_required


def test_office_vehicle_fuel():
    """Section 30: 'Bensin mobil kantor' -> Overhead transport (TRAVEL_OFFICE)."""
    result = classify_expense(
        raw_description="Bensin mobil kantor",
        caption="Bensin mobil kantor operasional",
        matched_project_id=None,
    )
    assert result.management_category == "Operasional Kendaraan"
    assert result.cost_category is None
    assert result.expense_category == ExpenseCategory.TRAVEL_OFFICE
    assert result.project_id is None
    assert "6104" in (result.proposed_account_or_rule or "")
    assert not result.review_required


def test_office_stationery():
    """Section 30: 'Kertas A4 kantor' -> Overhead administration (OFFICE_ADMIN)."""
    result = classify_expense(
        raw_description="Kertas A4 kantor",
        caption="Kertas A4 printer kantor",
        matched_project_id=None,
    )
    assert result.management_category == "ATK Kantor"
    assert result.cost_category is None
    assert result.expense_category == ExpenseCategory.OFFICE_ADMIN
    assert result.project_id is None
    assert "6103" in (result.proposed_account_or_rule or "")
    assert not result.review_required


def test_site_project_consumable():
    """Section 30: 'Marker dan kertas untuk site Ancol' -> Direct project cost (SIT)."""
    ancol_id = uuid.uuid4()
    result = classify_expense(
        raw_description="Marker dan kertas untuk site Ancol",
        caption="Pulpen, marker, kertas untuk site Proyek Ancol",
        matched_project_id=ancol_id,
    )
    assert result.management_category == "Consumable / ATK Proyek"
    assert result.cost_category == CostCategory.SIT
    assert result.expense_category is None
    assert result.project_id == ancol_id
    assert "5101" in (result.proposed_account_or_rule or "")
    assert not result.review_required


def test_site_generator_fuel():
    """Section 19: 'Solar genset proyek Ancol' -> Direct site cost (SIT)."""
    ancol_id = uuid.uuid4()
    result = classify_expense(
        raw_description="Solar genset proyek Ancol",
        caption="Solar genset proyek Ancol",
        matched_project_id=ancol_id,
    )
    assert result.management_category == "Bahan Bakar Proyek"
    assert result.cost_category == CostCategory.SIT
    assert result.expense_category is None
    assert result.project_id == ancol_id
    assert "5101" in (result.proposed_account_or_rule or "")
    assert not result.review_required


def test_ambiguous_spbu_receipt_no_context():
    """Section 19 & 30: SPBU receipt with no project or vehicle context -> REVIEW_REQUIRED."""
    result = classify_expense(
        raw_description="SPBU Pertamina 34-12345",
        caption=None,
        matched_project_id=None,
        document_text="Pertamina SPBU 34-12345 Solar Rp 150.000",
    )
    assert result.management_category == "BBM / Transportasi"
    assert result.cost_category is None
    assert result.expense_category is None
    assert result.project_id is None
    assert result.review_required is True
    assert "SPBU_RECEIPT_NO_CONTEXT" in result.classification_signals
    assert "PROJECT_OR_OVERHEAD_UNCERTAIN" in result.classification_conflicts


def test_caption_project_mismatch_conflict():
    """Section 17: Caption claims project Ancol but document text references Project Sudirman."""
    ancol_id = uuid.uuid4()
    result = classify_expense(
        raw_description="Bahan material proyek",
        caption="Untuk proyek Ancol",
        matched_project_id=ancol_id,
        document_project_hint="Proyek Sudirman Tower",
    )
    assert result.review_required is True
    assert "CAPTION_PROJECT_MISMATCH" in result.classification_conflicts
