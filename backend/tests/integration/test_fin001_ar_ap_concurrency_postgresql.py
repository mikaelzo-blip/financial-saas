from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from src.api.auth import require_application_user
from src.core.database import get_db
from src.main import create_application
from src.models.audit import AuditLog
from src.models.coa import PaymentAccount
from src.models.counterparty import Counterparty
from src.models.journal import JournalEntry
from src.models.money_movement import MoneyMovement, Settlement
from src.models.enums import ProjectStatus, TransactionType, UserRole, WorkflowStatus
from src.models.organization import Organization
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.tenant_sequence import TenantSequence
from src.models.transaction import Transaction
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.payable_service import VendorAPService
from src.services.receivable_service import CustomerARService
from src.services.transaction_retry import run_in_clean_transaction

pytestmark = pytest.mark.postgresql


async def _create_context(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    *,
    label: str,
) -> dict[str, UUID]:
    async with session_factory() as session:
        organization = await session.get(Organization, organization_id)
        assert organization is not None
        await seed_standard_coa(session, organization.id)
        await seed_standard_payment_accounts(session, organization.id)
        counterparty = Counterparty(
            organization_id=organization.id,
            name=f"Counterparty {label}",
            is_customer=True,
            is_vendor=True,
        )
        session.add(counterparty)
        await session.flush()
        project = Project(
            organization_id=organization.id,
            project_code=f"PRJ-2026-{organization.id.hex[:3]}",
            project_name=f"FIN-001 Project {label}",
            customer_id=counterparty.id,
            original_contract_value=Decimal("1000.00"),
            revised_contract_value=Decimal("1000.00"),
            start_date=date(2026, 9, 1),
            project_status=ProjectStatus.ACTIVE,
        )
        user = User(
            organization_id=organization.id,
            email=f"fin001-{label}-{organization.id.hex[:8]}@example.test",
            full_name="FIN-001 Operator",
            password_hash="test-only",
            role=UserRole.OPERATOR,
        )
        session.add_all([counterparty, project, user])
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


async def _create_sources_and_payments(
    session_factory: async_sessionmaker[AsyncSession],
    context: dict[str, UUID],
) -> dict[str, UUID]:
    async with session_factory() as session:
        invoice = CustomerInvoice(
            organization_id=context["organization_id"],
            invoice_code=f"INV-FIN001-{uuid4().hex[:12]}",
            customer_id=context["counterparty_id"],
            project_id=context["project_id"],
            invoice_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("100.00"),
            status="UNPAID",
        )
        bill = VendorBill(
            organization_id=context["organization_id"],
            bill_code=f"BIL-FIN001-{uuid4().hex[:12]}",
            vendor_id=context["counterparty_id"],
            project_id=context["project_id"],
            bill_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("100.00"),
            status="UNPAID",
        )
        payments = [
            Transaction(
                organization_id=context["organization_id"],
                transaction_code=f"TRX-FIN001-{uuid4().hex[:12]}",
                transaction_type=transaction_type,
                transaction_date=date(2026, 9, 2),
                amount=Decimal("60.00"),
                workflow_status=WorkflowStatus.POSTED,
                counterparty_id=context["counterparty_id"],
                payment_account_id=context["payment_account_id"],
                description="FIN-001 direct allocation race payment",
            )
            for transaction_type in (
                TransactionType.CUSTOMER_PAYMENT,
                TransactionType.CUSTOMER_PAYMENT,
                TransactionType.PAY_VENDOR_BILL,
                TransactionType.PAY_VENDOR_BILL,
            )
        ]
        session.add_all([invoice, bill, *payments])
        await session.commit()
        return {
            "invoice_id": invoice.id,
            "bill_id": bill.id,
            "ar_payment_a": payments[0].id,
            "ar_payment_b": payments[1].id,
            "ap_payment_a": payments[2].id,
            "ap_payment_b": payments[3].id,
        }


