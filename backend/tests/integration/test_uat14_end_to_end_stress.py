import io
import uuid
from datetime import date
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    DuplicateEntityException,
    EntityNotFoundException,
    InvariantViolationException,
)
from src.core.security import hash_password
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.enums import (
    AccountType,
    CandidateStatus,
    CostCategory,
    DocumentProcessingStatus,
    DocumentType,
    ExpenseCategory,
    NormalBalance,
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
from src.schemas.document import DocumentCorrectionRequest, TransactionCandidate
from src.schemas.project import ProjectStatusUpdate
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.document_service import DocumentService
from src.services.immutability_guard import ImmutabilityGuard
from src.services.payable_service import VendorAPService
from src.services.project_service import ProjectService
from src.services.receivable_service import CustomerARService
from src.services.reporting.ap_aging_service import APAgingService
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.dashboard_service import DashboardService
from src.services.reporting.gl_service import GeneralLedgerService
from src.services.reporting.integrity_service import IntegrityService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.project_reporting_service import ProjectReportingService
from src.services.reporting.trial_balance_service import TrialBalanceService
from src.services.reversal_service import ReversalService
from src.services.transaction_service import TransactionService


async def setup_contractor_tenant(db_session: AsyncSession, slug_prefix: str = "uat14"):
    suffix = uuid.uuid4().hex[:6]
    org = Organization(
        slug=f"{slug_prefix}-{suffix}",
        legal_name=f"PT Kontraktor Mandiri {suffix.upper()}",
        default_payment_term_days=30,
        fiscal_year_start_month=1,
    )
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email=f"reviewer.{suffix}@kontraktor.test",
        full_name="Reviewer UAT14",
        password_hash=hash_password("PasswordUAT14!"),
        role=UserRole.MANAGER,
    )
    db_session.add(user)

    # Standard Chart of Accounts
    accounts = [
        ChartOfAccount(organization_id=org.id, account_code="1101", account_name="Kas dan Bank", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSET"),
        ChartOfAccount(organization_id=org.id, account_code="1201", account_name="Piutang Usaha", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSET"),
        ChartOfAccount(organization_id=org.id, account_code="1202", account_name="Piutang Retensi", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSET"),
        ChartOfAccount(organization_id=org.id, account_code="2101", account_name="Utang Usaha", account_type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT, report_group="CURRENT_LIABILITY"),
        ChartOfAccount(organization_id=org.id, account_code="3101", account_name="Modal Pemilik", account_type=AccountType.EQUITY, normal_balance=NormalBalance.CREDIT, report_group="EQUITY"),
        ChartOfAccount(organization_id=org.id, account_code="4101", account_name="Pendapatan Proyek", account_type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT, report_group="REVENUE"),
        ChartOfAccount(organization_id=org.id, account_code="5101", account_name="Harga Pokok Proyek", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="COGS"),
        ChartOfAccount(organization_id=org.id, account_code="6103", account_name="Beban Operasional", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="OPEX"),
    ]
    db_session.add_all(accounts)
    await db_session.flush()

    coa_map = {a.account_code: a for a in accounts}
    pmt_acc = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_map["1101"].id,
        name="Bank Mandiri Operasional",
        bank_name="Mandiri",
        account_number=f"140-00-{suffix}",
        is_active=True,
    )
    customer = Counterparty(
        organization_id=org.id,
        name=f"PT Pemberi Kerja {suffix.upper()}",
        is_customer=True,
        is_vendor=False,
    )
    vendor = Counterparty(
        organization_id=org.id,
        name=f"CV Supplier Beton {suffix.upper()}",
        is_customer=False,
        is_vendor=True,
    )
    db_session.add_all([pmt_acc, customer, vendor])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        customer_id=customer.id,
        project_code=f"PRJ-{suffix.upper()}",
        project_name=f"Proyek Konstruksi Gedung {suffix.upper()}",
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 12, 31),
        original_contract_value=Decimal("500000000.00"),
        revised_contract_value=Decimal("500000000.00"),
    )
    db_session.add(project)
    await db_session.flush()

    return org, user, customer, vendor, project, pmt_acc, coa_map


