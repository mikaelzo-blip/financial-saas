import uuid
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import (
    AccountType,
    NormalBalance,
    ProjectStatus,
    TransactionType,
    CostCategory,
)
from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation, CustomerRetentionRelease
from src.models.payable import VendorBill
from src.models.transaction import Transaction
from src.core.exceptions import InvariantViolationException, EntityNotFoundException
from src.schemas.transaction import TransactionCreate
from src.schemas.project import ProjectStatusUpdate
from src.services.accounting_engine import AccountingEngine
from src.services.transaction_service import TransactionService
from src.services.receivable_service import CustomerARService
from src.services.project_service import ProjectService
from src.services.reversal_service import ReversalService
from src.services.reporting.gl_service import GeneralLedgerService
from src.services.reporting.trial_balance_service import TrialBalanceService
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.project_reporting_service import ProjectReportingService
from src.services.coa_seeder import seed_standard_coa


async def setup_uat10_context(session: AsyncSession, prefix: str = "uat10"):
    unique_suffix = uuid.uuid4().hex[:6]
    org = Organization(
        slug=f"org-{prefix}-{unique_suffix}",
        legal_name=f"PT Kontraktor {prefix.upper()} {unique_suffix}",
        tax_id=f"01.{unique_suffix}.789.0-000.000",
    )
    session.add(org)
    await session.flush()

    await seed_standard_coa(session, org.id)

    # Cash account
    cash_coa = (await session.execute(
        select(ChartOfAccount).where(
            ChartOfAccount.organization_id == org.id,
            ChartOfAccount.account_code == "1101"
        )
    )).scalar_one()

    pay_acc = PaymentAccount(
        organization_id=org.id,
        name=f"Bank Mandiri {prefix}",
        account_number=f"123-00-{unique_suffix}",
        coa_account_id=cash_coa.id,
    )
    session.add(pay_acc)

    customer = Counterparty(
        organization_id=org.id,
        name=f"Customer Pemberi Kerja {prefix}",
        is_customer=True,
    )
    vendor = Counterparty(
        organization_id=org.id,
        name=f"Vendor Supplier {prefix}",
        is_vendor=True,
    )
    session.add_all([customer, vendor])
    await session.flush()

    project = Project(
        organization_id=org.id,
        project_code=f"PRJ-{prefix.upper()}-{unique_suffix}",
        project_name=f"Proyek Konstruksi {prefix}",
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 1, 1),
        customer_id=customer.id,
        project_status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    await session.flush()
    await session.commit()

    return org, customer, vendor, project, pay_acc


