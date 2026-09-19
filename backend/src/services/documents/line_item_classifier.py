"""Suggest a recording category for each invoice line item.

OCR proposes, the reviewer decides: this only fills a category when the line has
none, so an explicit reviewer choice is never overwritten.
"""
import uuid
from typing import List, Optional

from src.schemas.document import LineItem
from src.services.documents.expense_classifier import classify_expense


def classify_line_items(
    items: List[LineItem],
    project_id: Optional[uuid.UUID] = None,
) -> List[LineItem]:
    classified: List[LineItem] = []
    for item in items:
        if item.cost_category is not None or item.expense_category is not None:
            classified.append(item)
            continue
        result = classify_expense(
            raw_description=item.description or "",
            matched_project_id=project_id,
        )
        classified.append(
            item.model_copy(
                update={
                    "cost_category": result.cost_category,
                    "expense_category": result.expense_category,
                }
            )
        )
    return classified
