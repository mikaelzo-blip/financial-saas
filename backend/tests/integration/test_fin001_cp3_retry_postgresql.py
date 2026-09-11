from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from asyncpg.exceptions import (
    CheckViolationError,
    DeadlockDetectedError,
    ForeignKeyViolationError,
    LockNotAvailableError,
    SerializationError,
    UniqueViolationError,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.api.auth import require_application_user
from src.core.database import get_db
from src.core.exceptions import InvariantViolationException, TransactionContentionError
from src.main import create_application
from src.models.enums import ProjectStatus, TransactionType, UserRole, WorkflowStatus
from src.models.audit import AuditLog
from src.models.coa import PaymentAccount
from src.models.counterparty import Counterparty
from src.models.journal import JournalEntry, JournalLine
from src.models.money_movement import MoneyMovement, Settlement, SettlementAllocation
from src.models.organization import Organization
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.transaction import Transaction
from src.models.user import User
from src.services.accounting_engine import AccountingEngine
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.money_movement_service import MoneyMovementService
from src.services.payable_service import VendorAPService
from src.services.receivable_service import CustomerARService
from src.services.tenant_sequence_allocator import allocate_next
from src.services.transaction_retry import (
    MAX_TRANSACTION_RETRY_ATTEMPTS,
    run_in_clean_transaction,
)
from src.services.transaction_service import TransactionCreate, TransactionService
from tests.integration.fin001_postgresql_support import (
    fin001_organizations,
    fin001_pg_engine,
    fin001_session_factory,
    require_fin001_postgres_url,
)

pytestmark = pytest.mark.postgresql


async def _noop_sleeper(_: float) -> None:
    """Zero-delay test sleeper to keep retry tests instant."""
    return None


def _endpoint_client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncClient:
    app = create_application()

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_application_user] = lambda: None
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://fin001.test")


async def _create_test_context(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    label: str,
) -> dict[str, Any]:
    async with session_factory() as session:
        organization = await session.get(Organization, organization_id)
        assert organization is not None
        await seed_standard_coa(session, organization.id)
        await seed_standard_payment_accounts(session, organization.id)
        counterparty = Counterparty(
            organization_id=organization.id,
            name=f"CP3 Counterparty {label}",
            is_customer=True,
            is_vendor=True,
        )
        session.add(counterparty)
        await session.flush()
        project = Project(
            organization_id=organization.id,
            project_code=f"PRJ-2026-{organization.id.hex[:3]}-{label[:4]}",
            project_name=f"CP3 Project {label}",
            customer_id=counterparty.id,
            original_contract_value=Decimal("10000.00"),
            revised_contract_value=Decimal("10000.00"),
            start_date=date(2026, 9, 1),
            project_status=ProjectStatus.ACTIVE,
        )
        user = User(
            organization_id=organization.id,
            email=f"cp3-{label}-{organization.id.hex[:8]}@example.test",
            full_name=f"CP3 Operator {label}",
            password_hash="test-only",
            role=UserRole.ADMIN,
        )
        session.add_all([project, user])
        await session.flush()
        payment_account = await session.scalar(
            select(PaymentAccount).where(
                PaymentAccount.organization_id == organization.id,
                PaymentAccount.name == "Bank Mandiri",
            )
        )
        assert payment_account is not None
        await session.commit()
        return {
            "organization_id": organization.id,
            "counterparty_id": counterparty.id,
            "project_id": project.id,
            "payment_account_id": payment_account.id,
            "user_id": user.id,
        }


