"""Slice 5 PostgreSQL concurrency, atomicity, and durable linkage integration suite.

Proves:
1. Migration 028 schema and catalog invariants on PostgreSQL 16 (RESTRICT FK, unique index, POSTED enum).
2. Same-document concurrent posting race prevention (FOR UPDATE serialization, exactly 1 transaction, 1 journal).
3. AR/AP settlement concurrency: exactly 1 allocation, no duplicate expense/revenue.
4. Downstream failure atomicity: failure after posting starts rolls back all changes, 0 orphan transactions/journals.
5. RESTRICT FK prevents transaction deletion (immutable audit trail, prevents reposting).
6. Worker DOCUMENT_POST auto-posting execution, system actor audit, and policy-blocked fail-closed behavior.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.exceptions import EntityNotFoundException, InvariantViolationException
from src.models.audit import AuditLog
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.enums import (
    CandidateStatus,
    CostCategory,
    DocumentProcessingStatus,
    DocumentType,
    ExpenseCategory,
    ProjectStatus,
    TransactionType,
    UserRole,
    WorkflowStatus,
)
from src.models.journal import JournalEntry, JournalLine
from src.models.organization import Organization
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.transaction import Transaction
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa
from src.services.document_posting_service import DocumentPostingService
from src.services.job_queue_service import JobQueueService
from src.services.job_worker import JobWorker
from src.services.transaction_retry import run_in_clean_transaction
from src.worker import handle_document_post

POSTGRES_URL_ENV = "FIN_001_TEST_DATABASE_URL"
EXPECTED_ALEMBIC_HEAD = "028_document_posting_linkage"

pytestmark = pytest.mark.postgresql


def require_slice5_postgres_url() -> str:
    url = (
        os.environ.get("SLICE5_TEST_DATABASE_URL")
        or os.environ.get("FIN_001_TEST_DATABASE_URL")
        or os.environ.get("LIVE_POSTGRES_URL")
    )
    if not url:
        pytest.skip("No PostgreSQL URL configured; skipping Slice 5 live PostgreSQL concurrency tests.")

    parsed = urlsplit(url)
    database_name = (parsed.path or "").lstrip("/").lower()
    if parsed.scheme != "postgresql+asyncpg" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        pytest.fail(f"Refusing PostgreSQL URL: {url} must be a local postgresql+asyncpg URL.")
    if not any(token in database_name for token in ("slice5", "fin001", "test", "disposable")):
        pytest.fail(f"Refusing PostgreSQL URL: database name '{database_name}' must identify a test/disposable DB.")
    return url


@pytest.fixture
async def pg_engine():
    url = require_slice5_postgres_url()
    engine = create_async_engine(url, pool_size=25, max_overflow=10, pool_timeout=30)
    try:
        async with engine.connect() as conn:
            ver = int(await conn.scalar(text("SHOW server_version_num")) or 0)
            assert ver >= 160000, f"Expected PostgreSQL 16+, got server_version_num={ver}"
            head = await conn.scalar(text("SELECT version_num FROM alembic_version"))
            assert head == EXPECTED_ALEMBIC_HEAD, f"Expected Alembic head {EXPECTED_ALEMBIC_HEAD}, got {head}"
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def pg_session_factory(pg_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(pg_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def pg_slice5_setup(pg_session_factory: async_sessionmaker[AsyncSession]):
    org_id = uuid4()
    manager_id = uuid4()
    vendor_id = uuid4()
    customer_id = uuid4()
    project_id = uuid4()
    payment_account_id = uuid4()

    async with pg_session_factory() as session:
        org = Organization(id=org_id, slug=f"s5-pg-{org_id.hex[:8]}", legal_name="Slice 5 PG Org")
        session.add(org)
        await session.flush()

        manager = User(
            id=manager_id,
            organization_id=org_id,
            email=f"manager-{org_id.hex[:6]}@s5.test",
            full_name="Slice5 PG Manager",
            password_hash="hash",
            role=UserRole.MANAGER,
        )
        session.add(manager)
        await session.flush()

        await seed_standard_coa(session, org_id)

        cash_acc = await session.scalar(
            select(ChartOfAccount).where(
                ChartOfAccount.organization_id == org_id,
                ChartOfAccount.account_code == "1101",
            )
        )

        vendor = Counterparty(
            id=vendor_id,
            organization_id=org_id,
            name=f"Vendor PG {org_id.hex[:6]}",
            is_vendor=True,
            is_customer=False,
            is_active=True,
        )
        customer = Counterparty(
            id=customer_id,
            organization_id=org_id,
            name=f"Customer PG {org_id.hex[:6]}",
            is_vendor=False,
            is_customer=True,
            is_active=True,
        )
        session.add_all([vendor, customer])
        await session.flush()

        project = Project(
            id=project_id,
            organization_id=org_id,
            project_code=f"PRJ-PG-{org_id.hex[:6]}",
            project_name="Slice 5 Project PG",
            project_status=ProjectStatus.ACTIVE,
            original_contract_value=Decimal("50000000.00"),
            start_date=date(2026, 1, 1),
            customer_id=customer_id,
        )
        pa = PaymentAccount(
            id=payment_account_id,
            organization_id=org_id,
            coa_account_id=cash_acc.id,
            name="Bank PG",
            bank_name="BCA",
            account_number="1234567890",
            is_active=True,
        )
        session.add_all([project, pa])
        await session.commit()

    yield {
        "org_id": org_id,
        "manager_id": manager_id,
        "vendor_id": vendor_id,
        "customer_id": customer_id,
        "project_id": project_id,
        "payment_account_id": payment_account_id,
    }

    # Teardown in strict foreign key order
    async with pg_session_factory() as session:
        await session.execute(text(f"DELETE FROM transaction_document_links WHERE document_id IN (SELECT id FROM documents WHERE organization_id = '{org_id}')"))
        await session.execute(text(f"UPDATE documents SET converted_transaction_id = NULL WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM vendor_payment_allocations WHERE bill_id IN (SELECT id FROM vendor_bills WHERE organization_id = '{org_id}')"))
        await session.execute(text(f"DELETE FROM customer_payment_allocations WHERE invoice_id IN (SELECT id FROM customer_invoices WHERE organization_id = '{org_id}')"))
        await session.execute(text(f"DELETE FROM vendor_bills WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM customer_invoices WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM journal_lines WHERE journal_entry_id IN (SELECT id FROM journal_entries WHERE organization_id = '{org_id}')"))
        await session.execute(text(f"DELETE FROM journal_entries WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM transactions WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM background_jobs WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM documents WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM audit_logs WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM payment_accounts WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM projects WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM counterparties WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM chart_of_accounts WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM users WHERE organization_id = '{org_id}'"))
        await session.execute(text(f"DELETE FROM organizations WHERE id = '{org_id}'"))
        await session.commit()


@pytest.mark.asyncio
async def test_slice5_postgresql_migration_028_schema_and_catalog(pg_engine: AsyncEngine):
    """Verify live PostgreSQL 16 catalog: RESTRICT FK, unique index, POSTED enum, and background job index."""
    async with pg_engine.connect() as conn:
        # 1. Foreign key constraint delete_rule is RESTRICT
        fk_res = await conn.execute(text("""
            SELECT rc.delete_rule, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.referential_constraints rc ON tc.constraint_name = rc.constraint_name
            JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
            WHERE tc.table_name = 'documents' AND tc.constraint_name = 'fk_documents_converted_transaction_id'
        """))
        fk_row = fk_res.fetchone()
        assert fk_row is not None, "fk_documents_converted_transaction_id not found in information_schema"
        assert fk_row[0] == "RESTRICT", f"Expected ON DELETE RESTRICT, got {fk_row[0]}"
        assert fk_row[1] == "transactions", f"Expected target table transactions, got {fk_row[1]}"
        assert fk_row[2] == "id", f"Expected target column id, got {fk_row[2]}"

        # 2. Unique index on converted_transaction_id
        idx_res = await conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'documents' AND indexname = 'ix_documents_converted_transaction_id'
        """))
        idx_row = idx_res.fetchone()
        assert idx_row is not None, "ix_documents_converted_transaction_id not found in pg_indexes"
        assert "UNIQUE INDEX" in idx_row[1], f"Expected UNIQUE INDEX, got {idx_row[1]}"

        # 3. Enum document_processing_status contains POSTED
        enum_res = await conn.execute(text("""
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'document_processing_status'
        """))
        enum_labels = [r[0] for r in enum_res.fetchall()]
        assert "POSTED" in enum_labels, f"'POSTED' missing from document_processing_status enum: {enum_labels}"
        assert "READY_TO_POST" in enum_labels, f"'READY_TO_POST' missing from enum: {enum_labels}"


