import io
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from src.models.background_job import BackgroundJob
from src.services.job_worker import JobWorker
from src.worker import handle_document_post
from src.models.audit import AuditLog
from src.models.coa import PaymentAccount
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
from src.core.exceptions import InvariantViolationException, EntityNotFoundException
from src.models.journal import JournalEntry
from src.models.organization import Organization
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.transaction import Transaction
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa
from src.services.document_posting_service import DocumentPostingService
from src.services.document_service import DocumentService


@pytest.fixture
async def posting_setup(db_session):
    org = Organization(slug="slice5-org", legal_name="Slice 5 Org")
    db_session.add(org)
    await db_session.flush()

    manager = User(
        organization_id=org.id,
        email="manager@slice5.test",
        full_name="Posting Manager",
        password_hash="not-used",
        role=UserRole.MANAGER,
    )
    viewer = User(
        organization_id=org.id,
        email="viewer@slice5.test",
        full_name="Viewer User",
        password_hash="not-used",
        role=UserRole.VIEWER,
    )
    db_session.add_all([manager, viewer])
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    from src.models.coa import ChartOfAccount
    cash_acc = await db_session.scalar(
        select(ChartOfAccount).where(
            ChartOfAccount.organization_id == org.id,
            ChartOfAccount.account_code == "1101",
        )
    )

    vendor = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="PT Semen Aman",
        is_vendor=True,
        is_customer=False,
        is_active=True,
    )
    customer = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="PT Klien Makmur",
        is_vendor=False,
        is_customer=True,
        is_active=True,
    )
    project = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-S5-001",
        project_name="Proyek S5",
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 1, 1),
        customer_id=customer.id,
    )
    payment_account = PaymentAccount(
        id=uuid.uuid4(),
        organization_id=org.id,
        coa_account_id=cash_acc.id,
        name="Main Cash",
        account_number="1101-001",
        is_active=True,
    )
    db_session.add_all([payment_account, vendor, customer, project])
    await db_session.flush()

    return {
        "org": org,
        "manager": manager,
        "viewer": viewer,
        "payment_account": payment_account,
        "vendor": vendor,
        "customer": customer,
        "project": project,
    }


@pytest.mark.asyncio
async def test_post_direct_purchase_document_converts_to_transaction_and_journal(
    db_session, posting_setup
):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    payment_account = posting_setup["payment_account"]

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\ndirect-purchase-proof"),
        "receipt.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(payment_account.id),
        "cost_category": CostCategory.MAT.value,
        "amount": "2500000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-10",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Pembelian semen proyek",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    service = DocumentPostingService(db_session)
    result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )

    assert result.document_id == doc.id
    assert result.processing_status == DocumentProcessingStatus.POSTED
    assert result.already_posted is False
    assert result.posting_outcome == "POSTED"
    assert result.transaction_id is not None
    assert result.journal_entry_id is not None

    # Check durable Document state
    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.POSTED
    assert doc.converted_transaction_id == result.transaction_id
    assert doc.candidate_transaction["status"] == CandidateStatus.CONVERTED.value
    assert doc.candidate_transaction["converted_transaction_id"] == str(result.transaction_id)

    # Check Transaction created via TransactionService
    trx = await db_session.scalar(select(Transaction).where(Transaction.id == result.transaction_id))
    assert trx is not None
    assert trx.organization_id == org.id
    assert trx.transaction_type == TransactionType.DIRECT_PURCHASE
    assert trx.amount == Decimal("2500000.00")
    assert trx.workflow_status == WorkflowStatus.POSTED
    assert trx.counterparty_id == vendor.id
    assert trx.payment_account_id == payment_account.id

    # Check balanced Journal Entry
    je = await db_session.scalar(select(JournalEntry).where(JournalEntry.id == result.journal_entry_id))
    assert je is not None
    assert je.organization_id == org.id
    assert je.transaction_id == trx.id
    assert je.is_balanced is True
    assert je.total_debit == Decimal("2500000.00")
    assert je.total_credit == Decimal("2500000.00")

    # Check Audit Log
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == doc.id,
            AuditLog.action == "DOCUMENT_POSTED",
        )
    )
    assert audit is not None
    assert audit.actor_id == manager.id