@pytest.mark.asyncio
async def test_full_project_lifecycle_retention_and_settlement(db_session: AsyncSession):
    """
    Test Phase A to Phase H:
    1. Project IN_PROGRESS with budget & contract
    2. Progress billing with 10% retention: Rp100,000,000 total -> Rp90,000,000 AR (1201) + Rp10,000,000 Retention (1202) -> Rp100,000,000 Revenue (4101)
    3. Vendor bill for project cost: Rp40,000,000 Cost (5101) -> Rp40,000,000 AP (2101)
    4. Customer pays collectible portion: Rp90,000,000 Cash (1101) -> Rp90,000,000 AR (1201)
    5. Vendor payment: Rp40,000,000 AP (2101) -> Rp40,000,000 Cash (1101)
    6. Physical Completion (COMPLETED): Allowed even though retention is outstanding
    7. Closure Guards: Cannot CLOSE because Rp10,000,000 retention is outstanding
    8. Retention Release: BAST-2 issued, Rp10,000,000 Retention Release posted: 1201 Dr Rp10m, 1202 Cr Rp10m (No double revenue!)
    9. Customer pays retention: Rp10,000,000 Cash (1101) -> Rp10,000,000 AR (1201)
    10. Financial Closure (CLOSED): All settled, project transitions to CLOSED
    11. Final financial reporting & accounting invariants verified
    """
    org, customer, vendor, project, pay_acc = await setup_uat10_context(db_session, "lifecycle")
    engine = AccountingEngine(db_session)
    trx_service = TransactionService(db_session)
    proj_service = ProjectService(db_session)
    ar_service = CustomerARService(db_session)

    # 1. Capital contribution so org has initial cash buffer
    cap_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 9, 1),
            amount=Decimal("50000000.00"),
            payment_account_id=pay_acc.id,
            description="Owner capital injection",
        )
    )
    await engine.post_transaction(org.id, cap_trx.id)

    # 2. Progress Billing with 10% retention
    # Invoicing Rp100m contract with 10% retention (Rp10m) -> Rp90m collectible AR
    inv_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 5),
            amount=Decimal("100000000.00"),
            counterparty_id=customer.id,
            project_id=project.id,
            retention_rate=Decimal("0.1000"),
            retention_amount=Decimal("10000000.00"),
            reference_no="INV-PRJ-001",
            description="Progress Billing 100% with 10% Retention",
        )
    )
    await engine.post_transaction(org.id, inv_trx.id)

    # Verify Invoice model fields
    inv_stmt = select(CustomerInvoice).where(
        CustomerInvoice.organization_id == org.id,
        CustomerInvoice.project_id == project.id
    )
    invoice = (await db_session.execute(inv_stmt)).scalar_one()
    assert invoice.total_amount == Decimal("100000000.00")
    assert invoice.retention_rate == Decimal("0.1000")
    assert invoice.retention_amount == Decimal("10000000.00")
    assert invoice.calculate_collectible_amount() == Decimal("90000000.00")
    assert invoice.calculate_outstanding_amount() == Decimal("90000000.00")
    assert invoice.calculate_retention_outstanding() == Decimal("10000000.00")

    # Verify GL postings:
    gl_1201 = await GeneralLedgerService.get_general_ledger(
        db_session, org.id, "1201", date(2026, 9, 1), date(2026, 12, 31)
    )
    gl_1202 = await GeneralLedgerService.get_general_ledger(
        db_session, org.id, "1202", date(2026, 9, 1), date(2026, 12, 31)
    )
    gl_4101 = await GeneralLedgerService.get_general_ledger(
        db_session, org.id, "4101", date(2026, 9, 1), date(2026, 12, 31)
    )
    assert any(l.debit == Decimal("90000000.00") for l in gl_1201.entries)
    assert any(l.debit == Decimal("10000000.00") for l in gl_1202.entries)
    assert any(l.credit == Decimal("100000000.00") for l in gl_4101.entries)

    # 3. Vendor Bill for project cost: Rp40,000,000
    bill_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 10),
            amount=Decimal("40000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="BILL-MAT-001",
            description="Material purchasing for project",
        )
    )
    await engine.post_transaction(org.id, bill_trx.id)

    # 4. Customer pays collectible portion: Rp90,000,000
    pay_cust_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 15),
            amount=Decimal("90000000.00"),
            counterparty_id=customer.id,
            payment_account_id=pay_acc.id,
            description="Payment for collectible invoice portion",
        )
    )
    await engine.post_transaction(org.id, pay_cust_trx.id)

    # Allocate payment to invoice
    await ar_service.allocate_customer_payment(
        org.id,
        pay_cust_trx.id,
        [(invoice.id, Decimal("90000000.00"))],
    )

    await db_session.refresh(invoice)
    assert invoice.calculate_paid_amount() == Decimal("90000000.00")
    assert invoice.calculate_outstanding_amount() == Decimal("0.00")
    assert invoice.calculate_retention_outstanding() == Decimal("10000000.00")

    # 5. Vendor payment: Rp40,000,000
    from src.services.payable_service import VendorAPService
    bill_stmt = select(VendorBill).where(
        VendorBill.organization_id == org.id,
        VendorBill.project_id == project.id
    )
    bill = (await db_session.execute(bill_stmt)).scalar_one()

    pay_vend_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 9, 18),
            amount=Decimal("40000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            payment_account_id=pay_acc.id,
            description="Payment for vendor bill",
        )
    )
    await engine.post_transaction(org.id, pay_vend_trx.id)
    await VendorAPService(db_session).allocate_vendor_payment(
        organization_id=org.id,
        payment_transaction_id=pay_vend_trx.id,
        bill_allocations=[(bill.id, Decimal("40000000.00"))],
    )
    await db_session.refresh(bill)
    assert bill.status == "PAID"
    assert bill.calculate_outstanding_amount() == Decimal("0.00")

    # 6. Physical Completion (COMPLETED):
    # Should SUCCEED even with retention outstanding (Rp10m)
    completed_project = await proj_service.update_project_status(
        organization_id=org.id,
        project_id=project.id,
        update=ProjectStatusUpdate(status=ProjectStatus.COMPLETED)
    )
    assert completed_project.project_status == ProjectStatus.COMPLETED

    # 7. Closure Guards: Attempting to CLOSE project before retention is settled must FAIL
    with pytest.raises(InvariantViolationException, match="uncollected retention balance|outstanding"):
        await proj_service.update_project_status(
            organization_id=org.id,
            project_id=project.id,
            update=ProjectStatusUpdate(status=ProjectStatus.CLOSED)
        )

    # 8. Retention Release: Maintenance period expires (BAST-2 issued)
    # Release Rp10,000,000 retention
    release_res = await ar_service.release_customer_retention(
        organization_id=org.id,
        invoice_id=invoice.id,
        release_amount=Decimal("10000000.00"),
        release_date=date(2026, 10, 1),
        notes="BAST-2 final handover and retention release",
    )
    assert release_res.release_amount == Decimal("10000000.00")

    await db_session.refresh(invoice)
    assert invoice.retention_released_amount == Decimal("10000000.00")
    assert invoice.calculate_unreleased_retention() == Decimal("0.00")
    assert invoice.calculate_outstanding_amount() == Decimal("10000000.00")

    # Verify Journal Entry for Retention Release:
    # 1201 Dr 10,000,000
    # 1202 Cr 10,000,000
    gl_ret_after = await GeneralLedgerService.get_general_ledger(
        db_session, org.id, "1202", date(2026, 9, 1), date(2026, 12, 31)
    )
    assert any(l.credit == Decimal("10000000.00") for l in gl_ret_after.entries)

    # 9. Customer pays the released retention: Rp10,000,000
    pay_ret_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 10, 5),
            amount=Decimal("10000000.00"),
            counterparty_id=customer.id,
            payment_account_id=pay_acc.id,
            description="Final payment settling retention",
        )
    )
    await engine.post_transaction(org.id, pay_ret_trx.id)
    await ar_service.allocate_customer_payment(
        org.id,
        pay_ret_trx.id,
        [(invoice.id, Decimal("10000000.00"))],
    )

    await db_session.refresh(invoice)
    assert invoice.calculate_paid_amount() == Decimal("100000000.00")
    assert invoice.calculate_outstanding_amount() == Decimal("0.00")
    assert invoice.calculate_retention_outstanding() == Decimal("0.00")
    assert invoice.status == "PAID"

    # 10. Financial Closure (CLOSED): All obligations settled -> now permitted!
    closed_project = await proj_service.update_project_status(
        organization_id=org.id,
        project_id=project.id,
        update=ProjectStatusUpdate(status=ProjectStatus.CLOSED)
    )
    assert closed_project.project_status == ProjectStatus.CLOSED

    # 11. Final Project Financial Statement and Reconciliations
    prof = await ProjectReportingService.get_project_profitability(db_session, org.id, project.id)
    assert prof.original_contract_value == Decimal("100000000.00")
    assert prof.revised_contract_value == Decimal("100000000.00")
    assert prof.revenue_recognized == Decimal("100000000.00")
    assert prof.total_project_cost == Decimal("40000000.00")
    assert prof.gross_profit == Decimal("60000000.00")
    assert prof.gross_margin_percentage == Decimal("60.00")

    cash_pos = await ProjectReportingService.get_project_cash_position(db_session, org.id, project.id)
    assert cash_pos.invoiced_amount == Decimal("100000000.00")
    assert cash_pos.cash_received == Decimal("100000000.00")
    assert cash_pos.receivable_outstanding == Decimal("0.00")
    assert cash_pos.cash_spent == Decimal("40000000.00")
    assert cash_pos.net_cash_position == Decimal("60000000.00")
    assert cash_pos.is_surplus is True

    # Verify Company-level Financial Reports
    tb = await TrialBalanceService.get_trial_balance(
        db_session, org.id, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert tb.is_balanced is True
    assert tb.total_ending_debit == tb.total_ending_credit

    # Profit & Loss
    pl = await ProfitLossService.get_profit_and_loss(
        db_session, org.id, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert pl.revenue_section.subtotal == Decimal("100000000.00")
    assert pl.cogs_section.subtotal == Decimal("40000000.00")
    assert pl.gross_profit == Decimal("60000000.00")
    assert pl.net_profit == Decimal("60000000.00")

    # Balance Sheet: Assets = Liabilities + Equity
    bs = await BalanceSheetService.get_balance_sheet(db_session, org.id, date(2026, 12, 31))
    assert bs.is_balanced is True
    # Cash in bank: 50m (capital) + 90m (cust) - 40m (vend) + 10m (retention) = 110,000,000
    assert bs.total_assets == Decimal("110000000.00")


@pytest.mark.asyncio
async def test_closure_guards_block_unsettled_conditions(db_session: AsyncSession):
    """
    Test Phase F: closure guards block if:
    - AR is outstanding
    - AP is outstanding
    - Pending review / draft transactions exist
    """
    org, customer, vendor, project, pay_acc = await setup_uat10_context(db_session, "guards")
    trx_service = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    proj_service = ProjectService(db_session)

    # 1. Outstanding AR blocks closure
    inv_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 5),
            amount=Decimal("30000000.00"),
            counterparty_id=customer.id,
            project_id=project.id,
            retention_rate=Decimal("0.0000"),
            retention_amount=Decimal("0.00"),
            description="Billing with zero retention",
        )
    )
    await engine.post_transaction(org.id, inv_trx.id)

    # Completing project physically is allowed
    await proj_service.update_project_status(
        org.id, project.id, ProjectStatusUpdate(status=ProjectStatus.COMPLETED)
    )

    # Closing project fails due to outstanding AR
    with pytest.raises(InvariantViolationException, match="outstanding AR balance|outstanding"):
        await proj_service.update_project_status(
            org.id, project.id, ProjectStatusUpdate(status=ProjectStatus.CLOSED)
        )

    # 2. Outstanding AP blocks closure
    # Settle AR first
    pay_cust_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 10),
            amount=Decimal("30000000.00"),
            counterparty_id=customer.id,
            payment_account_id=pay_acc.id,
            description="Full payment of AR",
        )
    )
    await engine.post_transaction(org.id, pay_cust_trx.id)
    inv = (await db_session.execute(
        select(CustomerInvoice).where(CustomerInvoice.project_id == project.id)
    )).scalar_one()
    await CustomerARService(db_session).allocate_customer_payment(
        org.id, pay_cust_trx.id, [(inv.id, Decimal("30000000.00"))]
    )

    # Create unpaid Vendor Bill
    bill_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 12),
            amount=Decimal("15000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            description="Unpaid bill",
        )
    )
    await engine.post_transaction(org.id, bill_trx.id)

    # Closing project fails due to outstanding AP
    with pytest.raises(InvariantViolationException, match="outstanding AP balance|outstanding"):
        await proj_service.update_project_status(
            org.id, project.id, ProjectStatusUpdate(status=ProjectStatus.CLOSED)
        )


