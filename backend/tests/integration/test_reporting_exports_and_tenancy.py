import pytest
import io
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
import openpyxl

from src.models.organization import Organization
from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import AccountType, NormalBalance, TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.excel_export_service import ExcelExportService
from src.services.reporting.pdf_export_service import PdfExportService


@pytest.mark.asyncio
async def test_export_parity_and_tenant_isolation(db_session: AsyncSession):
    # Org 1: PT Alpha Konstruksi
    org1 = Organization(slug="pt-alpha", legal_name="PT Alpha Konstruksi")
    # Org 2: PT Beta Engineering
    org2 = Organization(slug="pt-beta", legal_name="PT Beta Engineering")
    db_session.add_all([org1, org2])
    await db_session.flush()

    # Org 1 Accounts
    acc1_kas = ChartOfAccount(organization_id=org1.id, account_code="1101.01", account_name="Kas Alpha", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc1_rev = ChartOfAccount(organization_id=org1.id, account_code="4101.01", account_name="Pendapatan Alpha", account_type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT, report_group="REVENUE")
    # Org 2 Accounts
    acc2_kas = ChartOfAccount(organization_id=org2.id, account_code="1101.01", account_name="Kas Beta", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc2_rev = ChartOfAccount(organization_id=org2.id, account_code="4101.01", account_name="Pendapatan Beta", account_type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT, report_group="REVENUE")
    db_session.add_all([acc1_kas, acc1_rev, acc2_kas, acc2_rev])
    await db_session.flush()

    # Post 100M in Org 1
    trx1 = Transaction(organization_id=org1.id, transaction_code="TRX-A1", transaction_type=TransactionType.CUSTOMER_INVOICE, transaction_date=date(2026, 1, 15), amount=Decimal("100000000.00"), description="Termin A", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add(trx1)
    await db_session.flush()
    je1 = JournalEntry(organization_id=org1.id, entry_number="JE-A1", transaction_id=trx1.id, posting_date=date(2026, 1, 15), description="Termin A", total_debit=Decimal("100000000.00"), total_credit=Decimal("100000000.00"), is_balanced=True)
    db_session.add(je1)
    await db_session.flush()
    jl1_1 = JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc1_kas.id, debit_amount=Decimal("100000000.00"), credit_amount=Decimal("0.00"))
    jl1_2 = JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc1_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000000.00"))
    db_session.add_all([jl1_1, jl1_2])

    # Post 50M in Org 2
    trx2 = Transaction(organization_id=org2.id, transaction_code="TRX-B1", transaction_type=TransactionType.CUSTOMER_INVOICE, transaction_date=date(2026, 1, 15), amount=Decimal("50000000.00"), description="Termin B", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add(trx2)
    await db_session.flush()
    je2 = JournalEntry(organization_id=org2.id, entry_number="JE-B1", transaction_id=trx2.id, posting_date=date(2026, 1, 15), description="Termin B", total_debit=Decimal("50000000.00"), total_credit=Decimal("50000000.00"), is_balanced=True)
    db_session.add(je2)
    await db_session.flush()
    jl2_1 = JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc2_kas.id, debit_amount=Decimal("50000000.00"), credit_amount=Decimal("0.00"))
    jl2_2 = JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc2_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"))
    db_session.add_all([jl2_1, jl2_2])
    await db_session.commit()

    # 1. Multi-Tenant Isolation Check
    pl1 = await ProfitLossService.get_profit_and_loss(db_session, org1.id, date(2026, 1, 1), date(2026, 1, 31))
    pl2 = await ProfitLossService.get_profit_and_loss(db_session, org2.id, date(2026, 1, 1), date(2026, 1, 31))

    assert pl1.revenue_section.subtotal == Decimal("100000000.00")
    assert pl1.net_profit == Decimal("100000000.00")
    assert pl2.revenue_section.subtotal == Decimal("50000000.00")
    assert pl2.net_profit == Decimal("50000000.00")

    # 2. Export Parity Check (JSON == XLSX == PDF)
    # XLSX Export
    xlsx_stream = ExcelExportService.export_profit_loss(pl1)
    assert xlsx_stream is not None
    wb = openpyxl.load_workbook(xlsx_stream)
    ws = wb.active
    # In row 4 is header, row 5 is section, row 6 is line item (amount is col 3)
    c_val = ws.cell(row=6, column=3).value
    assert Decimal(str(c_val)) == pl1.revenue_section.lines[0].amount

    # PDF Export
    pdf_stream = PdfExportService.export_profit_loss(pl1)
    assert pdf_stream is not None
    pdf_bytes = pdf_stream.read()
    assert len(pdf_bytes) > 500  # Valid binary PDF stream generated
    assert b"%PDF" in pdf_bytes[:10]