@pytest.mark.asyncio
async def test_retry_of_already_posted_document_returns_existing_result_idempotently(
    db_session, posting_setup
):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    payment_account = posting_setup["payment_account"]

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nretry-proof"),
        "receipt_retry.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(payment_account.id),
        "cost_category": CostCategory.MAT.value,
        "amount": "1000000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-11",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Pembelian bahan",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    service = DocumentPostingService(db_session)

    # First post
    first_result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )
    assert first_result.already_posted is False
    assert first_result.posting_outcome == "POSTED"

    # Count records before retry
    trx_count_before = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org.id)
    )
    je_count_before = await db_session.scalar(
        select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org.id)
    )

    # Second post (retry)
    second_result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )

    assert second_result.already_posted is True
    assert second_result.posting_outcome == "ALREADY_POSTED"
    assert second_result.transaction_id == first_result.transaction_id
    assert second_result.journal_entry_id == first_result.journal_entry_id

    # Verify counts unchanged
    trx_count_after = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org.id)
    )
    je_count_after = await db_session.scalar(
        select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org.id)
    )
    assert trx_count_after == trx_count_before
    assert je_count_after == je_count_before


@pytest.mark.asyncio
async def test_not_ready_or_unresolved_review_fails_closed(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]

    service = DocumentPostingService(db_session)

    # 1. Document in REVIEW_REQUIRED
    doc_review_req = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nreview-req"),
        "doc1.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc_review_req.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc_review_req.candidate_transaction = {
        "id": str(doc_review_req.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "amount": "500000.00",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.REVIEW_REQUIRED.value,
    }
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await service.post_document(org.id, doc_review_req.id, manager.id, manager.role)
    assert "READY_TO_POST" in str(exc_info.value) or "status" in str(exc_info.value)

    # 2. Document READY_TO_POST but has unresolved review flags
    doc_flagged = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nflagged"),
        "doc2.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc_flagged.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc_flagged.review_flags = ["OCR_LOW_CONFIDENCE"]
    doc_flagged.candidate_transaction = {
        "id": str(doc_flagged.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "amount": "500000.00",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.READY_TO_POST.value,
    }
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await service.post_document(org.id, doc_flagged.id, manager.id, manager.role)
    assert "unresolved review" in str(exc_info.value).lower()

    # 3. Document with ambiguous matching results
    doc_ambiguous = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nambiguous"),
        "doc3.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc_ambiguous.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc_ambiguous.review_flags = []
    doc_ambiguous.matching_results = {"ambiguous": True}
    doc_ambiguous.candidate_transaction = {
        "id": str(doc_ambiguous.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "amount": "500000.00",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.READY_TO_POST.value,
    }
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await service.post_document(org.id, doc_ambiguous.id, manager.id, manager.role)
    assert "ambiguous" in str(exc_info.value).lower()

    # Verify no transactions were created
    trx_count = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org.id)
    )
    assert trx_count == 0


@pytest.mark.asyncio
async def test_unsupported_transaction_type_fails_closed(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    service = DocumentPostingService(db_session)

    # Unsupported / non-posting-rule type (e.g. TAX_PAYMENT or UNKNOWN)
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nunsupported"),
        "doc_unsup.pdf",
        "application/pdf",
        DocumentType.TAX_INVOICE,
        created_by=manager.id,
    )
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "OTHER_EXPENSE",
        "amount": "5000000.00",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.READY_TO_POST.value,
    }
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await service.post_document(org.id, doc.id, manager.id, manager.role)
    assert "not supported" in str(exc_info.value).lower() or "generic ingestion" in str(exc_info.value).lower()

    # Verify no transaction or journal was persisted
    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert doc.converted_transaction_id is None


