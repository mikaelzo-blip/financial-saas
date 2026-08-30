from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, NormalBalance, TransactionType, WorkflowStatus
from src.models.journal import JournalEntry, JournalLine
from src.models.organization import Organization
from src.models.transaction import Transaction


async def seed_cash_profit_ledger(
    session: AsyncSession,
    slug: str,
    revenue: Decimal,
    cost: Decimal = Decimal("0.00"),
) -> Organization:
    org = Organization(slug=slug, legal_name=f"PT {slug.replace('-', ' ').title()}")
    session.add(org)
    await session.flush()
    cash = ChartOfAccount(organization_id=org.id, account_code="1101.01", account_name="Kas dan Bank", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    income = ChartOfAccount(organization_id=org.id, account_code="4101.01", account_name="Pendapatan Proyek", account_type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT, report_group="REVENUE")
    cogs = ChartOfAccount(organization_id=org.id, account_code="5101.01", account_name="Biaya Material", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="COGS")
    session.add_all([cash, income, cogs])
    await session.flush()

    async def post(code, transaction_type, amount, debit_account, credit_account, day):
        transaction = Transaction(organization_id=org.id, transaction_code=f"{slug}-{code}", transaction_type=transaction_type, transaction_date=date(2026, 8, day), amount=amount, description=code, source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
        session.add(transaction)
        await session.flush()
        journal = JournalEntry(organization_id=org.id, entry_number=f"JE-{slug}-{code}", transaction_id=transaction.id, posting_date=date(2026, 8, day), description=code, total_debit=amount, total_credit=amount, is_balanced=True)
        session.add(journal)
        await session.flush()
        session.add_all([
            JournalLine(journal_entry_id=journal.id, line_number=1, account_id=debit_account.id, debit_amount=amount, credit_amount=Decimal("0.00")),
            JournalLine(journal_entry_id=journal.id, line_number=2, account_id=credit_account.id, debit_amount=Decimal("0.00"), credit_amount=amount),
        ])

    await post("REVENUE", TransactionType.CUSTOMER_PAYMENT, revenue, cash, income, 5)
    if cost:
        await post("COST", TransactionType.DIRECT_PURCHASE, cost, cogs, cash, 10)
    await session.commit()
    return org
