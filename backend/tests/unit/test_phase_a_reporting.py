import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.project import Project
from src.models.counterparty import Counterparty
from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import AccountType, NormalBalance, ProjectStatus, TransactionType, WorkflowStatus, DocumentType, DocumentProcessingStatus
from src.models.transaction import Transaction
from src.models.document import Document
from src.models.money_movement import MoneyMovement
from src.services.reporting.dashboard_service import DashboardService


@pytest.mark.asyncio
async def test_phase_a_reporting_endpoints(db_session: AsyncSession):
    org = Organization(slug=f"phase-a-org-{uuid.uuid4().hex[:6]}", legal_name="PT Kontraktor Jaya Sentosa")
    db_session.add(org)
    await db_session.flush()

    # Create Chart of Accounts
    acc_cash = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.01",
        account_name="Kas Utama",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    acc_bank = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.02",
        account_name="Bank BCA Operasional",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    acc_exp = ChartOfAccount(
        organization_id=org.id,
        account_code="5101.01",
        account_name="Biaya Material Langsung",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="Biaya Langsung"
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.01",
        account_name="Pendapatan Jasa Konstruksi",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="Pendapatan Proyek"
    )
    db_session.add_all([acc_cash, acc_bank, acc_exp, acc_rev])
    await db_session.flush()

    # Create Payment Accounts
    pa_cash = PaymentAccount(
        organization_id=org.id,
        coa_account_id=acc_cash.id,
        name="Kas Kantor",
        is_active=True
    )
    pa_bank = PaymentAccount(
        organization_id=org.id,
        coa_account_id=acc_bank.id,
        name="BCA Operasional",
        bank_name="BCA",
        account_number="1234567890",
        is_active=True
    )
    db_session.add_all([pa_cash, pa_bank])
    await db_session.flush()

    # Create Customer & Project
    cust = Counterparty(organization_id=org.id, name="PT Properti Sejahtera", is_customer=True)
    db_session.add(cust)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        customer_id=cust.id,
        project_name="Gedung Perkantoran Tower B",
        project_code="PRJ-2026-001",
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("500000000.00"),
        revised_contract_value=Decimal("500000000.00"),
        variation_order_value=Decimal("0.00")
    )
    db_session.add(project)
    await db_session.flush()

    # Create Transactions & Journal entries
    trx_in = Transaction(
        organization_id=org.id,
        transaction_code="TRX-PA-001",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 3, 1),
        amount=Decimal("150000000.00"),
        description="Termin 1",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    trx_out = Transaction(
        organization_id=org.id,
        transaction_code="TRX-PA-002",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 3, 15),
        amount=Decimal("50000000.00"),
        description="Pembelian Semen & Baja",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add_all([trx_in, trx_out])
    await db_session.flush()

    je_in = JournalEntry(
        organization_id=org.id,
        transaction_id=trx_in.id,
        entry_number="JE-PA-001",
        posting_date=date(2026, 3, 1),
        description="Termin 1",
        total_debit=Decimal("150000000.00"),
        total_credit=Decimal("150000000.00")
    )
    db_session.add(je_in)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je_in.id, account_id=acc_bank.id, debit_amount=Decimal("150000000.00"), credit_amount=Decimal("0.00"), line_number=1),
        JournalLine(journal_entry_id=je_in.id, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("150000000.00"), line_number=2)
    ])

    je_out = JournalEntry(
        organization_id=org.id,
        transaction_id=trx_out.id,
        entry_number="JE-PA-002",
        posting_date=date(2026, 3, 15),
        description="Pembelian Semen & Baja",
        total_debit=Decimal("50000000.00"),
        total_credit=Decimal("50000000.00")
    )
    db_session.add(je_out)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je_out.id, account_id=acc_exp.id, project_id=project.id, debit_amount=Decimal("50000000.00"), credit_amount=Decimal("0.00"), line_number=1),
        JournalLine(journal_entry_id=je_out.id, account_id=acc_bank.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"), line_number=2)
    ])

    # Add a document needing review
    doc = Document(
        organization_id=org.id,
        document_code="DOC-PA-001",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="faktur_semen.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        file_hash=uuid.uuid4().hex,
        storage_path="/tmp/faktur.pdf",
        processing_status=DocumentProcessingStatus.REVIEW_REQUIRED
        )
    db_session.add(doc)

    # Add unmatched money movement
    mm = MoneyMovement(
        organization_id=org.id,
        payment_account_id=pa_bank.id,
        movement_code="MM-PA-001",
        direction="IN",
        amount=Decimal("1000000.00"),
        movement_date=date(2026, 3, 20),
        source_type="BANK_STATEMENT"
    )
    db_session.add(mm)
    await db_session.flush()

    # 1. Test Cash Flow Trend (6 months)
    trend_res = await DashboardService.get_cash_flow_trend(
        session=db_session,
        organization_id=org.id,
        months=6,
        as_of_date=date(2026, 3, 31)
    )
    assert len(trend_res.items) == 6
    march_item = [item for item in trend_res.items if item.period == "2026-03"][0]
    assert march_item.month_label == "Mar 2026"
    assert march_item.cash_in == Decimal("150000000.00")
    assert march_item.cash_out == Decimal("50000000.00")
    assert march_item.net_cash == Decimal("100000000.00")

    # 2. Test Project Performance
    perf_res = await DashboardService.get_project_performance(
        session=db_session,
        organization_id=org.id,
        status_filter=ProjectStatus.ACTIVE
    )
    assert perf_res.total_active_projects == 1
    assert len(perf_res.items) == 1
    p_item = perf_res.items[0]
    assert p_item.project_code == "PRJ-2026-001"
    assert p_item.contract_value == Decimal("500000000.00")
    assert p_item.actual_cost == Decimal("50000000.00")
    assert p_item.gross_profit == Decimal("450000000.00")
    assert p_item.gross_margin_percentage == Decimal("90.0")
    assert p_item.financial_progress_percentage == Decimal("10.0")
    assert p_item.health_status == "NORMAL"
    assert p_item.customer_name == "PT Properti Sejahtera"

    # 3. Test Action Items
    actions_res = await DashboardService.get_action_items(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2026, 3, 31)
    )
    assert actions_res.documents_requires_review == 1
    assert actions_res.documents_failed == 0
    assert actions_res.unmatched_bank_movements == 1
    assert actions_res.total_action_count >= 2

    # 4. Test Cash & Bank Overview
    cb_res = await DashboardService.get_cash_bank_overview(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2026, 3, 31)
    )
    assert len(cb_res.accounts) == 2
    bca_acc = [a for a in cb_res.accounts if a.name == "BCA Operasional"][0]
    assert bca_acc.balance == Decimal("100000000.00")
    assert bca_acc.account_type == "BANK"
    assert bca_acc.last_movement_date == date(2026, 3, 20)
    assert cb_res.total_cash_and_bank == Decimal("100000000.00")
    assert cb_res.unmatched_movements_count == 1