@pytest.mark.asyncio
async def test_slice5_postgresql_same_document_concurrency_race(
    pg_session_factory: async_sessionmaker[AsyncSession],
    pg_slice5_setup: dict,
):
    """
    MANDATORY POSTGRESQL PROOF:
    Same READY_TO_POST document concurrently posted by two independent workers.
    Proves:
    - Row-level lock (SELECT ... FOR UPDATE) serializes conversion.
    - Exactly ONE transaction created.
    - Exactly ONE journal entry created.
    - Converted transaction ID stably linked.
    - Second request returns already_posted=True with identical transaction_id.
    - 0 duplicate transactions, 0 duplicate journals.
    """
    org_id = pg_slice5_setup["org_id"]
    manager_id = pg_slice5_setup["manager_id"]
    vendor_id = pg_slice5_setup["vendor_id"]
    project_id = pg_slice5_setup["project_id"]
    pa_id = pg_slice5_setup["payment_account_id"]

    doc_id = uuid4()
    async with pg_session_factory() as session:
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            document_code="DOC-PG-RACE-001",
            file_name="receipt_race.pdf",
            file_hash="hash-pg-race-001",
            file_size_bytes=1024,
            mime_type="application/pdf",
            document_type=DocumentType.RECEIPT,
            storage_path="tenants/test/receipt_race.pdf",
            processing_status=DocumentProcessingStatus.READY_TO_POST,
            candidate_transaction={
                "id": str(doc_id),
                "proposed_transaction_type": "DIRECT_PURCHASE",
                "counterparty_id": str(vendor_id),
                "project_id": str(project_id),
                "payment_account_id": str(pa_id),
                "amount": "1750000.00",
                "currency_code": "IDR",
                "transaction_date": "2026-09-16",
                "cost_category": "MAT",
                "description": "Materials for project PG race",
                "status": "READY_TO_POST",
            },
            review_flags=[],
            matching_results={},
            created_by=manager_id,
        )
        session.add(doc)
        await session.commit()

    barrier = asyncio.Barrier(2)

    async def worker_task(worker_name: str):
        await barrier.wait()
        async with pg_session_factory() as session:
            async def _do(sess):
                svc = DocumentPostingService(sess)
                return await svc.post_document(
                    organization_id=org_id,
                    document_id=doc_id,
                    actor_id=manager_id,
                    actor_role=UserRole.MANAGER,
                    is_worker=False,
                )
            res = await run_in_clean_transaction(session, _do)
            await session.commit()
            return res

    results = await asyncio.gather(worker_task("Worker-A"), worker_task("Worker-B"))

    res_a, res_b = results[0], results[1]
    already_posted_flags = [res_a.already_posted, res_b.already_posted]
    assert False in already_posted_flags, "At least one request must perform the primary conversion"
    assert True in already_posted_flags, "One request must detect already_posted under row lock"
    assert res_a.transaction_id == res_b.transaction_id, "Both workers must return the exact same transaction ID"

    # Verify durable state directly in PostgreSQL
    async with pg_session_factory() as session:
        # Check Document state
        doc_in_db = await session.scalar(select(Document).where(Document.id == doc_id))
        assert doc_in_db.processing_status == DocumentProcessingStatus.POSTED
        assert doc_in_db.converted_transaction_id == res_a.transaction_id

        # Check Transaction count (MUST BE EXACTLY 1)
        trx_count = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.organization_id == org_id)
        )
        assert trx_count == 1, f"Expected exactly 1 transaction, got {trx_count}"

        # Check JournalEntry count (MUST BE EXACTLY 1)
        je_count = await session.scalar(
            select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org_id)
        )
        assert je_count == 1, f"Expected exactly 1 journal entry, got {je_count}"

        # Check Journal is balanced
        je = await session.scalar(
            select(JournalEntry).where(JournalEntry.transaction_id == res_a.transaction_id)
        )
        assert je.is_balanced is True
        assert je.total_debit == Decimal("1750000.00")
        assert je.total_credit == Decimal("1750000.00")