async def _allocation_total(session_factory, allocation_model, source_column, source_id: UUID) -> Decimal:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(allocation_model.allocated_amount), Decimal("0.00"))).where(
                source_column == source_id
            )
        )
        return Decimal(str(total))


@pytest.mark.asyncio
@pytest.mark.xfail(
    raises=AssertionError,
    strict=True,
    reason="FIN-001 CP1 known defect: independent PostgreSQL transactions can over-allocate one invoice.",
)
async def test_ar_service_race_reproduces_overallocation_with_independent_postgresql_transactions(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = await _create_context(fin001_session_factory, fin001_organizations[0], label="ar-race")
    records = await _create_sources_and_payments(fin001_session_factory, context)
    source_read_barrier = asyncio.Barrier(2)
    original_get_invoice = CustomerARService.get_invoice

    async def synchronized_get_invoice(self, organization_id: UUID, invoice_id: UUID):
        invoice = await original_get_invoice(self, organization_id, invoice_id)
        if invoice_id == records["invoice_id"]:
            await source_read_barrier.wait()
        return invoice

    monkeypatch.setattr(CustomerARService, "get_invoice", synchronized_get_invoice)

    async def allocate(payment_id: UUID) -> None:
        async with fin001_session_factory() as session:
            await CustomerARService(session).allocate_customer_payment(
                context["organization_id"], payment_id, [(records["invoice_id"], Decimal("60.00"))]
            )
            await session.commit()

    await asyncio.gather(allocate(records["ar_payment_a"]), allocate(records["ar_payment_b"]))
    final_total = await _allocation_total(
        fin001_session_factory, CustomerPaymentAllocation, CustomerPaymentAllocation.invoice_id, records["invoice_id"]
    )
    assert final_total <= Decimal("100.00"), f"authoritative PostgreSQL total was {final_total}"


@pytest.mark.asyncio
@pytest.mark.xfail(
    raises=AssertionError,
    strict=True,
    reason="FIN-001 CP1 known defect: independent PostgreSQL transactions can over-allocate one vendor bill.",
)
async def test_ap_service_race_reproduces_overallocation_with_independent_postgresql_transactions(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = await _create_context(fin001_session_factory, fin001_organizations[0], label="ap-race")
    records = await _create_sources_and_payments(fin001_session_factory, context)
    source_read_barrier = asyncio.Barrier(2)
    original_get_bill = VendorAPService.get_bill

    async def synchronized_get_bill(self, organization_id: UUID, bill_id: UUID):
        bill = await original_get_bill(self, organization_id, bill_id)
        if bill_id == records["bill_id"]:
            await source_read_barrier.wait()
        return bill

    monkeypatch.setattr(VendorAPService, "get_bill", synchronized_get_bill)

    async def allocate(payment_id: UUID) -> None:
        async with fin001_session_factory() as session:
            await VendorAPService(session).allocate_vendor_payment(
                context["organization_id"], payment_id, [(records["bill_id"], Decimal("60.00"))]
            )
            await session.commit()

    await asyncio.gather(allocate(records["ap_payment_a"]), allocate(records["ap_payment_b"]))
    final_total = await _allocation_total(
        fin001_session_factory, VendorPaymentAllocation, VendorPaymentAllocation.bill_id, records["bill_id"]
    )
    assert final_total <= Decimal("100.00"), f"authoritative PostgreSQL total was {final_total}"


async def _real_endpoint_client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncClient:
    app: FastAPI = create_application()

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


async def _assert_endpoint_sequence_serialization(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    context: dict[str, UUID],
    path: str,
    source_field: str,
    source_id: UUID,
    allocation_class,
    allocation_method: str,
    expected_transaction_type: TransactionType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = getattr(allocation_class, allocation_method)
    first_arrived = asyncio.Event()
    release_first = asyncio.Event()
    entered = 0

    async def observed(self, *args, **kwargs):
        nonlocal entered
        entered += 1
        if entered == 1:
            first_arrived.set()
            await asyncio.wait_for(release_first.wait(), timeout=2)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(allocation_class, allocation_method, observed)
    headers = {"X-Organization-ID": str(context["organization_id"]), "X-User-ID": str(context["user_id"])}
    reference_no = f"FIN001-{uuid4().hex[:12]}"
    payload = {
        source_field: str(source_id),
        "payment_account_id": str(context["payment_account_id"]),
        "amount": "60.00",
        "payment_date": "2026-09-02",
        "reference_no": reference_no,
        "description": "FIN-001 endpoint sequence characterization",
    }
    async with await _real_endpoint_client(session_factory) as client:
        first = asyncio.create_task(client.post(path, headers=headers, json=payload))
        await asyncio.wait_for(first_arrived.wait(), timeout=2)
        second_reference_no = f"FIN001-{uuid4().hex[:12]}"
        second = asyncio.create_task(client.post(path, headers=headers, json={**payload, "reference_no": second_reference_no}))
        await asyncio.sleep(0.15)
        assert entered == 1, "second same-tenant endpoint request reached allocation before Feature-012 sequence serialized it"
        release_first.set()
        responses = await asyncio.gather(first, second)

    assert sorted(response.status_code for response in responses) == [201, 422]
    async with session_factory() as session:
        sequence = await session.scalar(
            select(TenantSequence).where(
                TenantSequence.organization_id == context["organization_id"],
                TenantSequence.namespace == "TRX",
                TenantSequence.scope_key == "2026",
            )
        )
        assert sequence is not None
        assert sequence.current_value == 1
        payment_ids = select(Transaction.id).where(
            Transaction.organization_id == context["organization_id"],
            Transaction.transaction_type == expected_transaction_type,
            Transaction.reference_no.in_((reference_no, second_reference_no)),
        )
        assert await session.scalar(select(func.count()).select_from(Transaction).where(
            Transaction.organization_id == context["organization_id"],
            Transaction.transaction_type == expected_transaction_type,
            Transaction.reference_no == reference_no,
        )) == 1
        assert await session.scalar(select(func.count()).select_from(JournalEntry).where(
            JournalEntry.transaction_id.in_(payment_ids)
        )) == 1
        assert await session.scalar(select(func.count()).select_from(Settlement).where(
            Settlement.transaction_id.in_(payment_ids)
        )) == 1
        settlement_movement_ids = select(Settlement.money_movement_id).where(
            Settlement.transaction_id.in_(payment_ids)
        )
        assert await session.scalar(select(func.count()).select_from(MoneyMovement).where(
            MoneyMovement.id.in_(settlement_movement_ids)
        )) == 1


@pytest.mark.asyncio
async def test_customer_payment_endpoint_characterizes_feature012_sequence_serialization(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = await _create_context(fin001_session_factory, fin001_organizations[0], label="customer-http")
    records = await _create_sources_and_payments(fin001_session_factory, context)
    await _assert_endpoint_sequence_serialization(
        session_factory=fin001_session_factory,
        context=context,
        path="/api/v1/customer-payments",
        source_field="invoice_id",
        source_id=records["invoice_id"],
        allocation_class=CustomerARService,
        allocation_method="allocate_customer_payment",
        expected_transaction_type=TransactionType.CUSTOMER_PAYMENT,
        monkeypatch=monkeypatch,
    )


@pytest.mark.asyncio
async def test_vendor_payment_endpoint_characterizes_feature012_sequence_serialization(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = await _create_context(fin001_session_factory, fin001_organizations[0], label="vendor-http")
    records = await _create_sources_and_payments(fin001_session_factory, context)
    await _assert_endpoint_sequence_serialization(
        session_factory=fin001_session_factory,
        context=context,
        path="/api/v1/vendor-payments",
        source_field="bill_id",
        source_id=records["bill_id"],
        allocation_class=VendorAPService,
        allocation_method="allocate_vendor_payment",
        expected_transaction_type=TransactionType.PAY_VENDOR_BILL,
        monkeypatch=monkeypatch,
    )


@pytest.mark.asyncio
async def test_tenant_isolation_and_identity_map_aggregate_characterization(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context_a = await _create_context(fin001_session_factory, fin001_organizations[0], label="tenant-a")
    context_b = await _create_context(fin001_session_factory, fin001_organizations[1], label="tenant-b")
    records_a = await _create_sources_and_payments(fin001_session_factory, context_a)

    async with fin001_session_factory() as session:
        with pytest.raises(Exception):
            await CustomerARService(session).allocate_customer_payment(
                context_b["organization_id"], records_a["ar_payment_a"], [(records_a["invoice_id"], Decimal("60.00"))]
            )

    async with fin001_session_factory() as stale_session:
        invoice = await stale_session.scalar(
            select(CustomerInvoice).options(selectinload(CustomerInvoice.allocations)).where(CustomerInvoice.id == records_a["invoice_id"])
        )
        assert invoice is not None and invoice.calculate_paid_amount() == Decimal("0.00")
        async with fin001_session_factory() as writer:
            await CustomerARService(writer).allocate_customer_payment(
                context_a["organization_id"], records_a["ar_payment_a"], [(records_a["invoice_id"], Decimal("60.00"))]
            )
            await writer.commit()
        assert invoice.calculate_paid_amount() == Decimal("0.00")
        sql_total = await stale_session.scalar(
            select(func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00"))).where(
                CustomerPaymentAllocation.invoice_id == records_a["invoice_id"]
            )
        )
        assert Decimal(str(sql_total)) == Decimal("60.00")


@pytest.mark.asyncio
async def test_current_multi_source_input_order_characterizes_cp2_canonical_lock_requirement(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_context(fin001_session_factory, fin001_organizations[0], label="source-order")
    records = await _create_sources_and_payments(fin001_session_factory, context)
    async with fin001_session_factory() as session:
        second_invoice = CustomerInvoice(
            organization_id=context["organization_id"],
            invoice_code=f"INV-FIN001-{uuid4().hex[:12]}",
            customer_id=context["counterparty_id"],
            project_id=context["project_id"],
            invoice_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("100.00"),
            status="UNPAID",
        )
        session.add(second_invoice)
        await session.commit()
        reversed_sources = [(second_invoice.id, Decimal("30.00")), (records["invoice_id"], Decimal("30.00"))]
        allocations = await CustomerARService(session).allocate_customer_payment(
            context["organization_id"], records["ar_payment_a"], reversed_sources
        )
        assert [allocation.invoice_id for allocation in allocations] == [source_id for source_id, _ in reversed_sources]
        await session.rollback()


@pytest.mark.asyncio
async def test_transaction_ownership_characterizes_clean_retry_and_request_side_effect_boundary(
    fin001_session_factory: async_sessionmaker[AsyncSession],
    fin001_organizations: tuple[UUID, UUID],
) -> None:
    context = await _create_context(fin001_session_factory, fin001_organizations[0], label="ownership")
    records = await _create_sources_and_payments(fin001_session_factory, context)
    async with fin001_session_factory() as session:
        result = await run_in_clean_transaction(session, lambda active: CustomerARService(active).allocate_customer_payment(
            context["organization_id"],
            records["ar_payment_a"],
            [(records["invoice_id"], Decimal("60.00"))],
        ))
        assert len(result) == 1
        assert await session.scalar(
            select(func.count()).select_from(CustomerPaymentAllocation).where(
                CustomerPaymentAllocation.payment_transaction_id == records["ar_payment_a"]
            )
        ) == 1
        await session.rollback()
    assert await _allocation_total(
        fin001_session_factory, CustomerPaymentAllocation, CustomerPaymentAllocation.invoice_id, records["invoice_id"]
    ) == Decimal("0.00")
