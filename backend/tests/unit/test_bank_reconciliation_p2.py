import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import AccountType, NormalBalance, ReconciliationStatus
from src.services.bank_reconciliation_service import BankReconciliationService
from src.schemas.bank_reconciliation import BankReconciliationMatchRequest
from src.core.exceptions import DuplicateEntityException


@pytest.mark.asyncio
async def test_bank_statement_import_and_duplicate_prevention(db_session: AsyncSession):
    service = BankReconciliationService(db_session)

    org = Organization(slug=f"recon-org-{uuid.uuid4().hex[:6]}", legal_name="Recon Test PT")
    db_session.add(org)
    await db_session.flush()

    coa_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Aset Lancar",
        is_active=True
    )
    db_session.add(coa_1101)
    await db_session.flush()

    bank_acc = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="BCA Operasional",
        bank_name="BCA",
        account_number="1234567890",
        is_active=True
    )
    db_session.add(bank_acc)
    await db_session.flush()

    csv_data = (
        "date,description,debit,credit,balance,reference\n"
        "2026-03-01,Transfer Masuk Termyn 1,0.00,50000000.00,50000000.00,REF-001\n"
        "2026-03-02,Biaya Material Semen,15000000.00,0.00,35000000.00,REF-002\n"
    ).encode("utf-8")

    # 1. First import succeeds
    stmt_import = await service.import_statement(
        organization_id=org.id,
        payment_account_id=bank_acc.id,
        source_file="bca_statement.csv",
        file_content=csv_data,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 2)
    )
    assert stmt_import.id is not None
    assert len(stmt_import.lines) == 2
    assert stmt_import.lines[0].credit == Decimal("50000000.00")
    assert stmt_import.lines[1].debit == Decimal("15000000.00")
    assert stmt_import.lines[0].reconciliation_status == ReconciliationStatus.UNMATCHED_BANK

    # 2. Duplicate import is strictly blocked
    with pytest.raises(DuplicateEntityException):
        await service.import_statement(
            organization_id=org.id,
            payment_account_id=bank_acc.id,
            source_file="bca_statement_duplicate.csv",
            file_content=csv_data
        )


@pytest.mark.asyncio
async def test_cash_completeness_dashboard_and_reconciliation(db_session: AsyncSession):
    service = BankReconciliationService(db_session)

    org = Organization(slug=f"recon-dash-{uuid.uuid4().hex[:6]}", legal_name="Recon Dashboard PT")
    db_session.add(org)
    await db_session.flush()

    coa_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Aset Lancar",
        is_active=True
    )
    db_session.add(coa_1101)
    await db_session.flush()

    bank_acc = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="Mandiri Rekon",
        bank_name="MANDIRI",
        account_number="9876543210",
        is_active=True
    )
    db_session.add(bank_acc)
    await db_session.flush()

    csv_data = (
        "date,description,debit,credit,balance,reference\n"
        "2026-03-05,Penerimaan Pembayaran,0.00,20000000.00,20000000.00,REF-INV-10\n"
    ).encode("utf-8")

    stmt_import = await service.import_statement(
        organization_id=org.id,
        payment_account_id=bank_acc.id,
        source_file="mandiri_statement.csv",
        file_content=csv_data
    )

    line = stmt_import.lines[0]

    # Check dashboard before match
    dash_before = await service.get_cash_completeness_dashboard(org.id, payment_account_id=bank_acc.id)
    assert dash_before.total_bank_inflow == Decimal("20000000.00")
    assert dash_before.matched_amount == Decimal("0.00")
    assert dash_before.unmatched_bank_amount == Decimal("20000000.00")

    # Perform manual match
    reconcil = await service.match_manual(
        organization_id=org.id,
        req=BankReconciliationMatchRequest(
            statement_line_id=line.id,
            matched_amount=Decimal("20000000.00"),
            notes="Matched with client transfer"
        )
    )
    assert reconcil.id is not None
    assert reconcil.status == ReconciliationStatus.MATCHED

    # Check dashboard after match
    dash_after = await service.get_cash_completeness_dashboard(org.id, payment_account_id=bank_acc.id)
    assert dash_after.matched_amount == Decimal("20000000.00")
    assert dash_after.unmatched_bank_amount == Decimal("0.00")
    assert dash_after.completeness_percentage == Decimal("100.00")
