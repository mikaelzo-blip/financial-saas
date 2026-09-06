import pytest
import uuid
from datetime import date, datetime
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.user import User, UserRole
from src.models.project import Project, ProjectStatus
from src.models.counterparty import Counterparty
from src.models.journal import JournalEntry, JournalLine
from src.models.money_movement import MoneyMovement
from src.models.enums import (
    TransactionType,
    WorkflowStatus,
    MovementDirection,
    ReconciliationStatus,
    ProjectStatus,
    UserRole,
    AccountingPeriodStatus,
)
from src.services.coa_seeder import seed_standard_coa
from src.services.accounting_period_service import AccountingPeriodService
from src.schemas.accounting_period import AccountingPeriodCreate, AccountingPeriodUpdate
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.equity_changes_service import EquityChangesService, CALKService
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.trial_balance_service import TrialBalanceService
from src.services.reporting.gl_service import GeneralLedgerService
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.ap_aging_service import APAgingService
from src.services.reporting.project_reporting_service import ProjectReportingService


@pytest.mark.asyncio
async def test_uat13_integrated_rc1_business_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession
):
    """
    R13: Complete End-to-End Business Lifecycle UAT.
    1. Organization, COA, Vendor, Customer, and Project Setup.
    2. Vendor Lifecycle: Vendor Bill -> AP -> Payment -> MoneyMovement -> Settlement.
    3. Customer Lifecycle: Customer Invoice -> AR -> Payment -> MoneyMovement -> Settlement.
    4. Project Dimension: Project cost & profitability attribution.
    5. Accounting Period Control: Soft close / Close / Block backdated posting.
    6. Reporting Tie-outs: Balance Sheet (A = L + E), P&L, Equity Changes, CALK, Cash Flow.
    """
    # 1. Setup Tenant & Baseline Accounts
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        slug="pt-citra-rc1-kontraktor",
        legal_name="PT Citra RC1 Kontraktor",
        tax_id="01.234.567.8-901.000"
    )
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org_id)

    user = User(
        id=uuid.uuid4(),
        organization_id=org_id,
        email="finance.rc1@citra-kontraktor.id",
        password_hash="hash",
        full_name="Finance Officer RC1",
        role=UserRole.ADMIN
    )
    db_session.add(user)

    vendor = Counterparty(
        id=uuid.uuid4(),
        organization_id=org_id,
        is_vendor=True,
        name="PT Semen Beton Jaya",
        tax_id="02.345.678.9-012.000"
    )
    customer = Counterparty(
        id=uuid.uuid4(),
        organization_id=org_id,
        is_customer=True,
        name="PT Logistik Nusantara",
        tax_id="03.456.789.0-123.000"
    )
    db_session.add_all([vendor, customer])
    await db_session.flush()

    project = Project(
        id=uuid.uuid4(),
        organization_id=org_id,
        project_code="PRJ-RC1-001",
        project_name="Pembangunan Warehouse Cikarang",
        customer_id=customer.id,
        original_contract_value=Decimal("500000000.00"),
        revised_contract_value=Decimal("500000000.00"),
        project_status=ProjectStatus.ACTIVE,
        start_date=date(2026, 1, 15)
    )
    db_session.add(project)
    await db_session.flush()

    # 2. Vendor Lifecycle: Bill -> AP -> Payment
    # Bill: Debit 5101 (Biaya Material Proyek) 20,000,000; Credit 2101 (Utang Usaha) 20,000,000
    bill_resp = await client.post(
        "/api/v1/transactions",
        headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)},
        json={
            "transaction_type": "VENDOR_BILL",
            "transaction_date": "2026-02-01",
            "amount": "20000000.00",
            "description": "Pembelian Semen Proyek Cikarang",
            "counterparty_id": str(vendor.id),
            "project_id": str(project.id),
            "lines": [
                {"account_code": "5101", "debit": "20000000.00", "credit": "0.00", "project_id": str(project.id)},
                {"account_code": "2101", "debit": "0.00", "credit": "20000000.00"}
            ]
        }
    )
    assert bill_resp.status_code == 201, bill_resp.text
    bill_id = bill_resp.json()["id"]

    # Approve and Post Vendor Bill
    appr_bill = await client.post(
        f"/api/v1/transactions/{bill_id}/approve",
        headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)}
    )
    assert appr_bill.status_code == 200, appr_bill.text

    # Pay Vendor Bill: Debit 2101 20,000,000; Credit 1102 (Bank Operasional) 20,000,000
    # Use payment account and vendor bill payment flow
    from src.models.payable import VendorBill
    from src.models.coa import PaymentAccount
    pa = await db_session.scalar(
        select(PaymentAccount).where(PaymentAccount.organization_id == org_id).limit(1)
    )
    if not pa:
        from src.services.coa_seeder import seed_standard_payment_accounts
        await seed_standard_payment_accounts(db_session, org_id)
        pa = await db_session.scalar(
            select(PaymentAccount).where(PaymentAccount.organization_id == org_id).limit(1)
        )

    bill_obj = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == uuid.UUID(bill_id)))
    assert bill_obj is not None

    pay_bill_resp = await client.post(
        "/api/v1/vendor-payments",
        headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)},
        json={
            "bill_id": str(bill_obj.id),
            "payment_account_id": str(pa.id),
            "amount": "20000000.00",
            "payment_date": "2026-02-05",
            "reference_no": "VPAY-RC1-001",
            "description": "Pelunasan Semen Proyek Cikarang",
        }
    )
    assert pay_bill_resp.status_code == 201, pay_bill_resp.text

    # 3. Customer Lifecycle: Invoice -> AR -> Payment
    # Customer Invoice: Debit 1201 (Piutang Usaha) 50,000,000; Credit 4101 (Pendapatan Proyek) 50,000,000
    inv_resp = await client.post(
        "/api/v1/transactions",
        headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)},
        json={
            "transaction_type": "CUSTOMER_INVOICE",
            "transaction_date": "2026-02-10",
            "amount": "50000000.00",
            "description": "Tagihan Progress 10% Warehouse",
            "counterparty_id": str(customer.id),
            "project_id": str(project.id),
            "lines": [
                {"account_code": "1201", "debit": "50000000.00", "credit": "0.00"},
                {"account_code": "4101", "debit": "0.00", "credit": "50000000.00", "project_id": str(project.id)}
            ]
        }
    )
    assert inv_resp.status_code == 201, inv_resp.text
    inv_id = inv_resp.json()["id"]

    appr_inv = await client.post(
        f"/api/v1/transactions/{inv_id}/approve",
        headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)}
    )
    assert appr_inv.status_code == 200, appr_inv.text

    # Customer Payment Received: Debit 1102 (Bank Operasional) 50,000,000; Credit 1201 (Piutang Usaha) 50,000,000
    from src.models.receivable import CustomerInvoice
    inv_obj = await db_session.scalar(select(CustomerInvoice).where(CustomerInvoice.transaction_id == uuid.UUID(inv_id)))
    assert inv_obj is not None

    pay_cust_resp = await client.post(
        "/api/v1/customer-payments",
        headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)},
        json={
            "invoice_id": str(inv_obj.id),
            "payment_account_id": str(pa.id),
            "amount": "50000000.00",
            "payment_date": "2026-02-15",
            "reference_no": "PAY-CUST-RC1-001",
            "description": "Penerimaan Termin 1 Warehouse",
        }
    )
    assert pay_cust_resp.status_code == 201, pay_cust_resp.text

    # Verify Money Movements Synchronized
    mm_records = (await db_session.execute(
        select(MoneyMovement).where(MoneyMovement.organization_id == org_id)
    )).scalars().all()
    assert len(mm_records) >= 2, "Money movement records must be created for payment events"
    outflow = next(m for m in mm_records if m.direction == MovementDirection.OUT)
    inflow = next(m for m in mm_records if m.direction == MovementDirection.IN)
    assert outflow.amount == Decimal("20000000.00")
    assert inflow.amount == Decimal("50000000.00")

    # 4. Accounting Period Controls (R7 verification)
    period_svc = AccountingPeriodService(db_session)
    period = await period_svc.create_period(
        organization_id=org_id,
        data=AccountingPeriodCreate(
            period_name="Februari 2026",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28)
        )
    )
    assert period.status == AccountingPeriodStatus.OPEN

    # Close period
    closed_p = await period_svc.update_period_status(
        organization_id=org_id,
        period_id=period.id,
        update_data=AccountingPeriodUpdate(status=AccountingPeriodStatus.CLOSED),
        actor_id=user.id
    )
    assert closed_p.status == AccountingPeriodStatus.CLOSED

    # Attempt backdated posting in closed period -> Must fail
    backdated_resp = await client.post(
        "/api/v1/transactions",
        headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)},
        json={
            "transaction_type": "EXPENSE",
            "transaction_date": "2026-02-20",
            "amount": "1000000.00",
            "description": "Biaya terlambat",
            "lines": [
                {"account_code": "6101", "debit": "1000000.00", "credit": "0.00"},
                {"account_code": "1102", "debit": "0.00", "credit": "1000000.00"}
            ]
        }
    )
    # The transaction creation or approval must be blocked due to closed period
    if backdated_resp.status_code == 201:
        tx_backdated_id = backdated_resp.json()["id"]
        appr_block = await client.post(
            f"/api/v1/transactions/{tx_backdated_id}/approve",
            headers={"X-Organization-Id": str(org_id), "X-User-Id": str(user.id)}
        )
        assert appr_block.status_code in (400, 422, 403, 409), "Approval in closed period must be blocked"
    else:
        assert backdated_resp.status_code in (400, 422, 403, 409), "Creation in closed period must be blocked"

    # 5. Formal Reporting Tie-outs (R9 & Accounting Invariants)
    # Profit & Loss: Revenue 50,000,000 - Cost 20,000,000 = Net Profit 30,000,000
    pnl = await ProfitLossService.get_profit_and_loss(
        session=db_session,
        organization_id=org_id,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28)
    )
    assert pnl.net_profit == Decimal("30000000.00")

    # Balance Sheet:
    # Assets: Bank 1102 net = +50,000,000 - 20,000,000 = +30,000,000
    # Liabilities: 0 (AP settled)
    # Equity: EQ-CY (Net Profit) = 30,000,000
    # Total Assets (30M) == Total Liabilities (0) + Total Equity (30M)
    bs = await BalanceSheetService.get_balance_sheet(
        session=db_session,
        organization_id=org_id,
        as_of_date=date(2026, 2, 28)
    )
    assert bs.total_assets == Decimal("30000000.00")
    assert bs.total_liabilities == Decimal("0.00")
    assert bs.total_equity == Decimal("30000000.00")
    assert bs.is_balanced is True

    # Equity Changes Report
    eq_report = await EquityChangesService.get_equity_changes(
        session=db_session,
        organization_id=org_id,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28)
    )
    assert eq_report.closing_total_equity == Decimal("30000000.00")
    assert eq_report.current_period_net_profit == Decimal("30000000.00")

    # CALK Report
    calk_report = await CALKService.get_calk_report(
        session=db_session,
        organization_id=org_id,
        as_of_date=date(2026, 2, 28)
    )
    assert len(calk_report.accounting_policies) >= 3

    # Cash Flow Statement
    cf = await CashFlowService.get_cash_flow(
        session=db_session,
        organization_id=org_id,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28)
    )
    assert cf.net_cash_change == Decimal("30000000.00")

    # Trial Balance: Total Debits == Total Credits, Difference == 0
    tb = await TrialBalanceService.get_trial_balance(
        session=db_session,
        organization_id=org_id,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28)
    )
    assert tb.is_balanced is True
    assert tb.difference == Decimal("0.00")
    assert tb.total_period_debit == tb.total_period_credit

    # General Ledger: Check 1101 (Kas & Bank)
    gl_bank = await GeneralLedgerService.get_general_ledger(
        session=db_session,
        organization_id=org_id,
        account_code="1101",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28)
    )
    assert gl_bank.closing_balance == Decimal("30000000.00")
    assert gl_bank.total_debit == Decimal("50000000.00")
    assert gl_bank.total_credit == Decimal("20000000.00")

    # AR Aging: Customer has 0 outstanding balance (fully paid)
    ar_aging = await ARAgingService.get_ar_aging(
        session=db_session,
        organization_id=org_id,
        as_of_date=date(2026, 2, 28)
    )
    assert ar_aging.summary.total == Decimal("0.00")

    # AP Aging: Vendor has 0 outstanding balance (fully paid)
    ap_aging = await APAgingService.get_ap_aging(
        session=db_session,
        organization_id=org_id,
        as_of_date=date(2026, 2, 28)
    )
    assert ap_aging.summary.total == Decimal("0.00")

    # Project Profitability: Contract 500M, Rev Recognized 50M, Cost 20M, Gross Profit 30M
    proj_prof = await ProjectReportingService.get_project_profitability(
        session=db_session,
        organization_id=org_id,
        project_id=project.id
    )
    assert proj_prof.revenue_recognized == Decimal("50000000.00")
    assert proj_prof.total_project_cost == Decimal("20000000.00")
    assert proj_prof.gross_profit == Decimal("30000000.00")

    # Project Cash Position: Cash Received 50M, Cash Spent 20M, Net Cash 30M
    proj_cash = await ProjectReportingService.get_project_cash_position(
        session=db_session,
        organization_id=org_id,
        project_id=project.id
    )
    assert proj_cash.cash_received == Decimal("50000000.00")
    assert proj_cash.cash_spent == Decimal("20000000.00")
    assert proj_cash.net_cash_position == Decimal("30000000.00")
    assert proj_cash.is_surplus is True
