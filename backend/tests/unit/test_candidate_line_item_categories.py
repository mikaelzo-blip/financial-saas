import uuid
from decimal import Decimal

from src.models.enums import CostCategory, DocumentType, ExpenseCategory
from src.schemas.document import LineItem, StructuredExtraction
from src.services.documents.candidate import build_candidate


def _extraction():
    return StructuredExtraction(
        transaction_date="2026-09-14",
        total_amount=Decimal("19937250"),
        line_items=[
            LineItem(description="JASA ANGKUT GERMAN TO JAKARTA", amount=Decimal("19927250")),
            LineItem(description="STAMP", amount=Decimal("10000")),
        ],
    )


def test_build_candidate_suggests_category_per_line():
    data = _extraction()
    build_candidate(
        document_id=uuid.uuid4(),
        document_type=DocumentType.VENDOR_INVOICE,
        data=data,
        matches={},
        flags=[],
    )
    assert data.line_items[0].cost_category is CostCategory.LOG
    assert data.line_items[1].expense_category is ExpenseCategory.OTHER_OPERATIONAL