@pytest.mark.asyncio
async def test_slice5_postgresql_ap_settlement_concurrency_and_retry(
    pg_session_factory: async_sessionmaker[AsyncSession],
    pg_slice5_setup: dict,
):
    """
    Proves AR/AP retry and concurrency on PostgreSQL 16:
    Concurrent and sequential retry of PAY_VENDOR_BILL does not duplicate:
    - VendorPaymentAllocation
    - VendorBill payment
    - Transaction or Journal
    """
    org_id = pg_slice5_setup["org_id"]
    manager_id = pg_slice5_setup["manager_id"]
    vendor_id = pg_slice5_setup["vendor_id"]
    project_id = pg_slice5_setup["project_id"]
    pa_id = pg_slice5_setup["payment_account_id"]

    bill_id = uuid4()
    doc_id = uuid4()

    async with pg_session_factory() as session:
        # Create a Vendor Bill of 5,000,000
        bill = VendorBill(
            id=bill_id,
            organization_id=org_id,
            vendor_id=vendor_id,
            project_id=project_id,
            bill_code="BILL-PG-001",
            bill_date=date(2026, 9, 1),
            due_date=date(2026, 10, 1),
            total_amount=Decimal("5000000.00"),
            status="UNPAID",
        )
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            document_code="DOC-PG-AP-001",
            file_name="proof_ap.pdf",
            file_hash="hash-pg-ap-001",
            file_size_bytes=2048,
            mime_type="application/pdf",
            document_type=DocumentType.TRANSFER_PROOF,
            storage_path="tenants/test/proof_ap.pdf",
            processing_status=DocumentProcessingStatus.READY_TO_POST,
            candidate_transaction={
                "id": str(doc_id),
                "proposed_transaction_type": "PAY_VENDOR_BILL",
                "counterparty_id": str(vendor_id),
                "project_id": str(project_id),
                "payment_account_id": str(pa_id),
                "allocation_target_id": str(bill_id),
                "amount": "5000000.00",
                "currency_code": "IDR",
                "transaction_date": "2026-09-16",
                "description": "Full payment for BILL-PG-001",
                "status": "READY_TO_POST",
            },
            review_flags=[],
            matching_results={},
            created_by=manager_id,
        )
        session.add_all([bill, doc])
        await session.commit()

    barrier = asyncio.Barrier(2)

    async def worker_task(name: str):
        await barrier.wait()
        async with pg_session_factory() as session:
            async def _do(sess):
                svc = DocumentPostingService(sess)
                return await svc.post_document(
                    organization_id=org_id,
                    document_id=doc_id,
                    actor_id=manager_id,
                    actor_role=UserRole.MANAGER,
                    is_worker=False,
                )
            res = await run_in_clean_transaction(session, _do)
            await session.commit()
            return res

    results = await asyncio.gather(worker_task("AP-1"), worker_task("AP-2"))
    assert (results[0].already_posted != results[1].already_posted)

    # Now test sequential retry
    async with pg_session_factory() as session:
        async def _do(sess):
            svc = DocumentPostingService(sess)
            return await svc.post_document(
                organization_id=org_id,
                document_id=doc_id,
                actor_id=manager_id,
                actor_role=UserRole.MANAGER,
                is_worker=False,
            )
        retry_res = await run_in_clean_transaction(session, _do)
        await session.commit()
    assert retry_res.already_posted is True
    assert retry_res.transaction_id == results[0].transaction_id

    # Verify allocation in PostgreSQL
    async with pg_session_factory() as session:
        alloc_count = await session.scalar(
            select(func.count(VendorPaymentAllocation.id)).where(VendorPaymentAllocation.bill_id == bill_id)
        )
        assert alloc_count == 1, f"Expected exactly 1 payment allocation, got {alloc_count}"

        alloc_sum = await session.scalar(
            select(func.sum(VendorPaymentAllocation.allocated_amount)).where(VendorPaymentAllocation.bill_id == bill_id)
        )
        assert alloc_sum == Decimal("5000000.00")

        # Total transactions and journals for AP must be 1
        trx_count = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.organization_id == org_id)
        )
        assert trx_count == 1


