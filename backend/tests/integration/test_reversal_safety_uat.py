import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.coa import PaymentAccount
from src.models.transaction import Transaction
from src.models.journal import JournalEntry, JournalLine
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.enums import ProjectStatus, TransactionType, CostCategory, WorkflowStatus, ReviewFlag
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.reversal_service import ReversalService
from src.services.receivable_service import CustomerARService
from src.services.payable_service import VendorAPService
from src.services.immutability_guard import ImmutabilityGuard
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.ap_aging_service import APAgingService
from src.services.reporting.trial_balance_service import TrialBalanceService
from src.services.reporting.project_reporting_service import ProjectReportingService
from src.core.exceptions import InvariantViolationException, EntityNotFoundException


async def create_test_tenant(db_session: AsyncSession, slug: str):
    org = Organization(slug=slug, legal_name=f"PT {slug.replace('-', ' ').title()}")
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    customer = Counterparty(organization_id=org.id, name=f"Customer {slug}", is_customer=True)
    vendor = Counterparty(organization_id=org.id, name=f"Vendor {slug}", is_vendor=True)
    db_session.add_all([customer, vendor])
    await db_session.flush()
    project = Project(
        organization_id=org.id,
        project_code=f"PRJ-{slug[:8].upper()}",
        project_name=f"Project {slug}",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("500000000.00"),
        revised_contract_value=Decimal("500000000.00"),
    )
    db_session.add(project)
    await db_session.commit()
    return org, customer, vendor, project


@pytest.mark.asyncio
async def test_duplicate_reference_replay_and_idempotency_safety(db_session: AsyncSession):
    """Phase B: Verify duplicate business reference replays do not create uninspected financial events."""
    org, customer, vendor, project = await create_test_tenant(db_session, "dup-replay-safety")
    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)

    # 1. Post original invoice
    inv1 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 2, 1),
            amount=Decimal("25000000.00"),
            reference_no="INV-DUP-TEST-001",
            counterparty_id=customer.id,
            description="Original Invoice",
            project_id=project.id,
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org.id, inv1.id)
    await db_session.commit()

    # 2. Attempt duplicate reference for customer invoice -> must route to review
    inv_dup = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 2, 1),
            amount=Decimal("25000000.00"),
            reference_no="INV-DUP-TEST-001",
            counterparty_id=customer.id,
            description="Replayed Duplicate Invoice",
            project_id=project.id,
        ),
    )
    await db_session.commit()
    assert inv_dup.workflow_status == WorkflowStatus.REVIEW_REQUIRED
    assert any(flag.flag == ReviewFlag.DUPLICATE_SUSPECTED for flag in inv_dup.review_flags)

    # 3. Post original payment
    kas_acc = (await db_session.scalars(
        select(PaymentAccount).where(PaymentAccount.organization_id == org.id)
    )).first()

    ar_svc = CustomerARService(db_session)
    cust_inv = (await db_session.scalars(
        select(CustomerInvoice).where(CustomerInvoice.transaction_id == inv1.id)
    )).first()

    pay1 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 2, 5),
            amount=Decimal("25000000.00"),
            reference_no="PAY-DUP-TEST-001",
            counterparty_id=customer.id,
            payment_account_id=kas_acc.id,
            description="Original Customer Payment",
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org.id, pay1.id)
    await ar_svc.allocate_customer_payment(org.id, pay1.id, [(cust_inv.id, Decimal("25000000.00"))])
    await db_session.commit()

    # 4. Attempt replaying payment reference -> must flag as review required
    pay_dup = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 2, 5),
            amount=Decimal("25000000.00"),
            reference_no="PAY-DUP-TEST-001",
            counterparty_id=customer.id,
            payment_account_id=kas_acc.id,
            description="Replayed Customer Payment",
        ),
    )
    await db_session.commit()
    assert pay_dup.workflow_status == WorkflowStatus.REVIEW_REQUIRED
    assert any(flag.flag == ReviewFlag.DUPLICATE_SUSPECTED for flag in pay_dup.review_flags)


