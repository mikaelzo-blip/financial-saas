import uuid
from decimal import Decimal

from src.models.enums import CostCategory, ExpenseCategory
from src.schemas.document import LineItem
from src.services.documents.line_item_classifier import classify_line_items


def test_suggests_log_for_freight_and_operational_for_stamp():
    items = [
        LineItem(description="JASA ANGKUT GERMAN TO JAKARTA", amount=Decimal("19927250")),
        LineItem(description="STAMP", amount=Decimal("10000")),
    ]
    out = classify_line_items(items, project_id=None)
    assert out[0].cost_category is CostCategory.LOG
    assert out[1].expense_category is ExpenseCategory.OTHER_OPERATIONAL
    assert out[1].cost_category is None


def test_never_overwrites_an_existing_reviewer_choice():
    items = [
        LineItem(
            description="JASA ANGKUT GERMAN TO JAKARTA",
            amount=Decimal("1000"),
            cost_category=CostCategory.SUB,
        )
    ]
    out = classify_line_items(items, project_id=None)
    assert out[0].cost_category is CostCategory.SUB


def test_preserves_amount_and_description():
    items = [LineItem(description="STAMP", amount=Decimal("10000"))]
    out = classify_line_items(items, project_id=uuid.uuid4())
    assert out[0].amount == Decimal("10000")
    assert out[0].description == "STAMP"