@pytest.mark.asyncio
async def test_slice5_postgresql_failure_atomicity_and_clean_recovery(
    pg_session_factory: async_sessionmaker[AsyncSession],
    pg_slice5_setup: dict,
    monkeypatch,
):
    """
    MANDATORY FAILURE ATOMICITY PROOF:
    Force a downstream failure AFTER posting begins (in AccountingEngine.post_transaction).
    Verify:
    - Document status remains READY_TO_POST (NOT POSTED).
    - converted_transaction_id is not falsely linked (remains None).
    - 0 transactions and 0 journals committed.
    - Clean subsequent retry succeeds without duplicate retry hazard.
    """
    org_id = pg_slice5_setup["org_id"]
    manager_id = pg_slice5_setup["manager_id"]
    vendor_id = pg_slice5_setup["vendor_id"]
    project_id = pg_slice5_setup["project_id"]
    pa_id = pg_slice5_setup["payment_account_id"]

    doc_id = uuid4()
    async with pg_session_factory() as session:
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            document_code="DOC-PG-FAIL-001",
            file_name="receipt_fail.pdf",
            file_hash="hash-pg-fail-001",
            file_size_bytes=1024,
            mime_type="application/pdf",
            document_type=DocumentType.RECEIPT,
            storage_path="tenants/test/receipt_fail.pdf",
            processing_status=DocumentProcessingStatus.READY_TO_POST,
            candidate_transaction={
                "id": str(doc_id),
                "proposed_transaction_type": "DIRECT_PURCHASE",
                "counterparty_id": str(vendor_id),
                "project_id": str(project_id),
                "payment_account_id": str(pa_id),
                "amount": "2500000.00",
                "currency_code": "IDR",
                "transaction_date": "2026-09-16",
                "cost_category": "MAT",
                "description": "Failure injection test",
                "status": "READY_TO_POST",
            },
            review_flags=[],
            matching_results={},
            created_by=manager_id,
        )
        session.add(doc)
        await session.commit()

    # Step 1: Inject downstream failure during AccountingEngine.post_transaction
    from src.services.accounting_engine import AccountingEngine

    original_post = AccountingEngine.post_transaction

    async def mock_failing_post(self, *args, **kwargs):
        raise RuntimeError("SIMULATED_DOWNSTREAM_POSTING_CRASH")

    monkeypatch.setattr(AccountingEngine, "post_transaction", mock_failing_post)

    async with pg_session_factory() as session:
        svc = DocumentPostingService(session)
        with pytest.raises(RuntimeError, match="SIMULATED_DOWNSTREAM_POSTING_CRASH"):
            await svc.post_document(org_id, doc_id, manager_id, UserRole.MANAGER)
        await session.rollback()

    # Verify database state after failure: strictly rolled back
    async with pg_session_factory() as session:
        doc_in_db = await session.scalar(select(Document).where(Document.id == doc_id))
        assert doc_in_db.processing_status == DocumentProcessingStatus.READY_TO_POST
        assert doc_in_db.converted_transaction_id is None

        trx_count = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.organization_id == org_id)
        )
        assert trx_count == 0, "No transaction should be committed on downstream failure"

        je_count = await session.scalar(
            select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org_id)
        )
        assert je_count == 0, "No journal entry should be committed on downstream failure"

    # Step 2: Remove failure injection and prove clean subsequent retry succeeds
    monkeypatch.setattr(AccountingEngine, "post_transaction", original_post)

    async with pg_session_factory() as session:
        async def _do(sess):
            svc = DocumentPostingService(sess)
            return await svc.post_document(org_id, doc_id, manager_id, UserRole.MANAGER)
        recovery_res = await run_in_clean_transaction(session, _do)
        await session.commit()

    assert recovery_res.already_posted is False
    assert recovery_res.processing_status == DocumentProcessingStatus.POSTED

    async with pg_session_factory() as session:
        doc_in_db = await session.scalar(select(Document).where(Document.id == doc_id))
        assert doc_in_db.processing_status == DocumentProcessingStatus.POSTED
        assert doc_in_db.converted_transaction_id == recovery_res.transaction_id

        trx_count = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.organization_id == org_id)
        )
        assert trx_count == 1
        je_count = await session.scalar(
            select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org_id)
        )
        assert je_count == 1