@pytest.mark.asyncio
async def test_overpayment_and_cross_allocation_rejection(db_session: AsyncSession):
    """Phase C: Verify rejection of over-allocation, paid record allocation, cross-party, and cross-tenant."""
    org_a, cust_a, vend_a, proj_a = await create_test_tenant(db_session, "alloc-safe-a")
    org_b, cust_b, vend_b, proj_b = await create_test_tenant(db_session, "alloc-safe-b")

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    ar_svc = CustomerARService(db_session)
    ap_svc = VendorAPService(db_session)

    # 1. Create and post Customer Invoice A: Rp 10.000.000
    t_inv = await trx_svc.create_transaction(
        org_a.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("10000000.00"),
            reference_no="INV-A-100",
            counterparty_id=cust_a.id,
            description="Invoice Org A",
            project_id=proj_a.id,
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org_a.id, t_inv.id)
    await db_session.commit()
    inv_a = (await db_session.scalars(select(CustomerInvoice).where(CustomerInvoice.transaction_id == t_inv.id))).first()

    # 2. Create customer payment A: Rp 15.000.000
    kas_a = (await db_session.scalars(
        select(PaymentAccount).where(PaymentAccount.organization_id == org_a.id)
    )).first()
    t_pay = await trx_svc.create_transaction(
        org_a.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 3, 5),
            amount=Decimal("15000000.00"),
            reference_no="PAY-A-100",
            counterparty_id=cust_a.id,
            payment_account_id=kas_a.id,
            description="Payment Org A",
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org_a.id, t_pay.id)
    await db_session.commit()

    # Rejection 1: Allocation > remaining invoice amount (Rp 15.000.000 > Rp 10.000.000)
    with pytest.raises(InvariantViolationException) as exc:
        await ar_svc.allocate_customer_payment(org_a.id, t_pay.id, [(inv_a.id, Decimal("15000000.00"))])
    assert "exceeds outstanding balance" in str(exc.value)

    # Valid partial allocation: Rp 6.000.000
    await ar_svc.allocate_customer_payment(org_a.id, t_pay.id, [(inv_a.id, Decimal("6000000.00"))])
    await db_session.commit()
    refreshed_inv = await ar_svc.get_invoice(org_a.id, inv_a.id)
    assert refreshed_inv.status == "PARTIALLY_PAID"
    assert refreshed_inv.calculate_outstanding_amount() == Decimal("4000000.00")

    # Rejection 2: Cross-tenant invoice allocation (Org A payment to Org B invoice)
    t_inv_b = await trx_svc.create_transaction(
        org_b.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("5000000.00"),
            reference_no="INV-B-100",
            counterparty_id=cust_b.id,
            description="Invoice Org B",
            project_id=proj_b.id,
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org_b.id, t_inv_b.id)
    await db_session.commit()
    inv_b = (await db_session.scalars(select(CustomerInvoice).where(CustomerInvoice.transaction_id == t_inv_b.id))).first()

    with pytest.raises(EntityNotFoundException):
        await ar_svc.allocate_customer_payment(org_a.id, t_pay.id, [(inv_b.id, Decimal("4000000.00"))])

    # Settle remaining Rp 4.000.000 on Invoice A
    await ar_svc.allocate_customer_payment(org_a.id, t_pay.id, [(inv_a.id, Decimal("4000000.00"))])
    await db_session.commit()
    refreshed_inv = await ar_svc.get_invoice(org_a.id, inv_a.id)
    assert refreshed_inv.status == "PAID"
    assert refreshed_inv.calculate_outstanding_amount() == Decimal("0.00")

    # Rejection 3: Allocation to already-paid invoice
    with pytest.raises(InvariantViolationException) as exc:
        await ar_svc.allocate_customer_payment(org_a.id, t_pay.id, [(inv_a.id, Decimal("1000.00"))])
    assert "already fully paid" in str(exc.value) or "exceeds outstanding balance" in str(exc.value)

    # Vendor Bill Over-allocation Check
    t_bill = await trx_svc.create_transaction(
        org_a.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("8000000.00"),
            reference_no="BILL-A-100",
            counterparty_id=vend_a.id,
            description="Bill Org A",
            project_id=proj_a.id,
            cost_category=CostCategory.MAT,
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org_a.id, t_bill.id)
    await db_session.commit()
    bill_a = (await db_session.scalars(select(VendorBill).where(VendorBill.transaction_id == t_bill.id))).first()

    t_vpay = await trx_svc.create_transaction(
        org_a.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 3, 6),
            amount=Decimal("10000000.00"),
            reference_no="VPAY-A-100",
            counterparty_id=vend_a.id,
            payment_account_id=kas_a.id,
            description="Vendor Payment Org A",
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org_a.id, t_vpay.id)
    await db_session.commit()

    # Over-allocation against vendor bill
    with pytest.raises(InvariantViolationException) as exc:
        await ap_svc.allocate_vendor_payment(org_a.id, t_vpay.id, [(bill_a.id, Decimal("10000000.00"))])
    assert "exceeds outstanding bill balance" in str(exc.value)