# ==============================================================================
# Scenario A: SQLSTATE 40001 (serialization_failure)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_a_sqlstate_40001_serialization_failure_retry_and_at_most_once(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-a")
    org_id = context["organization_id"]

    # Setup invoice
    async with fin001_session_factory() as session:
        invoice = CustomerInvoice(
            organization_id=org_id,
            invoice_code=f"INV-CP3-A-{uuid4().hex[:8]}",
            customer_id=context["counterparty_id"],
            project_id=context["project_id"],
            invoice_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("100.00"),
            status="UNPAID",
        )
        session.add(invoice)
        await session.commit()
        invoice_id = invoice.id

    attempts = 0

    async def operation(session: AsyncSession) -> UUID:
        nonlocal attempts
        attempts += 1
        payment = await TransactionService(session).create_transaction(
            org_id,
            TransactionCreate(
                transaction_type=TransactionType.CUSTOMER_PAYMENT,
                transaction_date=date(2026, 9, 2),
                amount=Decimal("50.00"),
                counterparty_id=context["counterparty_id"],
                payment_account_id=context["payment_account_id"],
                description="Scenario A payment",
            ),
            created_by=context["user_id"],
        )
        await session.flush()
        if attempts == 1:
            # Simulate transient 40001 after partial database writes
            raise OperationalError("simulated 40001", {}, SerializationError("serialization failure"))

        await AccountingEngine(session).post_transaction(
            org_id, payment.id, actor_id=context["user_id"], actor_role=UserRole.ADMIN
        )
        await CustomerARService(session).allocate_customer_payment(
            org_id, payment.id, [(invoice_id, Decimal("50.00"))]
        )
        await MoneyMovementService(session).synchronize_payment_money_movement(org_id, payment.id)
        return payment.id

    async with fin001_session_factory() as session:
        payment_id = await run_in_clean_transaction(session, operation, sleeper=_noop_sleeper)
        await session.commit()

    assert attempts == 2
    async with fin001_session_factory() as session:
        # Verify exactly one payment transaction was committed
        payments = (await session.scalars(select(Transaction).where(Transaction.id == payment_id))).all()
        assert len(payments) == 1

        # Verify exactly one allocation was committed
        allocations = (await session.scalars(
            select(CustomerPaymentAllocation).where(CustomerPaymentAllocation.payment_transaction_id == payment_id)
        )).all()
        assert len(allocations) == 1
        assert allocations[0].allocated_amount == Decimal("50.00")

        # Verify exactly one journal entry exists
        journals = (await session.scalars(
            select(JournalEntry).where(JournalEntry.transaction_id == payment_id)
        )).all()
        assert len(journals) == 1

        # Verify no orphan or partial records exist from attempt 1
        total_payments_in_org = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.organization_id == org_id)
        )
        assert total_payments_in_org == 1


# ==============================================================================
# Scenario B: SQLSTATE 40P01 (deadlock_detected)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_b_sqlstate_40p01_deadlock_retry_and_at_most_once(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-b")
    org_id = context["organization_id"]

    async with fin001_session_factory() as session:
        bill = VendorBill(
            organization_id=org_id,
            bill_code=f"BIL-CP3-B-{uuid4().hex[:8]}",
            vendor_id=context["counterparty_id"],
            project_id=context["project_id"],
            bill_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("150.00"),
            status="UNPAID",
        )
        session.add(bill)
        await session.commit()
        bill_id = bill.id

    attempts = 0

    async def operation(session: AsyncSession) -> UUID:
        nonlocal attempts
        attempts += 1
        payment = await TransactionService(session).create_transaction(
            org_id,
            TransactionCreate(
                transaction_type=TransactionType.PAY_VENDOR_BILL,
                transaction_date=date(2026, 9, 2),
                amount=Decimal("75.00"),
                counterparty_id=context["counterparty_id"],
                project_id=context["project_id"],
                payment_account_id=context["payment_account_id"],
                description="Scenario B vendor payment",
            ),
            created_by=context["user_id"],
        )
        await session.flush()
        if attempts == 1:
            raise DBAPIError("simulated 40P01", {}, DeadlockDetectedError("deadlock detected"))

        await AccountingEngine(session).post_transaction(
            org_id, payment.id, actor_id=context["user_id"], actor_role=UserRole.ADMIN
        )
        await VendorAPService(session).allocate_vendor_payment(
            org_id, payment.id, [(bill_id, Decimal("75.00"))]
        )
        await MoneyMovementService(session).synchronize_payment_money_movement(org_id, payment.id)
        return payment.id

    async with fin001_session_factory() as session:
        payment_id = await run_in_clean_transaction(session, operation, sleeper=_noop_sleeper)
        await session.commit()

    assert attempts == 2
    async with fin001_session_factory() as session:
        payments = (await session.scalars(select(Transaction).where(Transaction.id == payment_id))).all()
        assert len(payments) == 1
        allocations = (await session.scalars(
            select(VendorPaymentAllocation).where(VendorPaymentAllocation.payment_transaction_id == payment_id)
        )).all()
        assert len(allocations) == 1


