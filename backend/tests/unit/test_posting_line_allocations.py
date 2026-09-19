import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.exceptions import InvariantViolationException
from src.models.enums import CostCategory, ExpenseCategory
from src.services.document_posting_service import build_line_allocations


def _candidate(project_id=None):
    return SimpleNamespace(
        project_id=project_id,
        cost_category=CostCategory.MAT,
        expense_category=None,
        amount=Decimal("19937250"),
    )


def test_groups_lines_by_category_and_sums_each_group():
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "19927250", "cost_category": "LOG"},
            {"description": "STAMP", "amount": "10000", "expense_category": "OTHER_OPERATIONAL"},
        ]
    }
    allocs = build_line_allocations(extracted, _candidate(project_id=project_id))
    assert allocs is not None
    assert len(allocs) == 2
    by_cat = {a.cost_category or a.expense_category: a.amount for a in allocs}
    assert by_cat[CostCategory.LOG] == Decimal("19927250")
    assert by_cat[ExpenseCategory.OTHER_OPERATIONAL] == Decimal("10000")
    assert sum(a.amount for a in allocs) == Decimal("19937250")


def test_same_category_lines_are_merged_into_one_allocation():
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "SEMEN", "amount": "100", "cost_category": "MAT"},
            {"description": "BESI", "amount": "200", "cost_category": "MAT"},
        ]
    }
    allocs = build_line_allocations(extracted, _candidate(project_id=project_id))
    assert len(allocs) == 1
    assert allocs[0].amount == Decimal("300")


def test_returns_none_when_no_line_items():
    assert build_line_allocations({"line_items": []}, _candidate()) is None


def test_returns_none_when_no_category_anywhere():
    # No line category AND no document-level category -> keep legacy single path.
    extracted = {"line_items": [{"description": "X", "amount": "100"}]}
    bare = SimpleNamespace(
        project_id=None, cost_category=None, expense_category=None, amount=Decimal("100")
    )
    assert build_line_allocations(extracted, bare) is None


def test_uncategorised_lines_fall_back_to_document_category():
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "100", "cost_category": "LOG"},
            {"description": "NO CATEGORY", "amount": "50"},
        ]
    }
    allocs = build_line_allocations(extracted, _candidate(project_id=project_id))
    by_cat = {a.cost_category or a.expense_category: a.amount for a in allocs}
    assert by_cat[CostCategory.LOG] == Decimal("100")
    assert by_cat[CostCategory.MAT] == Decimal("50")
    assert all(a.project_id == project_id for a in allocs)


def test_operational_line_does_not_inherit_the_project():
    # posting_rules debits 5101 when an allocation has a project_id, else the
    # expense category's own account. An operational line on a project invoice
    # must therefore keep project_id=None, or it would book to HPP (5101).
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "19927250", "cost_category": "LOG"},
            {"description": "STAMP", "amount": "10000", "expense_category": "OTHER_OPERATIONAL"},
        ]
    }
    allocs = build_line_allocations(extracted, _candidate(project_id=project_id))
    by_cat = {a.cost_category or a.expense_category: a for a in allocs}
    assert by_cat[CostCategory.LOG].project_id == project_id
    assert by_cat[ExpenseCategory.OTHER_OPERATIONAL].project_id is None


def test_hpp_category_without_project_is_rejected():
    # A project-cost line with no project would silently book to 6199 in
    # posting_rules; refuse it here instead of posting to the wrong account.
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "100", "cost_category": "LOG"},
        ]
    }
    with pytest.raises(InvariantViolationException):
        build_line_allocations(extracted, _candidate(project_id=None))