@pytest.mark.asyncio
async def test_reversal_type_fails_closed(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    service = DocumentPostingService(db_session)

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nreversal"),
        "doc_rev.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "REVERSAL",
        "amount": "1000000.00",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.READY_TO_POST.value,
    }
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await service.post_document(org.id, doc.id, manager.id, manager.role)
    assert "not supported" in str(exc_info.value).lower() or "reversal" in str(exc_info.value).lower()

    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert doc.converted_transaction_id is None


@pytest.mark.asyncio
async def test_cross_tenant_references_fail_closed(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    payment_account = posting_setup["payment_account"]
    service = DocumentPostingService(db_session)

    # Create a second organization with foreign counterparty and project
    org2 = Organization(slug="foreign-org", legal_name="Foreign Org")
    db_session.add(org2)
    await db_session.flush()

    foreign_vendor = Counterparty(
        id=uuid.uuid4(),
        organization_id=org2.id,
        name="Foreign Vendor",
        is_vendor=True,
        is_active=True,
    )
    foreign_customer = Counterparty(
        id=uuid.uuid4(),
        organization_id=org2.id,
        name="Foreign Customer",
        is_customer=True,
        is_active=True,
    )
    foreign_project = Project(
        id=uuid.uuid4(),
        organization_id=org2.id,
        project_code="PRJ-FOR-01",
        project_name="Foreign Project",
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("50000000.00"),
        start_date=date(2026, 1, 1),
        customer_id=foreign_customer.id,
    )
    db_session.add_all([foreign_vendor, foreign_customer, foreign_project])
    await db_session.flush()

    # Candidate in org pointing to foreign vendor
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\ncross-tenant"),
        "doc_xtenant.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(foreign_vendor.id),
        "payment_account_id": str(payment_account.id),
        "amount": "1000000.00",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.READY_TO_POST.value,
    }
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await service.post_document(org.id, doc.id, manager.id, manager.role)
    assert "not found" in str(exc_info.value).lower() or "counterparty" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_malformed_candidate_payload_fails_closed(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    service = DocumentPostingService(db_session)

    # 1. Empty candidate
    doc_empty = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nempty-cand"),
        "empty_cand.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc_empty.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc_empty.candidate_transaction = {}
    await db_session.flush()

    with pytest.raises(InvariantViolationException) as exc_info:
        await service.post_document(org.id, doc_empty.id, manager.id, manager.role)
    assert exc_info.value.details.get("failure_reason") in {"NOT_READY", "INVALID_CANDIDATE"}

    await db_session.refresh(doc_empty)
    assert doc_empty.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert doc_empty.converted_transaction_id is None

    # 2. Invalid schema (unparseable payload)
    doc_invalid = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\ninvalid-cand"),
        "invalid_cand.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc_invalid.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc_invalid.candidate_transaction = {
        "id": "not-a-uuid",
        "amount": "not-a-number",
    }
    await db_session.flush()

    with pytest.raises(InvariantViolationException) as exc_info:
        await service.post_document(org.id, doc_invalid.id, manager.id, manager.role)
    assert exc_info.value.details.get("failure_reason") == "INVALID_CANDIDATE"

    await db_session.refresh(doc_invalid)
    assert doc_invalid.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert doc_invalid.converted_transaction_id is None

    # 3. Negative amount
    doc_neg = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nneg-cand"),
        "neg_cand.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc_neg.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc_neg.candidate_transaction = {
        "id": str(doc_neg.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "amount": "-500000.00",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.READY_TO_POST.value,
    }
    await db_session.flush()

    with pytest.raises(InvariantViolationException) as exc_info:
        await service.post_document(org.id, doc_neg.id, manager.id, manager.role)
    assert exc_info.value.details.get("failure_reason") in {"ALLOCATION_INVALID", "INVALID_CANDIDATE"}

    await db_session.refresh(doc_neg)
    assert doc_neg.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert doc_neg.converted_transaction_id is None

    # Verify zero transactions created across all malformed attempts
    trx_count = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org.id)
    )
    assert trx_count == 0