@pytest.mark.asyncio
async def test_phase_a_reporting_empty_dataset(db_session: AsyncSession):
    org = Organization(slug=f"empty-org-{uuid.uuid4().hex[:6]}", legal_name="PT Empty Org")
    db_session.add(org)
    await db_session.flush()

    # 1. Cash flow trend on empty dataset
    trend = await DashboardService.get_cash_flow_trend(
        session=db_session,
        organization_id=org.id,
        months=6,
        as_of_date=date(2026, 3, 31)
    )
    assert len(trend.items) == 6
    for item in trend.items:
        assert item.cash_in == Decimal("0.00")
        assert item.cash_out == Decimal("0.00")
        assert item.net_cash == Decimal("0.00")

    # 2. Project performance on empty dataset
    perf = await DashboardService.get_project_performance(
        session=db_session,
        organization_id=org.id
    )
    assert perf.total_active_projects == 0
    assert perf.total_contract_value == Decimal("0.00")
    assert perf.total_actual_cost == Decimal("0.00")
    assert perf.average_margin_percentage == Decimal("0.00")
    assert len(perf.items) == 0

    # 3. Action items on empty dataset
    actions = await DashboardService.get_action_items(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2026, 3, 31)
    )
    assert actions.total_action_count == 0
    assert actions.documents_requires_review == 0
    assert actions.documents_failed == 0
    assert actions.documents_ready_to_post == 0
    assert actions.unmatched_bank_movements == 0
    assert actions.overdue_ar_count == 0
    assert actions.overdue_ar_amount == Decimal("0.00")
    assert actions.overdue_ap_count == 0
    assert actions.overdue_ap_amount == Decimal("0.00")
    assert actions.projects_with_warning == 0

    # 4. Cash & bank overview on empty dataset
    cb = await DashboardService.get_cash_bank_overview(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2026, 3, 31)
    )
    assert cb.total_cash_and_bank == Decimal("0.00")
    assert cb.total_bank == Decimal("0.00")
    assert cb.total_cash == Decimal("0.00")
    assert cb.unmatched_movements_count == 0
    assert cb.unmatched_amount == Decimal("0.00")
    assert len(cb.accounts) == 0