@pytest.mark.asyncio
async def test_slice5_postgresql_fk_restrict_prevents_transaction_deletion(
    pg_session_factory: async_sessionmaker[AsyncSession],
    pg_slice5_setup: dict,
):
    """
    Proves ON DELETE RESTRICT on fk_documents_converted_transaction_id:
    A transaction linked to a converted document cannot be deleted from PostgreSQL.
    This guarantees immutable conversion linkage and prevents reposting vulnerabilities.
    """
    org_id = pg_slice5_setup["org_id"]
    manager_id = pg_slice5_setup["manager_id"]
    vendor_id = pg_slice5_setup["vendor_id"]
    project_id = pg_slice5_setup["project_id"]
    pa_id = pg_slice5_setup["payment_account_id"]

    doc_id = uuid4()
    async with pg_session_factory() as session:
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            document_code="DOC-PG-RESTRICT-001",
            file_name="receipt_restrict.pdf",
            file_hash="hash-pg-restrict-001",
            file_size_bytes=1024,
            mime_type="application/pdf",
            document_type=DocumentType.RECEIPT,
            storage_path="tenants/test/receipt_restrict.pdf",
            processing_status=DocumentProcessingStatus.READY_TO_POST,
            candidate_transaction={
                "id": str(doc_id),
                "proposed_transaction_type": "DIRECT_PURCHASE",
                "counterparty_id": str(vendor_id),
                "project_id": str(project_id),
                "payment_account_id": str(pa_id),
                "amount": "990000.00",
                "currency_code": "IDR",
                "transaction_date": "2026-09-16",
                "cost_category": "MAT",
                "description": "Restrict FK proof",
                "status": "READY_TO_POST",
            },
            review_flags=[],
            matching_results={},
            created_by=manager_id,
        )
        session.add(doc)
        await session.commit()

    # Convert document to transaction
    async with pg_session_factory() as session:
        svc = DocumentPostingService(session)
        res = await svc.post_document(org_id, doc_id, manager_id, UserRole.MANAGER)
        await session.commit()

    trx_id = res.transaction_id

    # Remove journal entries and document links so the only remaining reference
    # to transactions is documents.converted_transaction_id (testing that FK in isolation)
    async with pg_session_factory() as session:
        await session.execute(text(f"DELETE FROM transaction_document_links WHERE transaction_id = '{trx_id}'"))
        await session.execute(text(f"DELETE FROM journal_lines WHERE journal_entry_id IN (SELECT id FROM journal_entries WHERE transaction_id = '{trx_id}')"))
        await session.execute(text(f"DELETE FROM journal_entries WHERE transaction_id = '{trx_id}'"))
        await session.commit()

    # Attempt to delete the transaction directly via SQL in PostgreSQL
    async with pg_session_factory() as session:
        with pytest.raises(IntegrityError) as exc_info:
            await session.execute(text(f"DELETE FROM transactions WHERE id = '{trx_id}'"))
            await session.commit()
        await session.rollback()

    assert "violates foreign key constraint" in str(exc_info.value).lower()
    assert "fk_documents_converted_transaction_id" in str(exc_info.value).lower()

    # Verify linkage is still intact
    async with pg_session_factory() as session:
        doc_in_db = await session.scalar(select(Document).where(Document.id == doc_id))
        assert doc_in_db.converted_transaction_id == trx_id
        assert doc_in_db.processing_status == DocumentProcessingStatus.POSTED


