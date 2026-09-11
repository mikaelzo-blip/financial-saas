from __future__ import annotations

import random
from unittest.mock import Mock

import pytest
from asyncpg.exceptions import (
    CheckViolationError,
    DeadlockDetectedError,
    ForeignKeyViolationError,
    LockNotAvailableError,
    SerializationError,
    UniqueViolationError,
)
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from src.core.exceptions import AppException, TransactionContentionError
from src.services.transaction_retry import (
    calculate_retry_backoff,
    extract_sqlstate,
    is_retryable_postgres_conflict,
)


def _make_dbapi_error(base_cls: type[DBAPIError], asyncpg_exc: Exception) -> DBAPIError:
    return base_cls("statement", {}, asyncpg_exc)


def test_transaction_contention_error_structure() -> None:
    exc = TransactionContentionError("Custom contention message", details={"attempt": 3})
    assert isinstance(exc, AppException)
    assert exc.status_code == 409
    assert exc.error_code == "TRANSACTION_CONTENTION"
    assert exc.message == "Custom contention message"
    assert exc.details == {"attempt": 3}


def test_extract_sqlstate_from_various_chains() -> None:
    # Direct asyncpg exception
    assert extract_sqlstate(SerializationError("serialization")) == "40001"
    assert extract_sqlstate(DeadlockDetectedError("deadlock")) == "40P01"
    assert extract_sqlstate(LockNotAvailableError("lock timeout")) == "55P03"

    # Wrapped in OperationalError
    op_err = _make_dbapi_error(OperationalError, SerializationError("serialization"))
    assert extract_sqlstate(op_err) == "40001"

    # Wrapped in DBAPIError
    db_err = _make_dbapi_error(DBAPIError, DeadlockDetectedError("deadlock"))
    assert extract_sqlstate(db_err) == "40P01"

    # Wrapped in IntegrityError
    integ_err = _make_dbapi_error(IntegrityError, UniqueViolationError("unique"))
    assert extract_sqlstate(integ_err) == "23505"

    # Non-DB exception
    assert extract_sqlstate(ValueError("not a db error")) is None

    # Deep nested cause chain
    root = SerializationError("serialization")
    mid = Exception("mid layer")
    mid.__cause__ = root
    top = OperationalError("statement", {}, mid)
    assert extract_sqlstate(top) == "40001"

    # Context chain (raised while handling another exception)
    ctx_exc = DeadlockDetectedError("deadlock")
    wrapper = RuntimeError("wrapper error")
    wrapper.__context__ = ctx_exc
    assert extract_sqlstate(wrapper) == "40P01"

    # Mock diagnostic object with sqlstate_code
    class CustomDiagError(Exception):
        class Diag:
            sqlstate_code = "40001"
        diag = Diag()

    assert extract_sqlstate(CustomDiagError()) == "40001"


def test_is_retryable_postgres_conflict_classification() -> None:
    # 40001: serialization_failure -> retry
    ser_err = _make_dbapi_error(OperationalError, SerializationError("40001"))
    assert is_retryable_postgres_conflict(ser_err) is True
    assert is_retryable_postgres_conflict(ser_err, allow_lock_not_available=False) is True

    # 40P01: deadlock_detected -> retry
    deadlock_err = _make_dbapi_error(DBAPIError, DeadlockDetectedError("40P01"))
    assert is_retryable_postgres_conflict(deadlock_err) is True
    assert is_retryable_postgres_conflict(deadlock_err, allow_lock_not_available=False) is True

    # 55P03: lock_not_available -> retry ONLY when explicitly approved
    lock_err = _make_dbapi_error(OperationalError, LockNotAvailableError("55P03"))
    assert is_retryable_postgres_conflict(lock_err, allow_lock_not_available=False) is False
    assert is_retryable_postgres_conflict(lock_err, allow_lock_not_available=True) is True

    # 23505: unique_violation -> NO retry via transient classifier
    uniq_err = _make_dbapi_error(IntegrityError, UniqueViolationError("23505"))
    assert is_retryable_postgres_conflict(uniq_err) is False
    assert is_retryable_postgres_conflict(uniq_err, allow_lock_not_available=True) is False

    # 23514: check_violation -> NO retry
    check_err = _make_dbapi_error(IntegrityError, CheckViolationError("23514"))
    assert is_retryable_postgres_conflict(check_err) is False

    # 23503: foreign_key_violation -> NO retry
    fk_err = _make_dbapi_error(IntegrityError, ForeignKeyViolationError("23503"))
    assert is_retryable_postgres_conflict(fk_err) is False

    # Arbitrary operational error without SQLSTATE -> NO retry (fail closed)
    raw_op_err = OperationalError("unknown connection abort", {}, Exception("opaque"))
    assert is_retryable_postgres_conflict(raw_op_err) is False


