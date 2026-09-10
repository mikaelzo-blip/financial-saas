from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Collection
from typing import TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.tenant_sequence_allocator import (
    GENERATED_CODE_NAMESPACES_SESSION_KEY,
    SequenceCollisionError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_TRANSACTION_RETRY_ATTEMPTS = 3

RETRYABLE_GENERATED_CODE_CONSTRAINTS = {
    "uq_transactions_org_code": "TRX",
    "uq_je_org_entry_number": "JE",
    "uq_projects_org_project_code": "PRJ",
    "uq_documents_org_document_code": "DOC",
    "uq_customer_invoices_org_code": "INV",
    "uq_vendor_bills_org_code": "BIL",
    "uq_vendor_advances_org_code": "ADV",
    "uq_customer_retention_releases_org_code": "REL",
    "uq_money_movements_org_code": "MM",
    "uq_settlements_org_code": "SET",
}


def _constraint_name(error: IntegrityError) -> str | None:
    original = error.orig
    candidates = (original, getattr(original, "orig", None), error.__cause__)
    for candidate in candidates:
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str):
            return name
        diagnostic = getattr(candidate, "diag", None)
        name = getattr(diagnostic, "constraint_name", None)
        if isinstance(name, str):
            return name
        match = re.search(r'constraint "([^"]+)"', str(candidate))
        if match:
            return match.group(1)
    return None


def is_retryable_generated_code_collision(
    error: IntegrityError,
    generated_namespaces: Collection[str],
) -> bool:
    """Retry only approved constraints for namespaces allocated in this attempt."""
    constraint_name = _constraint_name(error)
    required_namespace = RETRYABLE_GENERATED_CODE_CONSTRAINTS.get(constraint_name)
    return required_namespace is not None and required_namespace in generated_namespaces


def _generated_namespaces(session: AsyncSession) -> Collection[str]:
    return session.info.get(GENERATED_CODE_NAMESPACES_SESSION_KEY, ())


def _clear_generated_namespaces(session: AsyncSession) -> None:
    session.info[GENERATED_CODE_NAMESPACES_SESSION_KEY] = set()


async def run_in_clean_transaction(
    session: AsyncSession,
    operation: Callable[[AsyncSession], Awaitable[T]],
    *,
    max_attempts: int = MAX_TRANSACTION_RETRY_ATTEMPTS,
) -> T:
    """Retry a classified collision after rolling back the caller transaction.

    The caller retains commit ownership. A failed PostgreSQL transaction is
    rolled back before the next operation attempt, so no statement runs in a
    poisoned transaction and each attempt gets a fresh allocator transaction.
    """
    if not 1 <= max_attempts <= MAX_TRANSACTION_RETRY_ATTEMPTS:
        raise ValueError(
            f"max_attempts must be between 1 and {MAX_TRANSACTION_RETRY_ATTEMPTS}"
        )

    for attempt in range(1, max_attempts + 1):
        _clear_generated_namespaces(session)
        try:
            result = await operation(session)
            await session.flush()
            return result
        except IntegrityError as error:
            generated_namespaces = _generated_namespaces(session)
            await session.rollback()
            if not is_retryable_generated_code_collision(error, generated_namespaces):
                raise
            if attempt == max_attempts:
                raise SequenceCollisionError(
                    "Generated business-code collision persisted after bounded retry"
                ) from error
            logger.warning(
                "Retrying generated-code transaction after classified collision "
                "(attempt %s of %s)",
                attempt,
                max_attempts,
            )

    raise AssertionError("unreachable")
