from decimal import Decimal

from src.models.enums import CostCategory, ExpenseCategory
from src.schemas.document import LineItem


def test_line_item_accepts_per_line_categories():
    item = LineItem(
        description="JASA ANGKUT GERMAN TO JAKARTA",
        amount=Decimal("19927250"),
        cost_category=CostCategory.LOG,
    )
    assert item.cost_category is CostCategory.LOG
    assert item.expense_category is None


def test_line_item_categories_default_to_none():
    item = LineItem(description="STAMP", amount=Decimal("10000"))
    assert item.cost_category is None
    assert item.expense_category is None


def test_line_item_round_trips_through_json():
    item = LineItem(
        description="STAMP",
        amount=Decimal("10000"),
        expense_category=ExpenseCategory.OTHER_OPERATIONAL,
    )
    dumped = item.model_dump(mode="json")
    assert dumped["expense_category"] == "OTHER_OPERATIONAL"
    assert LineItem.model_validate(dumped).expense_category is ExpenseCategory.OTHER_OPERATIONAL
