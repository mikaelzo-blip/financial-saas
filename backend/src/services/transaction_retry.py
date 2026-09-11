from __future__ import annotations

import asyncio
import logging
import random
import re
from collections.abc import Awaitable, Callable, Collection
from typing import TypeVar

from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import asyncpg
    POSTGRES_BASE_EXCEPTIONS: tuple[type[BaseException], ...] = (DBAPIError, asyncpg.PostgresError)
except ImportError:  # pragma: no cover
    POSTGRES_BASE_EXCEPTIONS = (DBAPIError,)

from src.core.exceptions import TransactionContentionError
from src.services.tenant_sequence_allocator import (
    GENERATED_CODE_NAMESPACES_SESSION_KEY,
    SequenceCollisionError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_TRANSACTION_RETRY_ATTEMPTS = 3
RETRYABLE_TRANSIENT_SQLSTATES = {"40001", "40P01"}
LOCK_NOT_AVAILABLE_SQLSTATE = "55P03"
MIN_BACKOFF_SECONDS = 0.050
MAX_BACKOFF_SECONDS = 0.200

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


def extract_sqlstate(error: BaseException) -> str | None:
    """Extract PostgreSQL 5-character SQLSTATE from an exception or exception chain."""
    queue: list[BaseException] = [error]
    visited: set[int] = set()
    while queue:
        curr = queue.pop(0)
        if id(curr) in visited:
            continue
        visited.add(id(curr))

        for attr in ("sqlstate", "pgcode"):
            val = getattr(curr, attr, None)
            if isinstance(val, str) and len(val) == 5:
                return val.upper()

        diag = getattr(curr, "diag", None)
        if diag is not None:
            for attr in ("sqlstate", "pgcode", "sqlstate_code"):
                val = getattr(diag, attr, None)
                if isinstance(val, str) and len(val) == 5:
                    return val.upper()

        orig = getattr(curr, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in visited:
            queue.append(orig)
        if curr.__cause__ is not None and id(curr.__cause__) not in visited:
            queue.append(curr.__cause__)
        if curr.__context__ is not None and id(curr.__context__) not in visited:
            queue.append(curr.__context__)

    return None


def is_retryable_postgres_conflict(
    exc: BaseException,
    *,
    allow_lock_not_available: bool = False,
) -> bool:
    """Return True only if exc represents an approved transient PostgreSQL conflict.

    Approved transient SQLSTATEs:
    - 40001: serialization_failure
    - 40P01: deadlock_detected
    - 55P03: lock_not_available (only when allow_lock_not_available=True)
    """
    sqlstate = extract_sqlstate(exc)
    if sqlstate in RETRYABLE_TRANSIENT_SQLSTATES:
        return True
    if sqlstate == LOCK_NOT_AVAILABLE_SQLSTATE and allow_lock_not_available:
        return True
    return False


def calculate_retry_backoff(
    attempt: int,
    *,
    rng: random.Random | None = None,
) -> float:
    """Calculate bounded jittered delay between attempts in seconds (50ms to 200ms).

    attempt is 1-indexed (1 for first failure, 2 for second failure).
    """
    base = MIN_BACKOFF_SECONDS * (2 ** max(0, attempt - 1))
    capped = min(MAX_BACKOFF_SECONDS, base)
    rand = rng if rng is not None else random
    jitter = rand.uniform(MIN_BACKOFF_SECONDS, capped)
    return max(MIN_BACKOFF_SECONDS, min(MAX_BACKOFF_SECONDS, jitter))


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
    allow_lock_not_available: bool = False,
    sleeper: Callable[[float], Awaitable[None]] | None = None,
    delay_fn: Callable[[int], float] | None = None,
) -> T:
    """Retry a classified conflict after rolling back the caller transaction.

    The caller retains commit ownership. A failed PostgreSQL transaction is
    rolled back before the next operation attempt, so no statement runs in a
    poisoned transaction and each attempt starts from a clean transaction state.
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
        except POSTGRES_BASE_EXCEPTIONS as error:
            generated_namespaces = _generated_namespaces(session)
            await session.rollback()
            if hasattr(session, "expunge_all"):
                session.expunge_all()

            # 1. Transient PostgreSQL conflict (40001, 40P01, approved 55P03)
            if is_retryable_postgres_conflict(
                error, allow_lock_not_available=allow_lock_not_available
            ):
                if attempt == max_attempts:
                    sqlstate = extract_sqlstate(error)
                    raise TransactionContentionError(
                        f"Transaction could not be completed due to persistent concurrent "
                        f"conflict ({sqlstate}) after {max_attempts} attempts.",
                        details={"sqlstate": sqlstate, "attempts": max_attempts},
                    ) from error

                delay = (
                    delay_fn(attempt)
                    if delay_fn is not None
                    else calculate_retry_backoff(attempt)
                )
                logger.warning(
                    "Retrying transaction after transient PostgreSQL conflict %s "
                    "(attempt %s of %s, delay %.3fs)",
                    extract_sqlstate(error),
                    attempt,
                    max_attempts,
                    delay,
                )
                if sleeper is not None:
                    await sleeper(delay)
                else:
                    await asyncio.sleep(delay)
                continue

            # 2. Feature-012 generated business-code uniqueness collision
            if isinstance(error, IntegrityError) and is_retryable_generated_code_collision(
                error, generated_namespaces
            ):
                if attempt == max_attempts:
                    raise SequenceCollisionError(
                        "Generated business-code collision persisted after bounded retry"
                    ) from error

                delay = (
                    delay_fn(attempt)
                    if delay_fn is not None
                    else calculate_retry_backoff(attempt)
                )
                logger.warning(
                    "Retrying generated-code transaction after classified collision "
                    "(attempt %s of %s, delay %.3fs)",
                    attempt,
                    max_attempts,
                    delay,
                )
                if sleeper is not None:
                    await sleeper(delay)
                else:
                    await asyncio.sleep(delay)
                continue

            # 3. Non-retryable database error -> fail closed immediately
            raise

    raise AssertionError("unreachable")
