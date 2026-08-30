import uuid
from typing import List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import AccountType, NormalBalance
from src.models.coa import ChartOfAccount, PaymentAccount

# Standard Master COA seed definition from Master Financial Concept
STANDARD_COA_DEFINITIONS: List[Dict[str, Any]] = [
    # 1xxx Assets
    {
        "account_code": "1101",
        "account_name": "Kas dan Bank",
        "account_type": AccountType.ASSET,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Kas & Setara Kas"
    },
    {
        "account_code": "1201",
        "account_name": "Piutang Usaha",
        "account_type": AccountType.ASSET,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Piutang Usaha"
    },
    {
        "account_code": "1301",
        "account_name": "Uang Muka Biaya & Vendor",
        "account_type": AccountType.ASSET,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Uang Muka"
    },
    {
        "account_code": "1401",
        "account_name": "Persediaan Material & Perlengkapan Proyek",
        "account_type": AccountType.ASSET,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Persediaan"
    },
    {
        "account_code": "1501",
        "account_name": "Aset Tetap Operasional",
        "account_type": AccountType.ASSET,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Aset Tetap"
    },
    {
        "account_code": "1502",
        "account_name": "Akumulasi Penyusutan Aset Tetap",
        "account_type": AccountType.ASSET,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Aset Tetap"
    },

    # 2xxx Liabilities
    {
        "account_code": "2101",
        "account_name": "Utang Usaha",
        "account_type": AccountType.LIABILITY,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Utang Usaha"
    },
    {
        "account_code": "2201",
        "account_name": "Uang Muka Customer",
        "account_type": AccountType.LIABILITY,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Uang Muka Customer"
    },
    {
        "account_code": "2301",
        "account_name": "Utang Pajak",
        "account_type": AccountType.LIABILITY,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Utang Pajak"
    },
    {
        "account_code": "2401",
        "account_name": "Utang Biaya / Akrual",
        "account_type": AccountType.LIABILITY,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Utang Akrual"
    },
    {
        "account_code": "2501",
        "account_name": "Utang Lainnya / Pinjaman",
        "account_type": AccountType.LIABILITY,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Utang Lainnya"
    },

    # 3xxx Equity
    {
        "account_code": "3101",
        "account_name": "Modal Disetor",
        "account_type": AccountType.EQUITY,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Modal"
    },
    {
        "account_code": "3201",
        "account_name": "Saldo Laba Ditahan",
        "account_type": AccountType.EQUITY,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Laba Ditahan"
    },
    {
        "account_code": "3301",
        "account_name": "Prive / Penarikan Pemilik",
        "account_type": AccountType.EQUITY,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Prive"
    },

    # 4xxx Revenue
    {
        "account_code": "4101",
        "account_name": "Pendapatan Proyek dan Jasa",
        "account_type": AccountType.REVENUE,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Pendapatan Proyek"
    },
    {
        "account_code": "4201",
        "account_name": "Pendapatan Lain-lain",
        "account_type": AccountType.REVENUE,
        "normal_balance": NormalBalance.CREDIT,
        "report_group": "Pendapatan Lain-lain"
    },

    # 5xxx Project Cost (COGS)
    {
        "account_code": "5101",
        "account_name": "Harga Pokok Proyek",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Harga Pokok Proyek"
    },

    # 6xxx Operational Expenses
    {
        "account_code": "6101",
        "account_name": "Beban Gaji dan Upah Kantor",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6102",
        "account_name": "Beban Fee, Komisi, dan Jasa Non-Proyek",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6103",
        "account_name": "Beban Operasional Kantor dan Administrasi",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6104",
        "account_name": "Beban Transport dan Perjalanan Dinas Non-Proyek",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6105",
        "account_name": "Beban Legal, Perizinan, dan Sertifikasi Perusahaan",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6106",
        "account_name": "Beban Pajak dan Konsultan Profesional",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6107",
        "account_name": "Beban Administrasi Bank",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6108",
        "account_name": "Beban Penyusutan Aset Tetap",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },
    {
        "account_code": "6199",
        "account_name": "Beban Operasional Lainnya",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Operasional"
    },

    # 7xxx Non-Operational Expense
    {
        "account_code": "7101",
        "account_name": "Beban Non-Operasional / Luar Usaha",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Beban Luar Usaha"
    },

    # 8xxx Tax Expense
    {
        "account_code": "8101",
        "account_name": "Beban Pajak Penghasilan",
        "account_type": AccountType.EXPENSE,
        "normal_balance": NormalBalance.DEBIT,
        "report_group": "Pajak Penghasilan"
    },
]

# Standard Operational Payment Accounts mapped to 1101 Kas dan Bank
STANDARD_PAYMENT_ACCOUNTS: List[Dict[str, Any]] = [
    {"name": "Kas", "bank_name": "Cash", "account_number": None},
    {"name": "Petty Cash", "bank_name": "Cash", "account_number": None},
    {"name": "Bank Mandiri", "bank_name": "Mandiri", "account_number": None},
    {"name": "BCA", "bank_name": "BCA", "account_number": None},
    {"name": "BRI", "bank_name": "BRI", "account_number": None},
]


async def seed_standard_coa(
    session: AsyncSession,
    organization_id: uuid.UUID
) -> Tuple[int, int]:
    """
    Seeds the standard Chart of Accounts for an organization idempotently.
    Returns (created_count, skipped_count).
    """
    # Fetch existing account codes for this organization
    stmt = select(ChartOfAccount.account_code).where(
        ChartOfAccount.organization_id == organization_id
    )
    result = await session.execute(stmt)
    existing_codes = set(result.scalars().all())

    created_count = 0
    skipped_count = 0

    for defn in STANDARD_COA_DEFINITIONS:
        if defn["account_code"] in existing_codes:
            skipped_count += 1
            continue

        account = ChartOfAccount(
            organization_id=organization_id,
            account_code=defn["account_code"],
            account_name=defn["account_name"],
            account_type=defn["account_type"],
            normal_balance=defn["normal_balance"],
            report_group=defn["report_group"],
            is_active=True
        )
        session.add(account)
        created_count += 1

    await session.flush()
    return created_count, skipped_count


async def seed_standard_payment_accounts(
    session: AsyncSession,
    organization_id: uuid.UUID
) -> Tuple[int, int]:
    """
    Seeds standard payment accounts mapped to COA 1101 for an organization idempotently.
    Returns (created_count, skipped_count).
    """
    # Find parent COA account 1101
    stmt = select(ChartOfAccount).where(
        ChartOfAccount.organization_id == organization_id,
        ChartOfAccount.account_code == "1101"
    )
    result = await session.execute(stmt)
    parent_coa = result.scalar_one_or_none()

    if not parent_coa:
        raise ValueError("Cannot seed payment accounts: Parent COA 1101 not found for organization.")

    # Fetch existing payment accounts
    pa_stmt = select(PaymentAccount.name).where(
        PaymentAccount.organization_id == organization_id
    )
    pa_result = await session.execute(pa_stmt)
    existing_names = set(pa_result.scalars().all())

    created_count = 0
    skipped_count = 0

    for p_defn in STANDARD_PAYMENT_ACCOUNTS:
        if p_defn["name"] in existing_names:
            skipped_count += 1
            continue

        pa = PaymentAccount(
            organization_id=organization_id,
            coa_account_id=parent_coa.id,
            name=p_defn["name"],
            bank_name=p_defn["bank_name"],
            account_number=p_defn["account_number"],
            is_active=True
        )
        session.add(pa)
        created_count += 1

    await session.flush()
    return created_count, skipped_count