def test_calculate_retry_backoff_bounds() -> None:
    # Verify 100 iterations per attempt stay strictly within [0.050, 0.200]
    for attempt in (1, 2, 3):
        for _ in range(100):
            delay = calculate_retry_backoff(attempt)
            assert 0.050 <= delay <= 0.200, f"Attempt {attempt} delay {delay} outside [0.050, 0.200]"

    # Test with controlled RNG
    mock_rng_min = Mock()
    mock_rng_min.uniform.return_value = 0.010  # Below min -> clamp to 0.050
    assert calculate_retry_backoff(1, rng=mock_rng_min) == 0.050

    mock_rng_max = Mock()
    mock_rng_max.uniform.return_value = 0.500  # Above max -> clamp to 0.200
    assert calculate_retry_backoff(2, rng=mock_rng_max) == 0.200


@pytest.mark.asyncio
async def test_run_in_clean_transaction_unit_success_without_retry() -> None:
    session = Mock()
    session.info = {}
    session.flush = Mock()
    session.rollback = Mock()

    from unittest.mock import AsyncMock
    session.flush = AsyncMock()
    session.rollback = AsyncMock()

    from src.services.transaction_retry import run_in_clean_transaction

    calls = 0
    async def op(s):
        nonlocal calls
        calls += 1
        return "immediate_success"

    res = await run_in_clean_transaction(session, op)
    assert res == "immediate_success"
    assert calls == 1
    assert session.rollback.call_count == 0
    assert session.flush.call_count == 1


@pytest.mark.asyncio
async def test_run_in_clean_transaction_unit_exhaustion_details() -> None:
    from unittest.mock import AsyncMock
    from src.services.transaction_retry import run_in_clean_transaction

    session = Mock()
    session.info = {}
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.expunge_all = Mock()

    attempts = 0
    async def failing_op(s):
        nonlocal attempts
        attempts += 1
        raise OperationalError("stmt", {}, SerializationError("40001"))

    async def noop_sleep(_):
        pass

    with pytest.raises(TransactionContentionError) as exc_info:
        await run_in_clean_transaction(session, failing_op, sleeper=noop_sleep)

    assert attempts == 3
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "TRANSACTION_CONTENTION"
    assert exc_info.value.details == {"sqlstate": "40001", "attempts": 3}
    assert session.rollback.call_count == 3
    assert session.expunge_all.call_count == 3


@pytest.mark.asyncio
async def test_run_in_clean_transaction_unit_validation_error_not_retried() -> None:
    from unittest.mock import AsyncMock
    from src.services.transaction_retry import run_in_clean_transaction

    session = Mock()
    session.info = {}
    session.flush = AsyncMock()
    session.rollback = AsyncMock()

    attempts = 0
    async def invalid_op(s):
        nonlocal attempts
        attempts += 1
        raise ValueError("business validation failure")

    with pytest.raises(ValueError, match="business validation failure"):
        await run_in_clean_transaction(session, invalid_op)

    assert attempts == 1
    assert session.rollback.call_count == 0