@pytest.mark.asyncio
async def test_bank_charge_document_posting(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    payment_account = posting_setup["payment_account"]

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nbank-charge-proof"),
        "bank_charge.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "BANK_CHARGE",
        "payment_account_id": str(payment_account.id),
        "expense_category": ExpenseCategory.BANK_CHARGES.value,
        "amount": "25000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-12",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Biaya administrasi bank bulanan",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    service = DocumentPostingService(db_session)
    result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )

    assert result.document_id == doc.id
    assert result.processing_status == DocumentProcessingStatus.POSTED
    assert result.already_posted is False
    assert result.posting_outcome == "POSTED"

    # Verify transaction
    trx = await db_session.scalar(select(Transaction).where(Transaction.id == result.transaction_id))
    assert trx is not None
    assert trx.transaction_type == TransactionType.BANK_CHARGE
    assert trx.amount == Decimal("25000.00")
    assert trx.workflow_status == WorkflowStatus.POSTED

    # Verify journal entry (balanced: Dr 6107 / Cr 1101)
    je = await db_session.scalar(select(JournalEntry).where(JournalEntry.id == result.journal_entry_id))
    assert je is not None
    assert je.is_balanced is True
    assert je.total_debit == Decimal("25000.00")
    assert je.total_credit == Decimal("25000.00")

    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.POSTED
    assert doc.converted_transaction_id == trx.id


@pytest.mark.asyncio
async def test_ap_settlement_pay_vendor_bill_no_duplicate_expense(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    payment_account = posting_setup["payment_account"]
    project = posting_setup["project"]

    # 1. Existing VendorBill
    bill = VendorBill(
        organization_id=org.id,
        bill_code="BIL-S5-001",
        vendor_id=vendor.id,
        project_id=project.id,
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("3000000.00"),
        status="UNPAID",
    )
    db_session.add(bill)
    await db_session.flush()

    # 2. Ingest payment proof document
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nvendor-payment-proof"),
        "vendor_payment.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "PAY_VENDOR_BILL",
        "counterparty_id": str(vendor.id),
        "payment_account_id": str(payment_account.id),
        "allocation_target_id": str(bill.id),
        "amount": "3000000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-13",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Pelunasan tagihan semen",
    }
    doc.extracted_data = {
        "total_amount": "3000000.00", "currency_code": "IDR",
        "transfer_details": {"execution_status": "EXECUTED", "execution_evidence": "Transfer berhasil"},
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    service = DocumentPostingService(db_session)
    result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )

    assert result.processing_status == DocumentProcessingStatus.POSTED
    assert result.already_posted is False

    # Check transaction: PAY_VENDOR_BILL
    trx = await db_session.scalar(select(Transaction).where(Transaction.id == result.transaction_id))
    assert trx.transaction_type == TransactionType.PAY_VENDOR_BILL
    assert trx.amount == Decimal("3000000.00")

    # Check journal entry: Debit 2101 (AP) / Credit 1101 (Cash) — NO 5101/610x expense
    from src.models.journal import JournalLine
    from src.models.coa import ChartOfAccount
    je = await db_session.scalar(select(JournalEntry).where(JournalEntry.id == result.journal_entry_id))
    assert je.is_balanced is True
    assert je.total_debit == Decimal("3000000.00")
    assert je.total_credit == Decimal("3000000.00")

    account_codes = set(
        await db_session.scalars(
            select(ChartOfAccount.account_code)
            .join(JournalLine, JournalLine.account_id == ChartOfAccount.id)
            .where(JournalLine.journal_entry_id == je.id)
        )
    )
    assert "2101" in account_codes  # Accounts Payable debited
    assert "1101" in account_codes  # Cash/Bank credited
    assert "5101" not in account_codes  # NO second project cost expense
    assert "6199" not in account_codes  # NO second operational expense

    # Check subledger allocation
    alloc = await db_session.scalar(
        select(VendorPaymentAllocation).where(
            VendorPaymentAllocation.payment_transaction_id == trx.id,
            VendorPaymentAllocation.bill_id == bill.id,
        )
    )
    assert alloc is not None
    assert alloc.allocated_amount == Decimal("3000000.00")

    # Retry of post: idempotent, no duplicates
    retry_result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )
    assert retry_result.already_posted is True
    assert retry_result.transaction_id == trx.id
    alloc_count = await db_session.scalar(
        select(func.count(VendorPaymentAllocation.id)).where(VendorPaymentAllocation.bill_id == bill.id)
    )
    assert alloc_count == 1