@pytest.mark.asyncio
async def test_phase_a_reporting_tenant_isolation(db_session: AsyncSession):
    org1 = Organization(slug=f"iso1-{uuid.uuid4().hex[:6]}", legal_name="PT Org Satu")
    org2 = Organization(slug=f"iso2-{uuid.uuid4().hex[:6]}", legal_name="PT Org Dua")
    db_session.add_all([org1, org2])
    await db_session.flush()

    # Add data to Org 1 only
    acc1 = ChartOfAccount(
        organization_id=org1.id,
        account_code="1101.01",
        account_name="Kas Org 1",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    db_session.add(acc1)
    await db_session.flush()

    pa1 = PaymentAccount(
        organization_id=org1.id,
        coa_account_id=acc1.id,
        name="Kas Kantor Org 1",
        is_active=True
    )
    db_session.add(pa1)

    cust1 = Counterparty(organization_id=org1.id, name="Customer Org 1", is_customer=True)
    db_session.add(cust1)
    await db_session.flush()

    proj1 = Project(
        organization_id=org1.id,
        customer_id=cust1.id,
        project_name="Proyek Org 1",
        project_code="PRJ-ISO-01",
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00"),
        variation_order_value=Decimal("0.00")
    )
    db_session.add(proj1)
    await db_session.flush()

    # Query Org 2: Should observe ZERO data from Org 1
    trend2 = await DashboardService.get_cash_flow_trend(
        session=db_session,
        organization_id=org2.id,
        months=6,
        as_of_date=date(2026, 3, 31)
    )
    for item in trend2.items:
        assert item.cash_in == Decimal("0.00")
        assert item.cash_out == Decimal("0.00")

    perf2 = await DashboardService.get_project_performance(
        session=db_session,
        organization_id=org2.id
    )
    assert perf2.total_active_projects == 0
    assert len(perf2.items) == 0

    cb2 = await DashboardService.get_cash_bank_overview(
        session=db_session,
        organization_id=org2.id
    )
    assert cb2.total_cash_and_bank == Decimal("0.00")
    assert len(cb2.accounts) == 0


@pytest.mark.asyncio
async def test_phase_a_cash_flow_net_neutral_internal_transfers(db_session: AsyncSession):
    org = Organization(slug=f"transfers-org-{uuid.uuid4().hex[:6]}", legal_name="PT Transfer Neutrality")
    db_session.add(org)
    await db_session.flush()

    # Cash & Bank accounts (1101%)
    acc_bank_a = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.01",
        account_name="Bank BCA",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    acc_bank_b = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.02",
        account_name="Bank Mandiri",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    # Non-cash accounts
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.01",
        account_name="Pendapatan Jasa",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="Pendapatan"
    )
    acc_exp = ChartOfAccount(
        organization_id=org.id,
        account_code="5101.01",
        account_name="Biaya Operasional",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="Biaya"
    )
    acc_bank_fee = ChartOfAccount(
        organization_id=org.id,
        account_code="5102.01",
        account_name="Biaya Administrasi Bank",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="Biaya"
    )
    acc_equity = ChartOfAccount(
        organization_id=org.id,
        account_code="3101.01",
        account_name="Modal Disetor Pemilik",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="Ekuitas"
    )
    db_session.add_all([acc_bank_a, acc_bank_b, acc_rev, acc_exp, acc_bank_fee, acc_equity])
    await db_session.flush()

    # 1. Customer payment (External inflow: non-cash -> cash): +100,000,000
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-NN-001",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 3, 5),
        amount=Decimal("100000000.00"),
        description="Penerimaan pembayaran piutang customer",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx1)
    await db_session.flush()
    je1 = JournalEntry(
        organization_id=org.id,
        transaction_id=trx1.id,
        entry_number="JE-NN-001",
        posting_date=date(2026, 3, 5),
        description="Penerimaan pembayaran piutang customer",
        total_debit=Decimal("100000000.00"),
        total_credit=Decimal("100000000.00")
    )
    db_session.add(je1)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je1.id, account_id=acc_bank_a.id, debit_amount=Decimal("100000000.00"), credit_amount=Decimal("0.00"), line_number=1),
        JournalLine(journal_entry_id=je1.id, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000000.00"), line_number=2)
    ])

    # 2. Vendor payment (External outflow: cash -> non-cash): -40,000,000
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-NN-002",
        transaction_type=TransactionType.PAY_VENDOR_BILL,
        transaction_date=date(2026, 3, 10),
        amount=Decimal("40000000.00"),
        description="Pembayaran utang vendor",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx2)
    await db_session.flush()
    je2 = JournalEntry(
        organization_id=org.id,
        transaction_id=trx2.id,
        entry_number="JE-NN-002",
        posting_date=date(2026, 3, 10),
        description="Pembayaran utang vendor",
        total_debit=Decimal("40000000.00"),
        total_credit=Decimal("40000000.00")
    )
    db_session.add(je2)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je2.id, account_id=acc_exp.id, debit_amount=Decimal("40000000.00"), credit_amount=Decimal("0.00"), line_number=1),
        JournalLine(journal_entry_id=je2.id, account_id=acc_bank_a.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("40000000.00"), line_number=2)
    ])

    # 3. Bank charge (External outflow: cash -> non-cash): -15,000
    trx3 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-NN-003",
        transaction_type=TransactionType.BANK_CHARGE,
        transaction_date=date(2026, 3, 12),
        amount=Decimal("15000.00"),
        description="Biaya administrasi bank bulanan",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx3)
    await db_session.flush()
    je3 = JournalEntry(
        organization_id=org.id,
        transaction_id=trx3.id,
        entry_number="JE-NN-003",
        posting_date=date(2026, 3, 12),
        description="Biaya administrasi bank bulanan",
        total_debit=Decimal("15000.00"),
        total_credit=Decimal("15000.00")
    )
    db_session.add(je3)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je3.id, account_id=acc_bank_fee.id, debit_amount=Decimal("15000.00"), credit_amount=Decimal("0.00"), line_number=1),
        JournalLine(journal_entry_id=je3.id, account_id=acc_bank_a.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("15000.00"), line_number=2)
    ])

    # 4. Owner contribution / loan (External inflow: non-cash -> cash): +50,000,000
    trx4 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-NN-004",
        transaction_type=TransactionType.OWNER_CONTRIBUTION,
        transaction_date=date(2026, 3, 15),
        amount=Decimal("50000000.00"),
        description="Setoran modal pemilik",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx4)
    await db_session.flush()
    je4 = JournalEntry(
        organization_id=org.id,
        transaction_id=trx4.id,
        entry_number="JE-NN-004",
        posting_date=date(2026, 3, 15),
        description="Setoran modal pemilik",
        total_debit=Decimal("50000000.00"),
        total_credit=Decimal("50000000.00")
    )
    db_session.add(je4)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je4.id, account_id=acc_bank_b.id, debit_amount=Decimal("50000000.00"), credit_amount=Decimal("0.00"), line_number=1),
        JournalLine(journal_entry_id=je4.id, account_id=acc_equity.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"), line_number=2)
    ])

    # 5. Internal transfer (Internal transfer: cash -> cash): 25,000,000 Bank A -> Bank B
    # Must be NET NEUTRAL: must NOT increase cash_in or cash_out at company level
    trx5 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-NN-005",
        transaction_type=TransactionType.INTERBANK_TRANSFER,
        transaction_date=date(2026, 3, 20),
        amount=Decimal("25000000.00"),
        description="Pemindahan dana dari Bank BCA ke Bank Mandiri",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx5)
    await db_session.flush()
    je5 = JournalEntry(
        organization_id=org.id,
        transaction_id=trx5.id,
        entry_number="JE-NN-005",
        posting_date=date(2026, 3, 20),
        description="Pemindahan dana dari Bank BCA ke Bank Mandiri",
        total_debit=Decimal("25000000.00"),
        total_credit=Decimal("25000000.00")
    )
    db_session.add(je5)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je5.id, account_id=acc_bank_b.id, debit_amount=Decimal("25000000.00"), credit_amount=Decimal("0.00"), line_number=1),
        JournalLine(journal_entry_id=je5.id, account_id=acc_bank_a.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("25000000.00"), line_number=2)
    ])

    await db_session.flush()

    # Query cash flow trend for March 2026
    trend_res = await DashboardService.get_cash_flow_trend(
        session=db_session,
        organization_id=org.id,
        months=1,
        as_of_date=date(2026, 3, 31)
    )
    assert len(trend_res.items) == 1
    march_item = trend_res.items[0]

    # Cash In: 100,000,000 (customer payment) + 50,000,000 (owner contribution) = 150,000,000
    # Must NOT include 25,000,000 from internal transfer!
    assert march_item.cash_in == Decimal("150000000.00")

    # Cash Out: 40,000,000 (vendor bill) + 15,000 (bank fee) = 40,015,000
    # Must NOT include 25,000,000 from internal transfer!
    assert march_item.cash_out == Decimal("40015000.00")

    # Net Cash: 150,000,000 - 40,015,000 = 109,985,000
    assert march_item.net_cash == Decimal("109985000.00")

    # Also verify get_dashboard_summary MTD numbers
    summary_res = await DashboardService.get_dashboard_summary(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2026, 3, 31)
    )
    assert summary_res.cash_in_period == Decimal("150000000.00")
    assert summary_res.cash_out_period == Decimal("40015000.00")
    assert summary_res.net_cash_flow == Decimal("109985000.00")