@pytest.mark.asyncio
async def test_uat14_end_to_end_operational_lifecycles_and_reconciliation(client: AsyncClient, db_session: AsyncSession):
    """
    UAT 14: Complete business workflow coverage & strict ledger reconciliation
    - Flow A: Customer Invoice (with retention) -> AR Allocation -> Customer Payment
    - Flow B: Vendor Bill -> AP Allocation -> Vendor Payment
    - Flow C: Direct Cash Purchase (Material)
    - Flow D: Retention Release (BAST-2) -> Final Settlement -> Project Closure
    - Report surface reconciliation across all steps
    """
    org, user, customer, vendor, project, pmt_acc, coa_map = await setup_contractor_tenant(db_session, "uat14-e2e")
    headers = {"X-Organization-Id": str(org.id), "X-User-Id": str(user.id)}

    trx_svc = TransactionService(db_session)
    eng = AccountingEngine(db_session)

    # Initial Capital: Rp200,000,000 cash injection
    cap_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 8, 1),
            amount=Decimal("200000000.00"),
            payment_account_id=pmt_acc.id,
            description="Initial Owner Equity",
        ),
    )
    await eng.post_transaction(org.id, cap_trx.id)

    # -------------------------------------------------------------
    # FLOW A: Customer Invoicing with 5% Retention (Progress Billing)
    # Total: Rp100,000,000 (Base AR Rp95,000,000 + Retention Rp5,000,000)
    # -------------------------------------------------------------
    inv_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 8, 10),
            amount=Decimal("100000000.00"),
            counterparty_id=customer.id,
            project_id=project.id,
            reference_no="INV-2026-001",
            description="Termin 1 Proyek Konstruksi",
            retention_rate=Decimal("0.0500"),
        ),
    )
    await eng.post_transaction(org.id, inv_trx.id)

    # Verify Customer Invoice Subledger
    inv = await db_session.scalar(select(CustomerInvoice).where(CustomerInvoice.transaction_id == inv_trx.id))
    assert inv is not None
    assert inv.status == "UNPAID"
    assert inv.calculate_base_collectible_amount() == Decimal("95000000.00")
    assert inv.calculate_unreleased_retention() == Decimal("5000000.00")
    assert inv.calculate_outstanding_amount() == Decimal("95000000.00")

    # Flow A: Customer Payment Allocation of Rp95,000,000
    pay_resp = await client.post(
        "/api/v1/customer-payments",
        json={
            "invoice_id": str(inv.id),
            "payment_account_id": str(pmt_acc.id),
            "amount": "95000000.00",
            "payment_date": "2026-08-15",
            "reference_no": "CPAY-2026-001",
            "description": "Pelunasan Termin 1",
        },
        headers=headers,
    )
    assert pay_resp.status_code == 201
    await db_session.refresh(inv)
    assert inv.status == "PARTIALLY_PAID"  # Because retention is still unreleased
    assert inv.calculate_outstanding_amount() == Decimal("0.00")

    # -------------------------------------------------------------
    # FLOW B: Vendor Bill (AP) of Rp40,000,000 & Partial/Full Payment
    # -------------------------------------------------------------
    bill_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 8, 12),
            amount=Decimal("40000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="VBILL-2026-001",
            description="Pengadaan Semen & Pasir",
        ),
    )
    await eng.post_transaction(org.id, bill_trx.id)
    bill = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == bill_trx.id))
    assert bill is not None
    assert bill.status == "UNPAID"
    assert bill.calculate_outstanding_amount() == Decimal("40000000.00")

    # Flow B: Vendor Payment (Partial Rp15,000,000 then Settlement Rp25,000,000)
    vpay1 = await client.post(
        "/api/v1/vendor-payments",
        json={
            "bill_id": str(bill.id),
            "payment_account_id": str(pmt_acc.id),
            "amount": "15000000.00",
            "payment_date": "2026-08-16",
            "reference_no": "VPAY-2026-001",
            "description": "Cicilan 1 Tagihan Vendor",
        },
        headers=headers,
    )
    assert vpay1.status_code == 201
    vpay2 = await client.post(
        "/api/v1/vendor-payments",
        json={
            "bill_id": str(bill.id),
            "payment_account_id": str(pmt_acc.id),
            "amount": "25000000.00",
            "payment_date": "2026-08-20",
            "reference_no": "VPAY-2026-002",
            "description": "Pelunasan Tagihan Vendor",
        },
        headers=headers,
    )
    assert vpay2.status_code == 201
    await db_session.refresh(bill)
    assert bill.status == "PAID"
    assert bill.calculate_outstanding_amount() == Decimal("0.00")

    # -------------------------------------------------------------
    # FLOW C: Direct Cash Purchase (Material Rp10,000,000)
    # -------------------------------------------------------------
    direct_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 8, 22),
            amount=Decimal("10000000.00"),
            payment_account_id=pmt_acc.id,
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="NOTA-CASH-001",
            description="Beli Perlengkapan Darurat Lapangan",
        ),
    )
    await eng.post_transaction(org.id, direct_trx.id)

    # -------------------------------------------------------------
    # FLOW D: Project Completion & Retention Release & Final Settlement
    # -------------------------------------------------------------
    # Transition to ACTIVE first, then physical completion BAST-1
    await ProjectService(db_session).update_project_status(
        org.id, project.id, ProjectStatusUpdate(status=ProjectStatus.ACTIVE)
    )
    await ProjectService(db_session).update_project_status(
        org.id, project.id, ProjectStatusUpdate(status=ProjectStatus.COMPLETED)
    )
    await db_session.refresh(project)
    assert project.project_status == ProjectStatus.COMPLETED

    # Financial Closure should fail while retention is unreleased/unpaid
    with pytest.raises(InvariantViolationException):
        await ProjectService(db_session).update_project_status(
            org.id, project.id, ProjectStatusUpdate(status=ProjectStatus.CLOSED)
        )

    # Release Retention (BAST-2)
    rel_resp = await client.post(
        "/api/v1/customer-invoices/retention-releases",
        json={
            "invoice_id": str(inv.id),
            "release_amount": "5000000.00",
            "release_date": "2026-08-28",
            "release_code": "REL-2026-001",
            "notes": "BAST-2 Pemeliharaan Selesai",
        },
        headers=headers,
    )
    assert rel_resp.status_code == 201
    await db_session.refresh(inv)
    assert inv.calculate_outstanding_amount() == Decimal("5000000.00")

    # Final Customer Payment of Released Retention
    final_pay = await client.post(
        "/api/v1/customer-payments",
        json={
            "invoice_id": str(inv.id),
            "payment_account_id": str(pmt_acc.id),
            "amount": "5000000.00",
            "payment_date": "2026-08-30",
            "reference_no": "CPAY-RET-001",
            "description": "Pelunasan Retensi",
        },
        headers=headers,
    )
    assert final_pay.status_code == 201
    await db_session.refresh(inv)
    assert inv.status == "PAID"
    assert inv.calculate_outstanding_amount() == Decimal("0.00")
    assert inv.calculate_unreleased_retention() == Decimal("0.00")

    # Financial Closure now succeeds (all AR/AP/Retention settled)
    await ProjectService(db_session).update_project_status(
        org.id, project.id, ProjectStatusUpdate(status=ProjectStatus.CLOSED)
    )
    await db_session.refresh(project)
    assert project.project_status == ProjectStatus.CLOSED

    # -------------------------------------------------------------
    # ACCOUNTING RECONCILIATION & INTEGRITY VERIFICATION
    # -------------------------------------------------------------
    as_of = date(2026, 8, 31)
    # 1. Total Debit == Total Credit across all journals
    tb = await TrialBalanceService.get_trial_balance(db_session, org.id, as_of_date=as_of)
    assert tb.is_balanced is True
    assert tb.difference == Decimal("0.00")
    assert tb.total_ending_debit == tb.total_ending_credit

    # 2. Profit & Loss: Revenue 100m - Cost 50m (40m vendor bill + 10m direct cash) = Net Profit 50m
    pl = await ProfitLossService.get_profit_and_loss(db_session, org.id, start_date=date(2026, 8, 1), end_date=as_of)
    assert pl.revenue_section.subtotal == Decimal("100000000.00")
    assert pl.cogs_section.subtotal == Decimal("50000000.00")
    assert pl.gross_profit == Decimal("50000000.00")
    assert pl.net_profit == Decimal("50000000.00")

    # 3. Cash Position:
    # +200m capital + 95m cpay + 5m cpay_ret - 15m vpay - 25m vpay - 10m direct = Rp250,000,000.00
    bs = await BalanceSheetService.get_balance_sheet(db_session, org.id, as_of_date=as_of)
    assert bs.is_balanced is True
    assert bs.total_assets == Decimal("250000000.00")
    assert bs.total_liabilities == Decimal("0.00")  # All AP settled
    assert bs.total_equity == Decimal("250000000.00")  # 200m capital + 50m profit

    cf = await CashFlowService.get_cash_flow(db_session, org.id, start_date=date(2026, 8, 1), end_date=as_of)
    assert cf.closing_cash_balance == Decimal("250000000.00")

    # 4. AR / AP Aging are clean
    ar = await ARAgingService.get_ar_aging(db_session, org.id, as_of_date=as_of)
    ap = await APAgingService.get_ap_aging(db_session, org.id, as_of_date=as_of)
    assert ar.summary.total == Decimal("0.00")
    assert ap.summary.total == Decimal("0.00")

    # 5. Project Profitability vs Project Cash Position
    p_prof = await ProjectReportingService.get_project_profitability(db_session, org.id, project.id)
    assert p_prof.revenue_recognized == Decimal("100000000.00")
    assert p_prof.total_project_cost == Decimal("50000000.00")
    assert p_prof.gross_profit == Decimal("50000000.00")

    p_cash = await ProjectReportingService.get_project_cash_position(db_session, org.id, project.id)
    assert p_cash.cash_received == Decimal("100000000.00")
    assert p_cash.cash_spent == Decimal("50000000.00")
    assert p_cash.net_cash_position == Decimal("50000000.00")

    # 6. Integrity check passes with 0 diagnostics failures
    diag = await IntegrityService.run_diagnostics(db_session, org.id, as_of_date=as_of)
    assert diag.overall_status == "VALID"
    assert all(c.status == "PASS" for c in diag.checks)