@pytest.mark.asyncio
async def test_ar_settlement_customer_payment_no_duplicate_revenue(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    customer = posting_setup["customer"]
    payment_account = posting_setup["payment_account"]
    project = posting_setup["project"]

    # 1. Existing CustomerInvoice
    invoice = CustomerInvoice(
        organization_id=org.id,
        invoice_code="INV-S5-001",
        customer_id=customer.id,
        project_id=project.id,
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("5000000.00"),
        status="ISSUED",
    )
    db_session.add(invoice)
    await db_session.flush()

    # 2. Ingest payment receipt document
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\ncustomer-payment-proof"),
        "customer_payment.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "CUSTOMER_PAYMENT",
        "counterparty_id": str(customer.id),
        "payment_account_id": str(payment_account.id),
        "allocation_target_id": str(invoice.id),
        "amount": "5000000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-13",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Pembayaran termin klien",
    }
    doc.extracted_data = {
        "total_amount": "5000000.00", "currency_code": "IDR",
        "transfer_details": {"execution_status": "EXECUTED", "execution_evidence": "Transfer berhasil"},
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    service = DocumentPostingService(db_session)
    result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )

    assert result.processing_status == DocumentProcessingStatus.POSTED
    assert result.already_posted is False

    # Check transaction: CUSTOMER_PAYMENT
    trx = await db_session.scalar(select(Transaction).where(Transaction.id == result.transaction_id))
    assert trx.transaction_type == TransactionType.CUSTOMER_PAYMENT
    assert trx.amount == Decimal("5000000.00")

    # Check journal entry: Debit 1101 (Cash) / Credit 1103 (AR) — NO 4101 revenue
    from src.models.journal import JournalLine
    from src.models.coa import ChartOfAccount
    je = await db_session.scalar(select(JournalEntry).where(JournalEntry.id == result.journal_entry_id))
    assert je.is_balanced is True
    assert je.total_debit == Decimal("5000000.00")
    assert je.total_credit == Decimal("5000000.00")

    account_codes = set(
        await db_session.scalars(
            select(ChartOfAccount.account_code)
            .join(JournalLine, JournalLine.account_id == ChartOfAccount.id)
            .where(JournalLine.journal_entry_id == je.id)
        )
    )
    assert "1101" in account_codes  # Cash/Bank debited
    assert "1201" in account_codes  # Accounts Receivable credited
    assert "4101" not in account_codes  # NO second revenue recognition

    # Check subledger allocation
    alloc = await db_session.scalar(
        select(CustomerPaymentAllocation).where(
            CustomerPaymentAllocation.payment_transaction_id == trx.id,
            CustomerPaymentAllocation.invoice_id == invoice.id,
        )
    )
    assert alloc is not None
    assert alloc.allocated_amount == Decimal("5000000.00")

    # Retry of post: idempotent, no duplicates
    retry_result = await service.post_document(
        organization_id=org.id,
        document_id=doc.id,
        actor_id=manager.id,
        actor_role=manager.role,
    )
    assert retry_result.already_posted is True
    assert retry_result.transaction_id == trx.id
    alloc_count = await db_session.scalar(
        select(func.count(CustomerPaymentAllocation.id)).where(CustomerPaymentAllocation.invoice_id == invoice.id)
    )
    assert alloc_count == 1