@pytest.mark.asyncio
async def test_customer_invoice_cancellation_and_reversal_lifecycle(db_session: AsyncSession):
    """Phase D: Unpaid Customer Invoice reversal cancels AR, inverts journal, and excludes from AR aging."""
    org, customer, vendor, project = await create_test_tenant(db_session, "inv-cancel-uat")
    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    rev_svc = ReversalService(db_session)
    ar_svc = CustomerARService(db_session)

    # 1. Post Customer Invoice: Rp 30.000.000
    t_inv = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 4, 1),
            amount=Decimal("30000000.00"),
            reference_no="INV-CANCEL-001",
            counterparty_id=customer.id,
            description="Customer Invoice To Be Cancelled",
            project_id=project.id,
        ),
    )
    await db_session.commit()
    orig_je = await engine.post_transaction(org.id, t_inv.id)
    await db_session.commit()

    inv = (await db_session.scalars(select(CustomerInvoice).where(CustomerInvoice.transaction_id == t_inv.id))).first()
    assert inv.status == "UNPAID"

    # Verify P&L and AR Aging before reversal
    pl_before = await ProfitLossService.get_profit_and_loss(db_session, org.id, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    assert pl_before.revenue_section.subtotal == Decimal("30000000.00")
    ar_aging_before = await ARAgingService.get_ar_aging(db_session, org.id, as_of_date=date(2026, 4, 1))
    assert ar_aging_before.summary.total == Decimal("30000000.00")

    # 2. Reverse the Customer Invoice
    rev_trx, rev_je = await rev_svc.reverse_transaction(
        org.id,
        t_inv.id,
        reason="Client contract cancelled before work started",
        reversal_date=date(2026, 4, 2),
    )
    await db_session.commit()

    # 3. Verify Reversal State
    assert rev_trx.workflow_status == WorkflowStatus.POSTED
    assert rev_trx.reversal_of_id == t_inv.id
    assert orig_je.is_reversed is True
    assert orig_je.reversal_entry_id == rev_je.id
    assert rev_je.total_debit == Decimal("30000000.00")
    assert rev_je.total_credit == Decimal("30000000.00")

    # Inverted lines: Dr 4101 Rp 30.000.000 / Cr 1201 Rp 30.000.000
    rev_lines = (await db_session.scalars(
        select(JournalLine).where(JournalLine.journal_entry_id == rev_je.id).order_by(JournalLine.line_number.asc())
    )).all()
    assert len(rev_lines) == 2
    assert rev_lines[0].credit_amount == Decimal("30000000.00")  # Cr 1201 Piutang Usaha
    assert rev_lines[1].debit_amount == Decimal("30000000.00")   # Dr 4101 Pendapatan

    # Verify CustomerInvoice status updated to CANCELLED and outstanding is 0
    refreshed_inv = await ar_svc.get_invoice(org.id, inv.id)
    assert refreshed_inv.status == "CANCELLED"
    assert refreshed_inv.calculate_outstanding_amount() == Decimal("0.00")

    # 4. Verify P&L and AR Aging after reversal
    pl_after = await ProfitLossService.get_profit_and_loss(db_session, org.id, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    assert pl_after.revenue_section.subtotal == Decimal("0.00")
    ar_aging_after = await ARAgingService.get_ar_aging(db_session, org.id, as_of_date=date(2026, 4, 2))
    assert ar_aging_after.summary.total == Decimal("0.00")

    # 5. Balance Sheet equation
    bs = await BalanceSheetService.get_balance_sheet(db_session, org.id, as_of_date=date(2026, 4, 2))
    assert bs.total_assets == Decimal("0.00")
    assert bs.total_liabilities == Decimal("0.00")
    assert bs.total_equity == Decimal("0.00")
    assert bs.is_balanced is True


@pytest.mark.asyncio
async def test_vendor_bill_cancellation_and_reversal_lifecycle(db_session: AsyncSession):
    """Phase E: Unpaid Vendor Bill reversal cancels AP, inverts journal, and excludes from AP aging & project cost."""
    org, customer, vendor, project = await create_test_tenant(db_session, "bill-cancel-uat")
    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    rev_svc = ReversalService(db_session)
    ap_svc = VendorAPService(db_session)

    # 1. Post Vendor Bill: Rp 15.000.000
    t_bill = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 4, 1),
            amount=Decimal("15000000.00"),
            reference_no="BILL-CANCEL-001",
            counterparty_id=vendor.id,
            description="Vendor Material Bill To Cancel",
            project_id=project.id,
            cost_category=CostCategory.MAT,
        ),
    )
    await db_session.commit()
    orig_je = await engine.post_transaction(org.id, t_bill.id)
    await db_session.commit()

    bill = (await db_session.scalars(select(VendorBill).where(VendorBill.transaction_id == t_bill.id))).first()
    assert bill.status == "UNPAID"

    # Verify AP Aging and Project Cost before reversal
    ap_aging_before = await APAgingService.get_ap_aging(db_session, org.id, as_of_date=date(2026, 4, 1))
    assert ap_aging_before.summary.total == Decimal("15000000.00")
    proj_rep_before = await ProjectReportingService.get_project_profitability(db_session, org.id, project.id)
    assert proj_rep_before.total_project_cost == Decimal("15000000.00")

    # 2. Reverse Vendor Bill
    rev_trx, rev_je = await rev_svc.reverse_transaction(
        org.id,
        t_bill.id,
        reason="Vendor invoiced wrong purchase order",
        reversal_date=date(2026, 4, 3),
    )
    await db_session.commit()

    # 3. Verify Reversal
    assert rev_trx.workflow_status == WorkflowStatus.POSTED
    assert rev_trx.reversal_of_id == t_bill.id
    assert orig_je.is_reversed is True

    refreshed_bill = await ap_svc.get_bill(org.id, bill.id)
    assert refreshed_bill.status == "CANCELLED"
    assert refreshed_bill.calculate_outstanding_amount() == Decimal("0.00")

    # Verify AP Aging and Project Cost after reversal
    ap_aging_after = await APAgingService.get_ap_aging(db_session, org.id, as_of_date=date(2026, 4, 3))
    assert ap_aging_after.summary.total == Decimal("0.00")
    proj_rep_after = await ProjectReportingService.get_project_profitability(db_session, org.id, project.id)
    assert proj_rep_after.total_project_cost == Decimal("0.00")