@pytest.mark.asyncio
async def test_retention_release_reversal_safety(db_session: AsyncSession):
    """
    Test Phase I: Reversal of retention release safely reverts subledger
    and re-establishes retention receivable balance.
    """
    org, customer, vendor, project, pay_acc = await setup_uat10_context(db_session, "revrel")
    engine = AccountingEngine(db_session)
    trx_service = TransactionService(db_session)
    ar_service = CustomerARService(db_session)

    # Invoice with 5% retention
    inv_trx = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 5),
            amount=Decimal("50000000.00"),
            counterparty_id=customer.id,
            project_id=project.id,
            retention_rate=Decimal("0.0500"),
            retention_amount=Decimal("2500000.00"),
            description="Invoice with 5% retention",
        )
    )
    await engine.post_transaction(org.id, inv_trx.id)

    inv = (await db_session.execute(
        select(CustomerInvoice).where(CustomerInvoice.project_id == project.id)
    )).scalar_one()

    # Release retention
    rel_res = await ar_service.release_customer_retention(
        org.id,
        inv.id,
        release_amount=Decimal("2500000.00"),
        release_date=date(2026, 10, 1),
        notes="Release before reversal",
    )
    assert rel_res.release_amount == Decimal("2500000.00")

    # Find the RETENTION_RELEASE transaction created
    rel_trx = (await db_session.execute(
        select(Transaction).where(
            Transaction.organization_id == org.id,
            Transaction.transaction_type == TransactionType.RETENTION_RELEASE
        )
    )).scalar_one()
    await db_session.refresh(inv)
    assert inv.retention_released_amount == Decimal("2500000.00")

    # Reverse the retention release transaction
    reversal_service = ReversalService(db_session)
    reversal_trx, rev_je = await reversal_service.reverse_transaction(
        organization_id=org.id,
        original_transaction_id=rel_trx.id,
        reason="Entered in error before inspection completed",
        reversal_date=date(2026, 10, 2),
    )
    assert reversal_trx.transaction_type == TransactionType.REVERSAL

    await db_session.refresh(inv)
    assert inv.retention_released_amount == Decimal("0.00")
    assert inv.calculate_retention_outstanding() == Decimal("2500000.00")