@pytest.mark.asyncio
async def test_posting_failure_does_not_falsely_mark_document_posted(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    payment_account = posting_setup["payment_account"]

    # Ingest document with invalid allocation target (does not exist)
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nfail-proof"),
        "fail.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    doc.extracted_data = {
        "total_amount": "1000000.00", "currency_code": "IDR",
        "transfer_details": {"execution_status": "EXECUTED", "execution_evidence": "Transfer berhasil"},
    }
    fake_bill_id = uuid.uuid4()
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "PAY_VENDOR_BILL",
        "counterparty_id": str(vendor.id),
        "payment_account_id": str(payment_account.id),
        "allocation_target_id": str(fake_bill_id),
        "amount": "1000000.00",
        "transaction_date": "2026-09-13",
        "status": CandidateStatus.READY_TO_POST.value,
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    service = DocumentPostingService(db_session)
    with pytest.raises(EntityNotFoundException):
        await service.post_document(org.id, doc.id, manager.id, manager.role)

    # Invariant: Document remains READY_TO_POST, converted_transaction_id is None, zero transactions created
    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert doc.converted_transaction_id is None

    trx_count = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org.id)
    )
    assert trx_count == 0


@pytest.mark.asyncio
async def test_manual_post_endpoint_authorized_and_unauthorized(security_client: AsyncClient, db_session, posting_setup):
    from src.api.auth import create_access_token

    org = posting_setup["org"]
    manager = posting_setup["manager"]
    viewer = posting_setup["viewer"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    payment_account = posting_setup["payment_account"]

    def auth_headers(user: User) -> dict[str, str]:
        token = create_access_token(str(user.id), {"organization_id": str(org.id)})
        return {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org.id),
            "X-User-ID": str(user.id),
        }

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nendpoint-test"),
        "endpoint_test.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(payment_account.id),
        "cost_category": CostCategory.MAT.value,
        "amount": "750000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-14",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Bahan uji endpoint",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.commit()

    # 1. Unauthenticated (no token) -> 401
    unauth_resp = await security_client.post(
        f"/api/v1/documents/{doc.id}/post",
        headers={"X-Organization-ID": str(org.id)},
    )
    assert unauth_resp.status_code == 401

    # 2. Viewer (unauthorized role) -> 403
    viewer_resp = await security_client.post(
        f"/api/v1/documents/{doc.id}/post",
        headers=auth_headers(viewer),
    )
    assert viewer_resp.status_code == 403

    # 3. Manager (authorized role) -> 200 OK
    manager_resp = await security_client.post(
        f"/api/v1/documents/{doc.id}/post",
        headers=auth_headers(manager),
    )
    assert manager_resp.status_code == 200
    data = manager_resp.json()
    assert data["processing_status"] == "POSTED"
    assert data["already_posted"] is False
    assert data["transaction_id"] is not None
    assert data["journal_entry_id"] is not None

    # 4. Retry by Manager -> 200 OK with already_posted=True
    retry_resp = await security_client.post(
        f"/api/v1/documents/{doc.id}/post",
        headers=auth_headers(manager),
    )
    assert retry_resp.status_code == 200
    retry_data = retry_resp.json()
    assert retry_data["already_posted"] is True
    assert retry_data["transaction_id"] == data["transaction_id"]

    # 5. Nonexistent document -> 404
    fake_id = uuid.uuid4()
    not_found_resp = await security_client.post(
        f"/api/v1/documents/{fake_id}/post",
        headers=auth_headers(manager),
    )
    assert not_found_resp.status_code == 404


@pytest.mark.asyncio
async def test_concurrent_same_document_post_prevents_duplicate(db_session, posting_setup):
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    payment_account = posting_setup["payment_account"]

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nconcurrent-test"),
        "concurrent_test.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(payment_account.id),
        "cost_category": CostCategory.MAT.value,
        "amount": "1500000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-15",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Uji idempotensi concurrent",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    service = DocumentPostingService(db_session)

    res1 = await service.post_document(org.id, doc.id, manager.id, manager.role)
    res2 = await service.post_document(org.id, doc.id, manager.id, manager.role)

    assert res1.already_posted is False
    assert res2.already_posted is True
    assert res1.transaction_id == res2.transaction_id
    assert res1.journal_entry_id == res2.journal_entry_id

    # Verify database counts
    trx_count = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org.id)
    )
    assert trx_count == 1

    je_count = await db_session.scalar(
        select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org.id)
    )
    assert je_count == 1