@pytest.mark.asyncio
async def test_customer_and_vendor_payment_reversals(db_session: AsyncSession):
    """Phase F: Reversing customer and vendor payments restores subledger status & releases allocations without repeating rev/cost."""
    org, customer, vendor, project = await create_test_tenant(db_session, "pay-rev-uat")
    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    rev_svc = ReversalService(db_session)
    ar_svc = CustomerARService(db_session)
    ap_svc = VendorAPService(db_session)

    kas_acc = (await db_session.scalars(
        select(PaymentAccount).where(PaymentAccount.organization_id == org.id)
    )).first()

    # 1. Customer Workflow: Post Invoice (Rp 20.000.000) -> Post Payment (Rp 20.000.000) -> Allocate -> Reverse Payment
    t_inv = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 5, 1),
            amount=Decimal("20000000.00"),
            reference_no="INV-PAY-REV-01",
            counterparty_id=customer.id,
            description="Invoice for Payment Reversal Test",
            project_id=project.id,
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_inv.id)
    await db_session.commit()
    inv = (await db_session.scalars(select(CustomerInvoice).where(CustomerInvoice.transaction_id == t_inv.id))).first()

    t_pay = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 5, 2),
            amount=Decimal("20000000.00"),
            reference_no="PAY-REV-01",
            counterparty_id=customer.id,
            payment_account_id=kas_acc.id,
            description="Customer Payment to be reversed",
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_pay.id)
    await ar_svc.allocate_customer_payment(org.id, t_pay.id, [(inv.id, Decimal("20000000.00"))])
    await db_session.commit()

    inv_paid = await ar_svc.get_invoice(org.id, inv.id)
    assert inv_paid.status == "PAID"
    assert inv_paid.calculate_outstanding_amount() == Decimal("0.00")

    # Reverse Customer Payment
    rev_pay_trx, rev_pay_je = await rev_svc.reverse_transaction(
        org.id,
        t_pay.id,
        reason="Cheque bounced / payment bounced",
        reversal_date=date(2026, 5, 3),
    )
    await db_session.commit()

    # Invoice should be restored to UNPAID with Rp 20.000.000 outstanding
    inv_restored = await ar_svc.get_invoice(org.id, inv.id)
    assert inv_restored.status == "UNPAID"
    assert inv_restored.calculate_outstanding_amount() == Decimal("20000000.00")

    # 2. Vendor Workflow: Post Bill (Rp 10.000.000) -> Post Payment (Rp 10.000.000) -> Allocate -> Reverse Payment
    t_bill = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 5, 1),
            amount=Decimal("10000000.00"),
            reference_no="BILL-PAY-REV-01",
            counterparty_id=vendor.id,
            description="Bill for Payment Reversal Test",
            project_id=project.id,
            cost_category=CostCategory.MAT,
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_bill.id)
    await db_session.commit()
    bill = (await db_session.scalars(select(VendorBill).where(VendorBill.transaction_id == t_bill.id))).first()

    t_vpay = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 5, 2),
            amount=Decimal("10000000.00"),
            reference_no="VPAY-REV-01",
            counterparty_id=vendor.id,
            payment_account_id=kas_acc.id,
            description="Vendor Payment to be reversed",
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_vpay.id)
    await ap_svc.allocate_vendor_payment(org.id, t_vpay.id, [(bill.id, Decimal("10000000.00"))])
    await db_session.commit()

    bill_paid = await ap_svc.get_bill(org.id, bill.id)
    assert bill_paid.status == "PAID"
    assert bill_paid.calculate_outstanding_amount() == Decimal("0.00")

    # Reverse Vendor Payment
    rev_vpay_trx, rev_vpay_je = await rev_svc.reverse_transaction(
        org.id,
        t_vpay.id,
        reason="Disbursement cancelled by bank",
        reversal_date=date(2026, 5, 4),
    )
    await db_session.commit()

    # Vendor bill should be restored to UNPAID with Rp 10.000.000 outstanding
    bill_restored = await ap_svc.get_bill(org.id, bill.id)
    assert bill_restored.status == "UNPAID"
    assert bill_restored.calculate_outstanding_amount() == Decimal("10000000.00")