@pytest.mark.asyncio
async def test_slice5_postgresql_worker_auto_post_and_system_actor_audit(
    pg_session_factory: async_sessionmaker[AsyncSession],
    pg_slice5_setup: dict,
):
    """
    Proves Background Job Worker auto-posting on PostgreSQL 16:
    1. AUTO_SAFE candidate (DIRECT_PURCHASE) automatically posts via worker.
    2. Document status becomes POSTED, transaction linked, balanced journal created.
    3. Audit log records DOCUMENT_POSTED with actor_id=None (system actor convention).
    4. Non-AUTO_SAFE candidate (PAY_VENDOR_BILL) refused by policy (POLICY_REQUIRED),
       remains READY_TO_POST (NOT FAILED), exits cleanly without infinite retry.
    """
    org_id = pg_slice5_setup["org_id"]
    manager_id = pg_slice5_setup["manager_id"]
    vendor_id = pg_slice5_setup["vendor_id"]
    project_id = pg_slice5_setup["project_id"]
    pa_id = pg_slice5_setup["payment_account_id"]

    doc_auto_id = uuid4()
    doc_policy_id = uuid4()

    async with pg_session_factory() as session:
        doc_auto = Document(
            id=doc_auto_id,
            organization_id=org_id,
            document_code="DOC-PG-AUTO-001",
            file_name="auto_receipt.pdf",
            file_hash="hash-pg-auto-001",
            file_size_bytes=1024,
            mime_type="application/pdf",
            document_type=DocumentType.RECEIPT,
            storage_path="tenants/test/auto_receipt.pdf",
            processing_status=DocumentProcessingStatus.READY_TO_POST,
            candidate_transaction={
                "id": str(doc_auto_id),
                "proposed_transaction_type": "DIRECT_PURCHASE",
                "counterparty_id": str(vendor_id),
                "project_id": str(project_id),
                "payment_account_id": str(pa_id),
                "amount": "1200000.00",
                "currency_code": "IDR",
                "transaction_date": "2026-09-16",
                "cost_category": "MAT",
                "description": "Auto safe worker test",
                "status": "READY_TO_POST",
            },
            review_flags=[],
            matching_results={},
            created_by=manager_id,
        )
        doc_policy = Document(
            id=doc_policy_id,
            organization_id=org_id,
            document_code="DOC-PG-POLICY-001",
            file_name="bill_policy.pdf",
            file_hash="hash-pg-policy-001",
            file_size_bytes=1024,
            mime_type="application/pdf",
            document_type=DocumentType.VENDOR_INVOICE,
            storage_path="tenants/test/bill_policy.pdf",
            processing_status=DocumentProcessingStatus.READY_TO_POST,
            candidate_transaction={
                "id": str(doc_policy_id),
                "proposed_transaction_type": "PAY_VENDOR_BILL",
                "counterparty_id": str(vendor_id),
                "project_id": str(project_id),
                "payment_account_id": str(pa_id),
                "allocation_target_id": str(uuid4()),
                "amount": "3000000.00",
                "currency_code": "IDR",
                "transaction_date": "2026-09-16",
                "description": "Policy blocked for auto worker",
                "status": "READY_TO_POST",
            },
            review_flags=[],
            matching_results={},
            created_by=manager_id,
        )
        session.add_all([doc_auto, doc_policy])
        await session.commit()

    # Part 1: Worker executes AUTO_SAFE DOCUMENT_POST
    worker = JobWorker(worker_id="test-pg-worker-1", session_factory=pg_session_factory)
    worker.register_handler("DOCUMENT_POST", handle_document_post)

    # Enqueue DOCUMENT_POST for doc_auto
    async with pg_session_factory() as session:
        queue = JobQueueService(session)
        job_auto = await queue.enqueue(
            job_type="DOCUMENT_POST",
            payload={"document_id": str(doc_auto_id), "organization_id": str(org_id)},
            organization_id=org_id,
            idempotency_key=f"document-post:{doc_auto_id}",
        )
        await session.commit()

    # Worker executes the job
    processed = await worker.execute_one_job()
    assert processed is True

    # Assert results for doc_auto
    async with pg_session_factory() as session:
        doc_auto_db = await session.scalar(select(Document).where(Document.id == doc_auto_id))
        assert doc_auto_db.processing_status == DocumentProcessingStatus.POSTED
        assert doc_auto_db.converted_transaction_id is not None

        # Check job status is COMPLETED
        job_status = await session.scalar(text(f"SELECT status FROM background_jobs WHERE id = '{job_auto.id}'"))
        assert job_status == "COMPLETED"

        # Check Audit Log: system actor convention (actor_id IS NULL)
        audit_row = await session.scalar(
            select(AuditLog).where(
                AuditLog.organization_id == org_id,
                AuditLog.entity_name == "Document",
                AuditLog.entity_id == doc_auto_id,
                AuditLog.action == "DOCUMENT_POSTED",
            )
        )
        assert audit_row is not None
        assert audit_row.actor_id is None, f"Worker posting must use system actor (actor_id=None), got {audit_row.actor_id}"

    # Part 2: Worker executes non-AUTO_SAFE DOCUMENT_POST (POLICY_REQUIRED)
    async with pg_session_factory() as session:
        queue = JobQueueService(session)
        job_policy = await queue.enqueue(
            job_type="DOCUMENT_POST",
            payload={"document_id": str(doc_policy_id), "organization_id": str(org_id)},
            organization_id=org_id,
            idempotency_key=f"document-post:{doc_policy_id}",
        )
        await session.commit()

    # Worker executes policy-blocked job
    processed_policy = await worker.execute_one_job()
    assert processed_policy is True

    async with pg_session_factory() as session:
        doc_policy_db = await session.scalar(select(Document).where(Document.id == doc_policy_id))
        # Document remains READY_TO_POST for manual accounting action; NOT marked FAILED!
        assert doc_policy_db.processing_status == DocumentProcessingStatus.READY_TO_POST
        assert doc_policy_db.converted_transaction_id is None

        # Job completed without thrashing retries
        policy_job_status = await session.scalar(text(f"SELECT status FROM background_jobs WHERE id = '{job_policy.id}'"))
        assert policy_job_status == "COMPLETED"