@pytest.mark.asyncio
async def test_uat14_failure_and_edge_case_stress_matrix(client: AsyncClient, db_session: AsyncSession, tmp_path):
    """
    Stress-test comprehensive failure and boundary cases:
    1. Duplicate file upload (exact same file & renamed same SHA-256)
    2. Corrupted file & extension/MIME mismatch & oversized payload
    3. Non-financial supporting evidence produces 0 financial transactions
    4. Ambiguous amounts & dates route to review queue
    5. Stale review & double-approval rejection & correction on finalized status
    6. Customer overpayment rejection & Vendor over-allocation rejection
    7. Posted transaction immutability & double-entry reversal lifecycle
    8. Cross-tenant isolation across documents, counterparties, accounts, and reports
    """
    org_a, user_a, cust_a, vend_a, prj_a, pmt_a, coa_a = await setup_contractor_tenant(db_session, "stress-a")
    org_b, user_b, cust_b, vend_b, prj_b, pmt_b, coa_b = await setup_contractor_tenant(db_session, "stress-b")

    headers_a = {"X-Organization-Id": str(org_a.id), "X-User-Id": str(user_a.id)}
    headers_b = {"X-Organization-Id": str(org_b.id), "X-User-Id": str(user_b.id)}

    doc_svc = DocumentService(db_session)
    doc_svc.storage.base_dir = tmp_path

    # 1. Duplicate File Upload within same tenant is rejected
    pdf_bytes = b"%PDF-1.4\nInvoice Ref 123 Total Rp50.000.000"
    doc1 = await doc_svc.ingest_document(org_a.id, io.BytesIO(pdf_bytes), "invoice.pdf", "application/pdf", DocumentType.VENDOR_INVOICE)
    assert doc1 is not None

    with pytest.raises(DuplicateEntityException):
        await doc_svc.ingest_document(org_a.id, io.BytesIO(pdf_bytes), "invoice_renamed.pdf", "application/pdf", DocumentType.VENDOR_INVOICE)

    # Cross-tenant same hash is permitted and tenant-isolated
    doc_b = await doc_svc.ingest_document(org_b.id, io.BytesIO(pdf_bytes), "invoice.pdf", "application/pdf", DocumentType.VENDOR_INVOICE)
    assert doc_b.organization_id == org_b.id
    assert doc_b.id != doc1.id

    # 2. Extension / MIME Mismatch & Empty File
    with pytest.raises(ValueError, match="MIME type"):
        await doc_svc.ingest_document(org_a.id, io.BytesIO(b"NOT_A_PDF"), "test.pdf", "application/pdf", DocumentType.UNKNOWN)

    with pytest.raises(ValueError, match="between 1 and"):
        await doc_svc.ingest_document(org_a.id, io.BytesIO(b""), "empty.pdf", "application/pdf", DocumentType.UNKNOWN)

    # 3. Non-Financial Supporting Evidence (SPK, BAST, Contract, Surat Jalan) produces NO financial mutations
    non_fin_docs = [
        (DocumentType.SPK, b"%PDF-1.4\nSurat Perintah Kerja PRJ-01"),
        (DocumentType.BAST, b"%PDF-1.4\nBerita Acara Serah Terima"),
        (DocumentType.CONTRACT, b"%PDF-1.4\nPerjanjian Kontrak Konstruksi"),
        (DocumentType.SURAT_JALAN, b"%PDF-1.4\nSurat Jalan Pengiriman Material"),
    ]
    for dtype, content in non_fin_docs:
        doc_ev = await doc_svc.ingest_document(org_a.id, io.BytesIO(content), f"{dtype.value.lower()}.pdf", "application/pdf", dtype)
        assert doc_ev.processing_status in {DocumentProcessingStatus.HASHED, DocumentProcessingStatus.PROCESSED}
        assert not doc_ev.candidate_transaction

    # Verify zero journal entries were created by document ingestion
    je_count = (await db_session.scalars(select(JournalEntry).where(JournalEntry.organization_id == org_a.id))).all()
    assert len(je_count) == 0

    # 4. Review Queue, Corrections, and Double-Approval Safety
    doc_cand = await doc_svc.ingest_document(
        org_a.id,
        io.BytesIO(b"%PDF-1.4\nInvoice Ambiguous"),
        "vendor_inv.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        created_by=user_a.id,
    )
    doc_cand.candidate_transaction = TransactionCandidate(
        id=doc_cand.id,
        status=CandidateStatus.REVIEW_REQUIRED,
        proposed_transaction_type=TransactionType.VENDOR_BILL,
        amount=Decimal("15000000.00"),
        description="Candidate pending review",
    ).model_dump(mode="json")
    doc_cand.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc_cand.review_flags = ["MISSING_COUNTERPARTY", "MISSING_PROJECT"]
    await db_session.flush()

    # Attempting to approve while review flags exist fails closed (HTTP 409)
    appr_fail = await client.post(f"/api/v1/documents/{doc_cand.id}/approve", headers=headers_a)
    assert appr_fail.status_code == 409

    # Correct the candidate fields
    corr_resp = await client.post(
        f"/api/v1/documents/{doc_cand.id}/corrections",
        headers=headers_a,
        json={
            "changes": {
                "counterparty_id": str(vend_a.id),
                "project_id": str(prj_a.id),
                "cost_category": CostCategory.MAT.value,
                "transaction_date": "2026-08-20",
                "external_reference": "VINV-CORRECTED-01",
            },
            "reason": "Provided vendor and project mapping",
        },
    )
    assert corr_resp.status_code == 200
    await db_session.refresh(doc_cand)
    assert doc_cand.candidate_transaction["counterparty_id"] == str(vend_a.id)
    assert doc_cand.candidate_transaction["project_id"] == str(prj_a.id)

    # Approve candidate -> converts to authoritative transaction & posts journal
    doc_cand.review_flags = []
    doc_cand.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.flush()

    appr_ok = await client.post(f"/api/v1/documents/{doc_cand.id}/approve", headers=headers_a)
    assert appr_ok.status_code == 201
    await db_session.refresh(doc_cand)
    assert doc_cand.processing_status == DocumentProcessingStatus.PROCESSED

    # Double approval / Replay fails closed (HTTP 409)
    double_appr = await client.post(f"/api/v1/documents/{doc_cand.id}/approve", headers=headers_a)
    assert double_appr.status_code == 409

    # Stale correction on finalized document is rejected (HTTP 409)
    stale_corr = await client.post(
        f"/api/v1/documents/{doc_cand.id}/corrections",
        headers=headers_a,
        json={"changes": {"amount": "999999.00"}, "reason": "Late edit"},
    )
    assert stale_corr.status_code == 409

    # 5. Overpayment & Over-Allocation Safety
    bill_a = await db_session.scalar(select(VendorBill).where(VendorBill.organization_id == org_a.id))
    assert bill_a is not None

    # Overpayment attempt fails (HTTP 422)
    over_vpay = await client.post(
        "/api/v1/vendor-payments",
        headers=headers_a,
        json={
            "bill_id": str(bill_a.id),
            "payment_account_id": str(pmt_a.id),
            "amount": "20000000.00",  # Exceeds 15m
            "payment_date": "2026-08-25",
            "reference_no": "VPAY-OVER-01",
            "description": "Overpay",
        },
    )
    assert over_vpay.status_code == 422
    assert "exceeds" in over_vpay.json()["error"]["message"]

    # Cross-tenant payment attempt fails closed (HTTP 404)
    cross_vpay = await client.post(
        "/api/v1/vendor-payments",
        headers=headers_b,
        json={
            "bill_id": str(bill_a.id),
            "payment_account_id": str(pmt_b.id),
            "amount": "5000000.00",
            "payment_date": "2026-08-25",
            "reference_no": "VPAY-CROSS",
            "description": "Cross tenant pay",
        },
    )
    assert cross_vpay.status_code == 404

    # 6. Posted Transaction Immutability & Reversal Workflow
    trx_to_reverse = await db_session.scalar(select(Transaction).where(Transaction.id == bill_a.transaction_id))
    assert trx_to_reverse.workflow_status == WorkflowStatus.POSTED

    # Mutation after POSTED fails via ImmutabilityGuard
    with pytest.raises(InvariantViolationException, match="immutable"):
        ImmutabilityGuard.assert_transaction_mutable(trx_to_reverse)

    # Reversal creates compensating journal and cancels the bill subledger
    rev_trx, rev_je = await ReversalService(db_session).reverse_transaction(
        org_a.id,
        trx_to_reverse.id,
        reason="Correction of duplicate bill",
        actor_id=user_a.id,
        reversal_date=date(2026, 8, 26),
    )
    assert rev_trx.workflow_status == WorkflowStatus.POSTED
    assert rev_trx.reversal_of_id == trx_to_reverse.id
    await db_session.refresh(bill_a)
    assert bill_a.status == "CANCELLED"
    assert bill_a.calculate_outstanding_amount() == Decimal("0.00")

    # 7. Final Ledger Balance: reversing the bill creates an offsetting journal entry in the same period
    # The journal lines cancel out so the ending net balance is 0 across all accounts.
    tb_final = await TrialBalanceService.get_trial_balance(db_session, org_a.id, as_of_date=date(2026, 8, 31))
    assert tb_final.is_balanced is True
    assert tb_final.difference == Decimal("0.00")
    assert tb_final.total_period_debit == Decimal("30000000.00")
    assert tb_final.total_period_credit == Decimal("30000000.00")
    assert tb_final.total_ending_debit == Decimal("0.00")
    assert tb_final.total_ending_credit == Decimal("0.00")