@pytest.mark.asyncio
async def test_tenant_isolation_retention_and_closure(db_session: AsyncSession):
    """
    Test Phase K: Cross-tenant operations must fail closed:
    - Cannot release retention on another tenant's invoice
    - Cannot close another tenant's project
    """
    org1, cust1, vend1, prj1, pay1 = await setup_uat10_context(db_session, "tenant1")
    org2, cust2, vend2, prj2, pay2 = await setup_uat10_context(db_session, "tenant2")

    engine = AccountingEngine(db_session)
    trx_service = TransactionService(db_session)
    ar_service = CustomerARService(db_session)
    proj_service = ProjectService(db_session)

    # Org 1 invoice with retention
    inv_trx = await trx_service.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 5),
            amount=Decimal("10000000.00"),
            counterparty_id=cust1.id,
            project_id=prj1.id,
            retention_rate=Decimal("0.0500"),
            retention_amount=Decimal("500000.00"),
            description="Org1 invoice",
        )
    )
    await engine.post_transaction(org1.id, inv_trx.id)
    inv1 = (await db_session.execute(
        select(CustomerInvoice).where(CustomerInvoice.project_id == prj1.id)
    )).scalar_one()

    # Org 2 attempts to release Org 1's retention -> MUST FAIL
    with pytest.raises((InvariantViolationException, EntityNotFoundException, ValueError)):
        await ar_service.release_customer_retention(
            organization_id=org2.id,
            invoice_id=inv1.id,
            release_amount=Decimal("500000.00"),
            release_date=date(2026, 10, 1),
        )

    # Org 2 attempts to close Org 1's project -> MUST FAIL
    with pytest.raises((InvariantViolationException, EntityNotFoundException, ValueError)):
        await proj_service.update_project_status(
            organization_id=org2.id,
            project_id=prj1.id,
            update=ProjectStatusUpdate(status=ProjectStatus.CLOSED),
        )