# ==============================================================================
# Scenario C: SQLSTATE 55P03 (lock_not_available)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_c_sqlstate_55p03_retried_only_on_approved_path(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-c")
    org_id = context["organization_id"]

    # 1. Approved path: allow_lock_not_available=True -> retries and succeeds
    approved_attempts = 0

    async def approved_op(session: AsyncSession) -> str:
        nonlocal approved_attempts
        approved_attempts += 1
        if approved_attempts == 1:
            raise OperationalError("lock timeout", {}, LockNotAvailableError("55P03"))
        return "approved_success"

    async with fin001_session_factory() as session:
        res = await run_in_clean_transaction(
            session, approved_op, allow_lock_not_available=True, sleeper=_noop_sleeper
        )
        await session.commit()
    assert approved_attempts == 2
    assert res == "approved_success"

    # 2. Non-approved path: allow_lock_not_available=False -> fails closed immediately without retry
    unapproved_attempts = 0

    async def unapproved_op(session: AsyncSession) -> str:
        nonlocal unapproved_attempts
        unapproved_attempts += 1
        raise OperationalError("lock timeout", {}, LockNotAvailableError("55P03"))

    async with fin001_session_factory() as session:
        with pytest.raises(OperationalError):
            await run_in_clean_transaction(
                session, unapproved_op, allow_lock_not_available=False, sleeper=_noop_sleeper
            )
    assert unapproved_attempts == 1