@pytest.mark.asyncio
async def test_immutability_and_audit_chain_integrity(db_session: AsyncSession):
    """Phase G & H: Verify ImmutabilityGuard rejects edits on posted records and audit chain is created."""
    org, customer, vendor, project = await create_test_tenant(db_session, "immutable-audit-uat")
    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    rev_svc = ReversalService(db_session)

    t_dir = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 6, 1),
            amount=Decimal("5000000.00"),
            description="Direct purchase test immutability",
            project_id=project.id,
            cost_category=CostCategory.MAT,
        ),
    )
    await db_session.commit()
    je = await engine.post_transaction(org.id, t_dir.id)
    await db_session.commit()

    # Immutability Check
    with pytest.raises(InvariantViolationException):
        ImmutabilityGuard.assert_transaction_mutable(t_dir)

    with pytest.raises(InvariantViolationException):
        ImmutabilityGuard.assert_journal_entry_immutable(je)

    # Reversal creates audit entry
    rev_trx, rev_je = await rev_svc.reverse_transaction(
        org.id,
        t_dir.id,
        reason="Direct purchase returned to supplier",
        reversal_date=date(2026, 6, 2),
    )
    await db_session.commit()

    # Check Audit Logs
    from src.models.audit import AuditLog
    audit_rows = (await db_session.scalars(
        select(AuditLog).where(AuditLog.organization_id == org.id, AuditLog.entity_id == t_dir.id)
    )).all()
    assert len(audit_rows) > 0
    assert any(a.action == "REVERSAL" for a in audit_rows)