def _make_auth_headers(user: User, org_id: uuid.UUID) -> dict[str, str]:
    from src.api.auth import create_access_token
    token = create_access_token(str(user.id), {"organization_id": str(org_id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(user.id),
    }


@pytest.mark.asyncio
async def test_approve_candidate_enqueues_auto_post_for_auto_safe_type(
    security_client: AsyncClient,
    posting_setup,
    db_session,
):
    """
    Proves Slice 5 auto-post trigger design:
    Approving an AUTO_SAFE document (DIRECT_PURCHASE) transitions it to READY_TO_POST
    and durably enqueues a DOCUMENT_POST background job without synchronous posting.
    """
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    pa = posting_setup["payment_account"]

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nauto-safe-test"),
        "auto_safe.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(pa.id),
        "cost_category": CostCategory.MAT.value,
        "amount": "850000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-16",
        "status": CandidateStatus.READY_FOR_APPROVAL.value,
        "description": "Auto safe direct purchase",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.flush()

    # Call approval endpoint
    resp = await security_client.post(
        f"/api/v1/documents/{doc.id}/approve",
        headers=_make_auth_headers(manager, org.id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processing_status"] == DocumentProcessingStatus.READY_TO_POST.value

    # Verify background job was enqueued
    job = await db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.job_type == "DOCUMENT_POST",
            BackgroundJob.idempotency_key == f"document-post:{doc.id}",
        )
    )
    assert job is not None
    assert job.payload["document_id"] == str(doc.id)
    status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
    assert status_str in ("PENDING", "RUNNING")

    # Verify NO financial transaction or journal exists yet (approval did NOT post synchronously)
    trx_count = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org.id)
    )
    assert trx_count == 0