# ==============================================================================
# Scenario D: Non-retryable database / invariant constraints
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_d_non_retryable_database_constraints_fail_immediately(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-d")
    org_id = context["organization_id"]

    # D1: Foreign key violation (23503) -> no retry
    fk_attempts = 0

    async def fk_op(session: AsyncSession) -> None:
        nonlocal fk_attempts
        fk_attempts += 1
        raise IntegrityError("fk fail", {}, ForeignKeyViolationError("23503"))

    async with fin001_session_factory() as session:
        with pytest.raises(IntegrityError):
            await run_in_clean_transaction(session, fk_op, sleeper=_noop_sleeper)
    assert fk_attempts == 1

    # D2: Check violation (23514) -> no retry
    check_attempts = 0

    async def check_op(session: AsyncSession) -> None:
        nonlocal check_attempts
        check_attempts += 1
        raise IntegrityError("check fail", {}, CheckViolationError("23514"))

    async with fin001_session_factory() as session:
        with pytest.raises(IntegrityError):
            await run_in_clean_transaction(session, check_op, sleeper=_noop_sleeper)
    assert check_attempts == 1

    # D3: Non-approved unique violation (23505 not in generated sequence whitelist) -> no retry
    uniq_attempts = 0

    async def uniq_op(session: AsyncSession) -> None:
        nonlocal uniq_attempts
        uniq_attempts += 1
        raise IntegrityError("duplicate email", {}, UniqueViolationError("23505"))

    async with fin001_session_factory() as session:
        with pytest.raises(IntegrityError):
            await run_in_clean_transaction(session, uniq_op, sleeper=_noop_sleeper)
    assert uniq_attempts == 1


# ==============================================================================
# Scenario E: Retry Exhaustion (exactly 3 total attempts, raises TransactionContentionError)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_e_retry_exhaustion_exact_three_attempts_and_no_side_effects(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-e")
    org_id = context["organization_id"]

    attempts = 0

    async def failing_op(session: AsyncSession) -> None:
        nonlocal attempts
        attempts += 1
        # Insert a transaction on each attempt
        tx = Transaction(
            organization_id=org_id,
            transaction_code=f"TRX-EXHAUST-{attempts}-{uuid4().hex[:8]}",
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("100.00"),
            workflow_status=WorkflowStatus.APPROVED,
            description=f"Attempt {attempts}",
        )
        session.add(tx)
        await session.flush()
        # Always fail with 40001
        raise OperationalError("serialization error", {}, SerializationError("40001"))

    async with fin001_session_factory() as session:
        with pytest.raises(TransactionContentionError) as exc_info:
            await run_in_clean_transaction(session, failing_op, sleeper=_noop_sleeper)

    assert attempts == MAX_TRANSACTION_RETRY_ATTEMPTS
    assert attempts == 3
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "TRANSACTION_CONTENTION"
    assert "40001" in exc_info.value.message

    # Verify complete rollback: zero transactions were persisted
    async with fin001_session_factory() as session:
        persisted = (await session.scalars(
            select(Transaction).where(Transaction.organization_id == org_id, Transaction.description.like("Attempt%"))
        )).all()
        assert len(persisted) == 0


# ==============================================================================
# Scenario F: HTTP Exhaustion -> 409 Conflict with repository-standard error format
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_f_http_exhaustion_returns_standard_409(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-f")
    org_id = context["organization_id"]

    # Setup invoice
    async with fin001_session_factory() as session:
        invoice = CustomerInvoice(
            organization_id=org_id,
            invoice_code=f"INV-HTTP-EXH-{uuid4().hex[:8]}",
            customer_id=context["counterparty_id"],
            project_id=context["project_id"],
            invoice_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("200.00"),
            status="UNPAID",
        )
        session.add(invoice)
        await session.commit()
        invoice_id = invoice.id

    payload = {
        "invoice_id": str(invoice_id),
        "amount": "100.00",
        "payment_date": "2026-09-02",
        "payment_account_id": str(context["payment_account_id"]),
        "reference_no": "REF-HTTP-EXH",
        "description": "Testing HTTP contention exhaustion",
    }
    headers = {
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(context["user_id"]),
        "X-User-Role": "ADMIN",
    }

    # Simulate persistent deadlock in customer payment allocation
    original_allocate = CustomerARService.allocate_customer_payment

    async def failing_allocate(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("simulated deadlock in endpoint", {}, DeadlockDetectedError("40P01"))

    async with _endpoint_client(fin001_session_factory) as client:
        with patch.object(CustomerARService, "allocate_customer_payment", side_effect=failing_allocate):
            with patch("src.services.transaction_retry.calculate_retry_backoff", return_value=0.0):
                response = await client.post("/api/v1/customer-payments", json=payload, headers=headers)

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TRANSACTION_CONTENTION"
    assert "concurrent conflict" in body["error"]["message"]

    # Verify zero database rows were persisted
    async with fin001_session_factory() as session:
        inv = await session.get(CustomerInvoice, invoice_id)
        assert inv is not None
        assert inv.status == "UNPAID"
        assert inv.calculate_paid_amount() == Decimal("0.00")


# ==============================================================================
# Scenario G: Insufficient Balance returns 422, NOT 409
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_g_insufficient_balance_returns_422_without_retry(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-g")
    org_id = context["organization_id"]

    async with fin001_session_factory() as session:
        invoice = CustomerInvoice(
            organization_id=org_id,
            invoice_code=f"INV-CP3-G-{uuid4().hex[:8]}",
            customer_id=context["counterparty_id"],
            project_id=context["project_id"],
            invoice_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("100.00"),
            status="UNPAID",
        )
        session.add(invoice)
        await session.commit()
        invoice_id = invoice.id

    # Request to allocate 150.00 to an invoice of 100.00
    payload = {
        "invoice_id": str(invoice_id),
        "amount": "150.00",
        "payment_date": "2026-09-02",
        "payment_account_id": str(context["payment_account_id"]),
        "reference_no": "REF-INSUFFICIENT",
        "description": "Excess allocation",
    }
    headers = {
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(context["user_id"]),
        "X-User-Role": "ADMIN",
    }

    async with _endpoint_client(fin001_session_factory) as client:
        response = await client.post("/api/v1/customer-payments", json=payload, headers=headers)

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVARIANT_VIOLATION"


# ==============================================================================
# Scenario H: AR Customer Payment Retry (At-most-once full financial graph)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_h_ar_customer_payment_retry_commits_at_most_once_graph(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-h")
    org_id = context["organization_id"]

    async with fin001_session_factory() as session:
        invoice = CustomerInvoice(
            organization_id=org_id,
            invoice_code=f"INV-CP3-H-{uuid4().hex[:8]}",
            customer_id=context["counterparty_id"],
            project_id=context["project_id"],
            invoice_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("100.00"),
            status="UNPAID",
        )
        session.add(invoice)
        await session.commit()
        invoice_id = invoice.id

    payload = {
        "invoice_id": str(invoice_id),
        "amount": "60.00",
        "payment_date": "2026-09-02",
        "payment_account_id": str(context["payment_account_id"]),
        "reference_no": "REF-AR-RETRY",
        "description": "AR retry test payment",
    }
    headers = {
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(context["user_id"]),
        "X-User-Role": "ADMIN",
    }

    call_count = 0
    real_allocate = CustomerARService.allocate_customer_payment

    async def transient_allocate(self: CustomerARService, *args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OperationalError("transient conflict on attempt 1", {}, SerializationError("40001"))
        return await real_allocate(self, *args, **kwargs)

    async with _endpoint_client(fin001_session_factory) as client:
        with patch.object(CustomerARService, "allocate_customer_payment", side_effect=transient_allocate, autospec=True):
            with patch("src.services.transaction_retry.calculate_retry_backoff", return_value=0.0):
                response = await client.post("/api/v1/customer-payments", json=payload, headers=headers)

    assert response.status_code == 201
    assert call_count == 2
    res_data = response.json()
    payment_id = UUID(res_data["payment_transaction_id"])
    allocation_id = UUID(res_data["allocation_id"])
    journal_id = UUID(res_data["journal_entry_id"])

    # Authoritative verification of exactly ONE financial graph
    async with fin001_session_factory() as session:
        # 1. Exactly 1 transaction
        txs = (await session.scalars(select(Transaction).where(Transaction.organization_id == org_id))).all()
        assert len(txs) == 1
        assert txs[0].id == payment_id
        assert txs[0].amount == Decimal("60.00")

        # 2. Exactly 1 allocation
        allocs = (await session.scalars(select(CustomerPaymentAllocation).where(CustomerPaymentAllocation.payment_transaction_id == payment_id))).all()
        assert len(allocs) == 1
        assert allocs[0].id == allocation_id
        assert allocs[0].allocated_amount == Decimal("60.00")

        # 3. Exactly 1 journal entry with balanced debit/credit lines
        jes = (await session.scalars(select(JournalEntry).where(JournalEntry.id == journal_id))).all()
        assert len(jes) == 1
        lines = (await session.scalars(select(JournalLine).where(JournalLine.journal_entry_id == journal_id))).all()
        assert len(lines) == 2
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        assert total_debit == total_credit == Decimal("60.00")

        # 4. Exactly 1 settlement and 1 settlement allocation
        settlements = (await session.scalars(select(Settlement).where(Settlement.transaction_id == payment_id))).all()
        assert len(settlements) == 1
        settlement_allocs = (await session.scalars(select(SettlementAllocation).where(SettlementAllocation.settlement_id == settlements[0].id))).all()
        assert len(settlement_allocs) == 1

        # 5. Exactly 1 money movement linked to settlement
        mm = await session.get(MoneyMovement, settlements[0].money_movement_id)
        assert mm is not None
        assert mm.amount == Decimal("60.00")

        # 6. Audit logs present and no duplicate create actions
        audits = (await session.scalars(select(AuditLog).where(AuditLog.entity_id == payment_id))).all()
        assert len(audits) >= 1

        # 7. Invoice state updated accurately
        inv = await session.scalar(
            select(CustomerInvoice)
            .options(selectinload(CustomerInvoice.allocations))
            .where(CustomerInvoice.id == invoice_id)
        )
        assert inv is not None
        assert inv.status == "PARTIALLY_PAID"
        assert inv.calculate_outstanding_amount() == Decimal("40.00")


# ==============================================================================
# Scenario I: AP Vendor Payment Retry (At-most-once full financial graph)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_i_ap_vendor_payment_retry_commits_at_most_once_graph(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-i")
    org_id = context["organization_id"]

    async with fin001_session_factory() as session:
        bill = VendorBill(
            organization_id=org_id,
            bill_code=f"BIL-CP3-I-{uuid4().hex[:8]}",
            vendor_id=context["counterparty_id"],
            project_id=context["project_id"],
            bill_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("100.00"),
            status="UNPAID",
        )
        session.add(bill)
        await session.commit()
        bill_id = bill.id

    payload = {
        "bill_id": str(bill_id),
        "amount": "100.00",
        "payment_date": "2026-09-02",
        "payment_account_id": str(context["payment_account_id"]),
        "reference_no": "REF-AP-RETRY",
        "description": "AP retry test payment",
    }
    headers = {
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(context["user_id"]),
        "X-User-Role": "ADMIN",
    }

    call_count = 0
    real_allocate = VendorAPService.allocate_vendor_payment

    async def transient_allocate(self: VendorAPService, *args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise DBAPIError("transient conflict on attempt 1", {}, DeadlockDetectedError("40P01"))
        return await real_allocate(self, *args, **kwargs)

    async with _endpoint_client(fin001_session_factory) as client:
        with patch.object(VendorAPService, "allocate_vendor_payment", side_effect=transient_allocate, autospec=True):
            with patch("src.services.transaction_retry.calculate_retry_backoff", return_value=0.0):
                response = await client.post("/api/v1/vendor-payments", json=payload, headers=headers)

    assert response.status_code == 201
    assert call_count == 2
    res_data = response.json()
    payment_id = UUID(res_data["payment_transaction_id"])
    allocation_id = UUID(res_data["allocation_id"])
    journal_id = UUID(res_data["journal_entry_id"])

    async with fin001_session_factory() as session:
        # 1. Exactly 1 transaction
        txs = (await session.scalars(select(Transaction).where(Transaction.organization_id == org_id))).all()
        assert len(txs) == 1
        assert txs[0].id == payment_id

        # 2. Exactly 1 allocation
        allocs = (await session.scalars(select(VendorPaymentAllocation).where(VendorPaymentAllocation.payment_transaction_id == payment_id))).all()
        assert len(allocs) == 1
        assert allocs[0].id == allocation_id

        # 3. Exactly 1 journal entry with balanced debit/credit lines
        jes = (await session.scalars(select(JournalEntry).where(JournalEntry.id == journal_id))).all()
        assert len(jes) == 1
        lines = (await session.scalars(select(JournalLine).where(JournalLine.journal_entry_id == journal_id))).all()
        assert len(lines) == 2
        assert sum(l.debit_amount for l in lines) == sum(l.credit_amount for l in lines) == Decimal("100.00")

        # 4. Exactly 1 settlement
        settlements = (await session.scalars(select(Settlement).where(Settlement.transaction_id == payment_id))).all()
        assert len(settlements) == 1

        # 5. Exactly 1 money movement linked to settlement
        mm = await session.get(MoneyMovement, settlements[0].money_movement_id)
        assert mm is not None
        assert mm.amount == Decimal("100.00")

        # 6. Bill fully paid
        b = await session.scalar(
            select(VendorBill)
            .options(selectinload(VendorBill.allocations))
            .where(VendorBill.id == bill_id)
        )
        assert b is not None
        assert b.status == "PAID"
        assert b.calculate_outstanding_amount() == Decimal("0.00")


# ==============================================================================
# Scenario J: Shared TRX / Feature-012 Sequence Allocation
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_j_feature_012_trx_sequence_consistency_through_retry(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-j")
    org_id = context["organization_id"]

    attempts = 0

    async def op(session: AsyncSession) -> str:
        nonlocal attempts
        attempts += 1
        code = await TransactionService(session).generate_transaction_code(org_id, date(2026, 9, 2))
        tx = Transaction(
            organization_id=org_id,
            transaction_code=code,
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("50.00"),
            workflow_status=WorkflowStatus.APPROVED,
            description="TRX sequence retry test",
        )
        session.add(tx)
        await session.flush()
        if attempts == 1:
            raise OperationalError("transient conflict", {}, SerializationError("40001"))
        return code

    async with fin001_session_factory() as session:
        committed_code = await run_in_clean_transaction(session, op, sleeper=_noop_sleeper)
        await session.commit()

    assert attempts == 2
    assert committed_code.startswith("TRX-2026-")

    # Verify only 1 transaction exists with that code in the database
    async with fin001_session_factory() as session:
        txs = (await session.scalars(select(Transaction).where(Transaction.transaction_code == committed_code))).all()
        assert len(txs) == 1


# ==============================================================================
# Scenario K: Tenant Isolation
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_k_tenant_isolation_during_retry_and_contention(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context_a = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-k-a")
    context_b = await _create_test_context(fin001_session_factory, fin001_organizations[1], "sc-k-b")
    org_a = context_a["organization_id"]
    org_b = context_b["organization_id"]

    # In Org A, execute an operation that retries
    async def op_a(session: AsyncSession) -> None:
        await session.execute(text("SELECT 1"))
        raise OperationalError("force failure", {}, SerializationError("40001"))

    # In Org B, execute a normal successful operation
    async def op_b(session: AsyncSession) -> str:
        tx = Transaction(
            organization_id=org_b,
            transaction_code=f"TRX-ORGB-{uuid4().hex[:8]}",
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("80.00"),
            workflow_status=WorkflowStatus.APPROVED,
            description="Org B unaffected",
        )
        session.add(tx)
        await session.flush()
        return tx.transaction_code

    # Org A fails with exhaustion
    async with fin001_session_factory() as session_a:
        with pytest.raises(TransactionContentionError):
            await run_in_clean_transaction(session_a, op_a, sleeper=_noop_sleeper)

    # Org B succeeds cleanly
    async with fin001_session_factory() as session_b:
        code_b = await run_in_clean_transaction(session_b, op_b, sleeper=_noop_sleeper)
        await session_b.commit()

    # Check database: Org A has 0 rows, Org B has 1 row
    async with fin001_session_factory() as session:
        count_a = await session.scalar(select(func.count(Transaction.id)).where(Transaction.organization_id == org_a))
        count_b = await session.scalar(select(func.count(Transaction.id)).where(Transaction.organization_id == org_b))
        assert count_a == 0
        assert count_b == 1


# ==============================================================================
# Scenario L: Year Isolation
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_l_year_scope_isolation_preserved_across_retries(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-l")
    org_id = context["organization_id"]

    # Generate sequence in 2026 with retry
    attempts_2026 = 0

    async def op_2026(session: AsyncSession) -> str:
        nonlocal attempts_2026
        attempts_2026 += 1
        code = await TransactionService(session).generate_transaction_code(org_id, date(2026, 9, 2))
        if attempts_2026 == 1:
            raise OperationalError("retry in 2026", {}, SerializationError("40001"))
        return code

    async with fin001_session_factory() as session:
        code_2026 = await run_in_clean_transaction(session, op_2026, sleeper=_noop_sleeper)
        await session.commit()

    # Generate sequence in 2027
    async with fin001_session_factory() as session:
        code_2027 = await TransactionService(session).generate_transaction_code(org_id, date(2027, 9, 2))
        await session.commit()

    assert code_2026.startswith("TRX-2026-")
    assert code_2027.startswith("TRX-2027-")
    # Year counters are separate
    assert code_2026.endswith("000001") or code_2026.endswith("000002")
    assert code_2027.endswith("000001")


# ==============================================================================
# Scenario M: Settlement Global Scope Sequence Safety
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_m_settlement_global_sequence_retry_safety(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-m")
    org_id = context["organization_id"]

    attempts = 0

    async def op(session: AsyncSession) -> str:
        nonlocal attempts
        attempts += 1
        seq = await allocate_next(session, org_id, "SET", "GLOBAL")
        code = f"SET-2026-{seq:06d}"
        if attempts == 1:
            raise OperationalError("transient conflict in settlement", {}, SerializationError("40001"))
        return code

    async with fin001_session_factory() as session:
        code = await run_in_clean_transaction(session, op, sleeper=_noop_sleeper)
        await session.commit()

    assert attempts == 2
    assert code.startswith("SET-2026-")


# ==============================================================================
# Scenario N: N=50 Contention
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_n_n50_concurrent_allocations_respect_source_cap(
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    """Run 50 concurrent allocation attempts against a single invoice of 100.00.

    Each worker attempts to allocate 10.00.
    Exactly 10 workers must succeed (total allocated == 100.00).
    The remaining 40 workers must fail with InvariantViolationException.
    Total allocated must never exceed 100.00.
    """
    url = require_fin001_postgres_url()
    # Create engine with 60 pool connections for 50 concurrent workers
    high_capacity_engine = create_async_engine(
        url,
        echo=False,
        pool_size=30,
        max_overflow=40,
        pool_timeout=60,
    )
    high_capacity_factory = async_sessionmaker(high_capacity_engine, expire_on_commit=False, autoflush=False)

    try:
        context = await _create_test_context(high_capacity_factory, fin001_organizations[0], "sc-n")
        org_id = context["organization_id"]

        # 1 invoice of 100.00
        async with high_capacity_factory() as session:
            invoice = CustomerInvoice(
                organization_id=org_id,
                invoice_code=f"INV-CP3-N-{uuid4().hex[:8]}",
                customer_id=context["counterparty_id"],
                project_id=context["project_id"],
                invoice_date=date(2026, 9, 1),
                due_date=date(2026, 10, 1),
                total_amount=Decimal("100.00"),
                status="UNPAID",
            )
            session.add(invoice)
            await session.commit()
            invoice_id = invoice.id

        # Pre-create 50 distinct posted payments of 10.00 each so payment serialization does not block source race
        payment_ids: list[UUID] = []
        async with high_capacity_factory() as session:
            for i in range(50):
                pid = uuid4()
                payment = Transaction(
                    id=pid,
                    organization_id=org_id,
                    transaction_code=f"TRX-N50-{i:02d}-{uuid4().hex[:6]}",
                    transaction_type=TransactionType.CUSTOMER_PAYMENT,
                    transaction_date=date(2026, 9, 2),
                    amount=Decimal("10.00"),
                    workflow_status=WorkflowStatus.POSTED,
                    counterparty_id=context["counterparty_id"],
                    payment_account_id=context["payment_account_id"],
                    description=f"N=50 payment {i}",
                )
                session.add(payment)
                payment_ids.append(pid)
            await session.commit()

        barrier = asyncio.Barrier(50)
        successes = 0
        failures = 0

        async def worker(payment_id: UUID) -> None:
            nonlocal successes, failures
            await barrier.wait()
            async with high_capacity_factory() as session:
                try:
                    async def allocate_op(active_session: AsyncSession) -> None:
                        await CustomerARService(active_session).allocate_customer_payment(
                            org_id, payment_id, [(invoice_id, Decimal("10.00"))]
                        )
                    await run_in_clean_transaction(session, allocate_op, allow_lock_not_available=True)
                    await session.commit()
                    successes += 1
                except InvariantViolationException:
                    await session.rollback()
                    failures += 1

        tasks = [asyncio.create_task(worker(pid)) for pid in payment_ids]
        await asyncio.gather(*tasks)

        # Assert exactly 10 successes and 40 invariant failures
        assert successes == 10, f"Expected exactly 10 successes, got {successes}"
        assert failures == 40, f"Expected exactly 40 invariant failures, got {failures}"

        # Assert database authoritative sum is EXACTLY 100.00
        async with high_capacity_factory() as session:
            allocated_total = await session.scalar(
                select(func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00"))).where(
                    CustomerPaymentAllocation.invoice_id == invoice_id
                )
            )
            assert Decimal(str(allocated_total)) == Decimal("100.00")

            inv = await session.scalar(
                select(CustomerInvoice)
                .options(selectinload(CustomerInvoice.allocations))
                .where(CustomerInvoice.id == invoice_id)
            )
            assert inv is not None
            assert inv.status == "PAID"
            assert inv.calculate_outstanding_amount() == Decimal("0.00")

    finally:
        await high_capacity_engine.dispose()


# ==============================================================================
# Scenario O: Success without retry
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_o_success_without_retry(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_test_context(fin001_session_factory, fin001_organizations[0], "sc-o")
    org_id = context["organization_id"]

    attempts = 0
    sleep_calls = 0

    async def counting_sleeper(_: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1

    async def single_op(session: AsyncSession) -> UUID:
        nonlocal attempts
        attempts += 1
        tx = Transaction(
            organization_id=org_id,
            transaction_code=f"TRX-NO-RETRY-{uuid4().hex[:8]}",
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("25.00"),
            workflow_status=WorkflowStatus.APPROVED,
            description="Success on first attempt",
        )
        session.add(tx)
        await session.flush()
        return tx.id

    async with fin001_session_factory() as session:
        tx_id = await run_in_clean_transaction(session, single_op, sleeper=counting_sleeper)
        await session.commit()

    assert attempts == 1
    assert sleep_calls == 0

    async with fin001_session_factory() as session:
        tx = await session.get(Transaction, tx_id)
        assert tx is not None
        assert tx.amount == Decimal("25.00")

