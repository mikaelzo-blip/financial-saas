import uuid

from src.models.enums import CostCategory, ExpenseCategory
from src.services.documents.expense_classifier import classify_expense


def test_freight_is_logistics_cost():
    res = classify_expense(raw_description="JASA ANGKUT GERMAN TO JAKARTA")
    assert res.cost_category is CostCategory.LOG


def test_freight_with_a_physical_unit_stays_logistics_not_material():
    # A service word plus a unit ("2 TRUK") must not be read as material (MAT).
    res = classify_expense(raw_description="JASA ANGKUT 2 TRUK KE JAKARTA")
    assert res.cost_category is CostCategory.LOG


def test_stamp_duty_is_operational_expense():
    res = classify_expense(raw_description="STAMP")
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.OTHER_OPERATIONAL


def test_stamp_duty_stays_operational_even_with_a_project():
    # Stamp duty is overhead, never HPP, even on a project document.
    res = classify_expense(raw_description="STAMP", matched_project_id=uuid.uuid4())
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.OTHER_OPERATIONAL


def test_installation_service_is_subcontractor():
    res = classify_expense(raw_description="JASA PASANG BEARING POMPA")
    assert res.cost_category is CostCategory.SUB


def test_document_service_is_office_admin():
    res = classify_expense(raw_description="JASA PEMBUATAN DOKUMEN PROYEK")
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.OFFICE_ADMIN


def test_permit_and_licensing_is_permits_expense():
    # The company's Laba Rugi carries a distinct "BIAYA PERIJINAN *SBU" line, so
    # permits map to the PERMITS account (6105), not OFFICE_ADMIN (6103).
    res = classify_expense(raw_description="BIAYA PERIJINAN SBU")
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.PERMITS
