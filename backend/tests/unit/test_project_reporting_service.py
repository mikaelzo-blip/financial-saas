import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import AccountType, NormalBalance, CostCategory, ProjectStatus, TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.reporting.project_reporting_service import ProjectReportingService


@pytest.mark.asyncio
async def test_project_profitability_and_cash_position(db_session: AsyncSession):
    org = Organization(slug="pt-proj-test", legal_name="PT Project Report Test")
    db_session.add(org)
    await db_session.flush()

    client = Counterparty(organization_id=org.id, name="Klien Proyek A", is_customer=True)
    db_session.add(client)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-REP-001",
        project_name="Proyek Gedung Serbaguna",
        customer_id=client.id,
        project_status=ProjectStatus.ACTIVE,
        po_spk_no="SPK-001",
        original_contract_value=Decimal("500000000.00"),
        variation_order_value=Decimal("0.00"),
        revised_contract_value=Decimal("500000000.00"),
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 12, 31)
    )
    db_session.add(proj)
    await db_session.flush()

    # Accounts
    acc_kas = ChartOfAccount(organization_id=org.id, account_code="1101.01", account_name="Kas", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc_mat = ChartOfAccount(organization_id=org.id, account_code="5101.01", account_name="Bahan", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="COGS")
    acc_lab = ChartOfAccount(organization_id=org.id, account_code="5103.01", account_name="Upah", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="COGS")
    db_session.add_all([acc_kas, acc_mat, acc_lab])
    await db_session.flush()

    # 1. Invoiced: 200M (Paid: 150M)
    inv = CustomerInvoice(
        organization_id=org.id,
        customer_id=client.id,
        project_id=proj.id,
        invoice_code="INV-PRJ-01",
        invoice_date=date(2026, 2, 1),
        due_date=date(2026, 3, 1),
        total_amount=Decimal("200000000.00"),
        status="PARTIAL"
    )
    db_session.add(inv)
    await db_session.flush()

    trx_pay = Transaction(
        organization_id=org.id,
        transaction_code="TRX-REC-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 2, 10),
        amount=Decimal("150000000.00"),
        description="Termin Proyek",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx_pay)
    await db_session.flush()

    alloc = CustomerPaymentAllocation(
        invoice_id=inv.id,
        payment_transaction_id=trx_pay.id,
        allocated_amount=Decimal("150000000.00")
    )
    db_session.add(alloc)
    await db_session.flush()

    cancelled_inv = CustomerInvoice(
        organization_id=org.id,
        customer_id=client.id,
        project_id=proj.id,
        invoice_code="INV-PRJ-CANCELLED",
        invoice_date=date(2026, 2, 2),
        due_date=date(2026, 3, 2),
        total_amount=Decimal("900000000.00"),
        status="CANCELLED"
    )
    db_session.add(cancelled_inv)
    await db_session.flush()

    # 2. Direct Costs: Material 60M (Dr Material, Cr Kas), Labor 40M (Dr Labor, Cr Kas)
    trx1 = Transaction(organization_id=org.id, transaction_code="TRX-MAT-01", transaction_type=TransactionType.DIRECT_PURCHASE, transaction_date=date(2026, 2, 5), amount=Decimal("60000000.00"), description="Material", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    trx2 = Transaction(organization_id=org.id, transaction_code="TRX-LAB-01", transaction_type=TransactionType.DIRECT_PURCHASE, transaction_date=date(2026, 2, 10), amount=Decimal("40000000.00"), description="Upah", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add_all([trx1, trx2])
    await db_session.flush()

    je1 = JournalEntry(organization_id=org.id, entry_number="JE-MAT-01", transaction_id=trx1.id, posting_date=date(2026, 2, 5), description="Material", total_debit=Decimal("60000000.00"), total_credit=Decimal("60000000.00"), is_balanced=True)
    je2 = JournalEntry(organization_id=org.id, entry_number="JE-LAB-01", transaction_id=trx2.id, posting_date=date(2026, 2, 10), description="Labor", total_debit=Decimal("40000000.00"), total_credit=Decimal("40000000.00"), is_balanced=True)
    db_session.add_all([je1, je2])
    await db_session.flush()

    jl1_1 = JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc_mat.id, debit_amount=Decimal("60000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id, cost_category=CostCategory.MAT)
    jl1_2 = JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("60000000.00"), project_id=proj.id)

    jl2_1 = JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc_lab.id, debit_amount=Decimal("40000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id, cost_category=CostCategory.LAB)
    jl2_2 = JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("40000000.00"), project_id=proj.id)
    db_session.add_all([jl1_1, jl1_2, jl2_1, jl2_2])
    await db_session.commit()

    # Query Profitability
    prof = await ProjectReportingService.get_project_profitability(db_session, org.id, proj.id)
    assert prof.revenue_recognized == Decimal("200000000.00")
    assert prof.total_project_cost == Decimal("100000000.00")
    assert prof.gross_profit == Decimal("100000000.00")
    assert prof.gross_margin_percentage == Decimal("50.00")

    # Query Cash Position
    cash_pos = await ProjectReportingService.get_project_cash_position(db_session, org.id, proj.id)
    assert cash_pos.invoiced_amount == Decimal("200000000.00")
    assert cash_pos.cash_received == Decimal("150000000.00")
    assert cash_pos.receivable_outstanding == Decimal("50000000.00")
    assert cash_pos.cash_spent == Decimal("100000000.00")
    assert cash_pos.net_cash_position == Decimal("50000000.00")
    assert cash_pos.is_surplus is True


@pytest.mark.asyncio
async def test_project_reporting_loan_principal_and_tax_invariants(db_session: AsyncSession):
    """
    Invariants tested:
    1. Loan principal payment affects project cash position (cash spent), but NEVER project profit or direct cost.
    2. PPh withheld (creditable) affects cash/receivable, but does NOT reduce Gross Project Profit.
    3. Project Net Contribution calculates: Gross Profit - Project Fee - Bank Interest - Final Tax.
    4. Help texts conform to owner friendly policy.
    """
    org = Organization(slug="pt-invariants-test", legal_name="PT Invariant Test")
    db_session.add(org)
    await db_session.flush()

    client = Counterparty(organization_id=org.id, name="Klien Invariant Proyek", is_customer=True)
    db_session.add(client)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-INV-001",
        project_name="Proyek Tower Komersial",
        customer_id=client.id,
        project_status=ProjectStatus.ACTIVE,
        po_spk_no="SPK-INV-001",
        original_contract_value=Decimal("1000000000.00"),
        variation_order_value=Decimal("0.00"),
        revised_contract_value=Decimal("1000000000.00"),
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 12, 31)
    )
    db_session.add(proj)
    await db_session.flush()

    # Accounts
    acc_kas = ChartOfAccount(organization_id=org.id, account_code="1101.01", account_name="Kas & Bank", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc_ar = ChartOfAccount(organization_id=org.id, account_code="1201.01", account_name="Piutang Usaha", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc_pph_prepaid = ChartOfAccount(organization_id=org.id, account_code="1108.01", account_name="Uang Muka Pajak PPh 23", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc_loan = ChartOfAccount(organization_id=org.id, account_code="2501.01", account_name="Utang Bank / Pinjaman", account_type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT, report_group="LONG_TERM_LIABILITIES")
    acc_cogs_mat = ChartOfAccount(organization_id=org.id, account_code="5101.01", account_name="Biaya Material Proyek", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="COGS")
    acc_fee = ChartOfAccount(organization_id=org.id, account_code="6108.01", account_name="Fee Konsultan Proyek", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="OPEX")
    acc_interest = ChartOfAccount(organization_id=org.id, account_code="7101.01", account_name="Beban Bunga Pinjaman Proyek", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="OTHER_EXPENSE")
    acc_pph_final = ChartOfAccount(organization_id=org.id, account_code="8101.01", account_name="PPh Final Jasa Konstruksi", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="INCOME_TAX")
    db_session.add_all([acc_kas, acc_ar, acc_pph_prepaid, acc_loan, acc_cogs_mat, acc_fee, acc_interest, acc_pph_final])
    await db_session.flush()

    # 1. Invoice: 400M (Customer paid 388M cash + 12M PPh 23 withheld by client)
    inv = CustomerInvoice(
        organization_id=org.id,
        customer_id=client.id,
        project_id=proj.id,
        invoice_code="INV-INV-01",
        invoice_date=date(2026, 3, 1),
        due_date=date(2026, 4, 1),
        total_amount=Decimal("400000000.00"),
        status="PAID"
    )
    db_session.add(inv)
    await db_session.flush()

    trx_pay = Transaction(
        organization_id=org.id,
        transaction_code="TRX-INVPAY-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 3, 15),
        amount=Decimal("388000000.00"),
        description="Pembayaran termin potong PPh 23",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx_pay)
    await db_session.flush()

    alloc = CustomerPaymentAllocation(
        invoice_id=inv.id,
        payment_transaction_id=trx_pay.id,
        allocated_amount=Decimal("388000000.00")
    )
    db_session.add(alloc)
    await db_session.flush()

    # Journal: Dr Kas 388M, Dr PPh 23 (Prepaid) 12M, Cr Piutang 400M
    je_pay = JournalEntry(
        organization_id=org.id,
        entry_number="JE-PAY-01",
        transaction_id=trx_pay.id,
        posting_date=date(2026, 3, 15),
        description="Customer Payment with PPh 23 withheld",
        total_debit=Decimal("400000000.00"),
        total_credit=Decimal("400000000.00"),
        is_balanced=True
    )
    db_session.add(je_pay)
    await db_session.flush()

    jl_pay1 = JournalLine(journal_entry_id=je_pay.id, line_number=1, account_id=acc_kas.id, debit_amount=Decimal("388000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id)
    jl_pay2 = JournalLine(journal_entry_id=je_pay.id, line_number=2, account_id=acc_pph_prepaid.id, debit_amount=Decimal("12000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id)
    jl_pay3 = JournalLine(journal_entry_id=je_pay.id, line_number=3, account_id=acc_ar.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("400000000.00"), project_id=proj.id)
    db_session.add_all([jl_pay1, jl_pay2, jl_pay3])
    await db_session.flush()

    # 2. Direct Material COGS: 200M (Dr Material COGS, Cr Kas)
    trx_mat = Transaction(organization_id=org.id, transaction_code="TRX-MAT-02", transaction_type=TransactionType.DIRECT_PURCHASE, transaction_date=date(2026, 3, 5), amount=Decimal("200000000.00"), description="Material Beton", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add(trx_mat)
    await db_session.flush()

    je_mat = JournalEntry(organization_id=org.id, entry_number="JE-MAT-02", transaction_id=trx_mat.id, posting_date=date(2026, 3, 5), description="Beli Material", total_debit=Decimal("200000000.00"), total_credit=Decimal("200000000.00"), is_balanced=True)
    db_session.add(je_mat)
    await db_session.flush()

    jl_m1 = JournalLine(journal_entry_id=je_mat.id, line_number=1, account_id=acc_cogs_mat.id, debit_amount=Decimal("200000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id, cost_category=CostCategory.MAT)
    jl_m2 = JournalLine(journal_entry_id=je_mat.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("200000000.00"), project_id=proj.id)
    db_session.add_all([jl_m1, jl_m2])
    await db_session.flush()

    # 3. Loan Principal Repayment: 50M (Dr Utang Bank 2501, Cr Kas 1101) - Must NOT be in Direct Costs or P&L!
    trx_loan = Transaction(organization_id=org.id, transaction_code="TRX-LOAN-01", transaction_type=TransactionType.LOAN_PAYMENT, transaction_date=date(2026, 3, 20), amount=Decimal("50000000.00"), description="Bayar Pokok Pinjaman Alat Proyek", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add(trx_loan)
    await db_session.flush()

    je_loan = JournalEntry(organization_id=org.id, entry_number="JE-LOAN-01", transaction_id=trx_loan.id, posting_date=date(2026, 3, 20), description="Bayar Pokok Pinjaman", total_debit=Decimal("50000000.00"), total_credit=Decimal("50000000.00"), is_balanced=True)
    db_session.add(je_loan)
    await db_session.flush()

    jl_l1 = JournalLine(journal_entry_id=je_loan.id, line_number=1, account_id=acc_loan.id, debit_amount=Decimal("50000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id)
    jl_l2 = JournalLine(journal_entry_id=je_loan.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"), project_id=proj.id)
    db_session.add_all([jl_l1, jl_l2])
    await db_session.flush()

    # 4. Secondary management costs: Fee Proyek (5M), Bunga Pinjaman (3M), PPh Final (7M)
    trx_sec = Transaction(organization_id=org.id, transaction_code="TRX-SEC-01", transaction_type=TransactionType.OTHER_EXPENSE, transaction_date=date(2026, 3, 25), amount=Decimal("15000000.00"), description="Biaya Bunga Fee dan Pajak", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add(trx_sec)
    await db_session.flush()

    je_sec = JournalEntry(organization_id=org.id, entry_number="JE-SEC-01", transaction_id=trx_sec.id, posting_date=date(2026, 3, 25), description="Biaya Sekunder Proyek", total_debit=Decimal("15000000.00"), total_credit=Decimal("15000000.00"), is_balanced=True)
    db_session.add(je_sec)
    await db_session.flush()

    jl_s1 = JournalLine(journal_entry_id=je_sec.id, line_number=1, account_id=acc_fee.id, debit_amount=Decimal("5000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id)
    jl_s2 = JournalLine(journal_entry_id=je_sec.id, line_number=2, account_id=acc_interest.id, debit_amount=Decimal("3000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id)
    jl_s3 = JournalLine(journal_entry_id=je_sec.id, line_number=3, account_id=acc_pph_final.id, debit_amount=Decimal("7000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id)
    jl_s4 = JournalLine(journal_entry_id=je_sec.id, line_number=4, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("15000000.00"), project_id=proj.id)
    db_session.add_all([jl_s1, jl_s2, jl_s3, jl_s4])
    await db_session.commit()

    # Query Profitability
    prof = await ProjectReportingService.get_project_profitability(db_session, org.id, proj.id)
    
    # 1. Invoiced Revenue: 400M
    assert prof.invoiced_amount == Decimal("400000000.00")
    # 2. Direct Project Cost: Material 200M (Loan repayment 50M is NEVER expense!)
    assert prof.direct_project_cost == Decimal("200000000.00")
    assert prof.total_project_cost == Decimal("200000000.00")
    # 3. Gross Project Profit = 400M - 200M = 200M (PPh Withheld 12M does NOT reduce gross profit)
    assert prof.gross_project_profit == Decimal("200000000.00")
    assert prof.gross_profit == Decimal("200000000.00")
    assert prof.gross_margin == Decimal("50.00")

    # 4. Secondary Management Metrics
    assert prof.pph_withheld == Decimal("12000000.00")
    assert prof.project_fee == Decimal("5000000.00")
    assert prof.bank_charges == Decimal("3000000.00")
    assert prof.pph_final == Decimal("7000000.00")
    assert prof.loan_principal_paid == Decimal("50000000.00")
    assert prof.has_net_contribution_data is True
    # Project Net Contribution = 200M - 5M - 3M - 7M = 185M
    assert prof.project_net_contribution == Decimal("185000000.00")

    # 5. Tooltip help texts exist and match policy
    assert "laba_kotor_proyek" in prof.help_texts
    assert "pokok_pinjaman" in prof.help_texts
    assert "pph_dipotong" in prof.help_texts

    # Query Cash Position
    cash_pos = await ProjectReportingService.get_project_cash_position(db_session, org.id, proj.id)
    assert cash_pos.invoiced_amount == Decimal("400000000.00")
    assert cash_pos.cash_received == Decimal("388000000.00")
    assert cash_pos.receivable_outstanding == Decimal("12000000.00")  # remaining unpaid or tax offset
    # Total Cash Spent: Material 200M + Loan Principal 50M + Secondary 15M = 265M
    assert cash_pos.cash_spent == Decimal("265000000.00")
    # Net Cash Position = 388M - 265M = 123M
    assert cash_pos.net_cash_position == Decimal("123000000.00")
    assert cash_pos.is_surplus is True