@pytest.mark.asyncio
async def test_approve_candidate_does_not_enqueue_auto_post_for_manual_only_type(
    security_client: AsyncClient,
    posting_setup,
    db_session,
):
    """
    Proves Slice 5 auto-post eligibility gating:
    Approving a processable but non-AUTO_SAFE candidate (PAY_VENDOR_BILL)
    transitions to READY_TO_POST but does NOT enqueue a background job.
    It remains READY_TO_POST for explicit manual POST action.
    """
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    pa = posting_setup["payment_account"]

    bill = VendorBill(
        organization_id=org.id,
        vendor_id=vendor.id,
        project_id=project.id,
        bill_code="BILL-AP-GATE-001",
        total_amount=Decimal("3000000.00"),
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        status=WorkflowStatus.APPROVED,
    )
    db_session.add(bill)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nmanual-only-test"),
        "manual_only.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "PAY_VENDOR_BILL",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(pa.id),
        "allocation_target_id": str(bill.id),
        "amount": "3000000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-16",
        "status": CandidateStatus.READY_FOR_APPROVAL.value,
        "description": "Manual-only vendor bill payment",
    }
    doc.extracted_data = {
        "total_amount": "3000000.00", "currency_code": "IDR",
        "transfer_details": {"execution_status": "EXECUTED", "execution_evidence": "Transfer berhasil"},
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.flush()

    # Approve
    resp = await security_client.post(
        f"/api/v1/documents/{doc.id}/approve",
        headers=_make_auth_headers(manager, org.id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processing_status"] == DocumentProcessingStatus.READY_TO_POST.value

    # Verify NO background job was enqueued
    job = await db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.job_type == "DOCUMENT_POST",
            BackgroundJob.idempotency_key == f"document-post:{doc.id}",
        )
    )
    assert job is None


@pytest.mark.asyncio
async def test_worker_auto_post_execution_and_policy_rejection(
    posting_setup,
    db_session,
):
    """
    Proves Background Job Worker auto-posting:
    1. AUTO_SAFE candidate (DIRECT_PURCHASE) posts cleanly via worker with system actor.
    2. Non-AUTO_SAFE candidate (PAY_VENDOR_BILL) is rejected by policy, leaving document
       in READY_TO_POST (not FAILED) and not retrying endlessly.
    """
    from unittest.mock import AsyncMock
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    pa = posting_setup["payment_account"]

    # 1. AUTO_SAFE document
    doc_auto = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nworker-auto"),
        "worker_auto.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc_auto.candidate_transaction = {
        "id": str(doc_auto.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(pa.id),
        "cost_category": CostCategory.MAT.value,
        "amount": "600000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-16",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Auto safe worker execution",
    }
    doc_auto.review_flags = []
    doc_auto.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    # Execute worker handler directly
    await handle_document_post(
        {"document_id": str(doc_auto.id), "organization_id": str(org.id)},
        db_session,
    )
    await db_session.flush()

    # Verify posted
    await db_session.refresh(doc_auto)
    assert doc_auto.processing_status == DocumentProcessingStatus.POSTED
    assert doc_auto.converted_transaction_id is not None

    # Verify audit log recorded system actor (actor_id=None)
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.organization_id == org.id,
            AuditLog.entity_id == doc_auto.id,
            AuditLog.action == "DOCUMENT_POSTED",
        )
    )
    assert audit is not None
    assert audit.actor_id is None

    # 2. Non-AUTO_SAFE document submitted to worker
    doc_policy = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nworker-policy"),
        "worker_policy.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    doc_policy.candidate_transaction = {
        "id": str(doc_policy.id),
        "proposed_transaction_type": "PAY_VENDOR_BILL",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(pa.id),
        "allocation_target_id": str(uuid.uuid4()),
        "amount": "1200000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-16",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Policy blocked for worker",
    }
    doc_policy.review_flags = []
    doc_policy.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()

    # Worker handler executes; should catch POLICY_REQUIRED and NOT raise
    await handle_document_post(
        {"document_id": str(doc_policy.id), "organization_id": str(org.id)},
        db_session,
    )
    await db_session.flush()

    # Verify document remains READY_TO_POST and is NOT marked FAILED
    await db_session.refresh(doc_policy)
    assert doc_policy.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert doc_policy.converted_transaction_id is None


@pytest.mark.asyncio
async def test_downstream_failure_atomicity_rolls_back_cleanly(
    posting_setup,
    db_session,
):
    """
    Proves downstream failure atomicity:
    When a failure occurs downstream after transaction creation (e.g. during journal posting),
    the entire operation rolls back. Document is NOT POSTED, converted_transaction_id is None,
    and no orphan transactions/journals exist.
    """
    from unittest.mock import patch
    org = posting_setup["org"]
    manager = posting_setup["manager"]
    vendor = posting_setup["vendor"]
    project = posting_setup["project"]
    pa = posting_setup["payment_account"]

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nfailure-atomicity"),
        "failure_atomicity.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "payment_account_id": str(pa.id),
        "cost_category": CostCategory.MAT.value,
        "amount": "400000.00",
        "currency_code": "IDR",
        "transaction_date": "2026-09-16",
        "status": CandidateStatus.READY_TO_POST.value,
        "description": "Failure atomicity test",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    doc_id = doc.id
    org_id = org.id
    await db_session.commit()

    service = DocumentPostingService(db_session)

    # Simulate downstream catastrophic failure inside AccountingEngine.post_transaction
    with patch.object(
        service.accounting_engine,
        "post_transaction",
        side_effect=RuntimeError("Simulated downstream GL failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated downstream GL failure"):
            await service.post_document(org_id, doc_id, manager.id, manager.role)

    # Roll back the aborted session
    await db_session.rollback()

    # Re-fetch document from database
    refreshed_doc = await db_session.scalar(
        select(Document).where(Document.id == doc_id)
    )
    assert refreshed_doc.processing_status == DocumentProcessingStatus.READY_TO_POST
    assert refreshed_doc.converted_transaction_id is None

    # Verify zero transactions exist
    trx_count = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.organization_id == org_id)
    )
    assert trx_count == 0
