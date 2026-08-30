"""
Standard Indonesian Contractor Chart of Accounts report grouping definitions and mappings.
"""
from src.models.enums import AccountType, NormalBalance

REPORT_GROUPS = {
    # P&L Groups
    "REVENUE": {
        "code": "REV",
        "name": "Pendapatan Proyek & Jasa",
        "account_types": [AccountType.REVENUE],
        "normal_balance": NormalBalance.CREDIT
    },
    "COGS": {
        "code": "COGS",
        "name": "Harga Pokok Proyek (HPP)",
        "account_types": [AccountType.EXPENSE],
        "normal_balance": NormalBalance.DEBIT,
        "prefix_match": ["51"]
    },
    "OPEX": {
        "code": "OPEX",
        "name": "Beban Operasional",
        "account_types": [AccountType.EXPENSE],
        "normal_balance": NormalBalance.DEBIT,
        "prefix_match": ["61"]
    },
    "OTHER_INCOME_EXPENSE": {
        "code": "OTHER",
        "name": "Pendapatan & Beban Lain-lain",
        "account_types": [AccountType.REVENUE, AccountType.EXPENSE],
        "prefix_match": ["71", "72"]
    },
    # Balance Sheet Groups
    "CURRENT_ASSETS": {
        "code": "CA",
        "name": "Aset Lancar",
        "account_types": [AccountType.ASSET],
        "normal_balance": NormalBalance.DEBIT,
        "prefix_match": ["11"]
    },
    "FIXED_ASSETS": {
        "code": "FA",
        "name": "Aset Tetap",
        "account_types": [AccountType.ASSET],
        "normal_balance": NormalBalance.DEBIT,
        "prefix_match": ["12"]
    },
    "CURRENT_LIABILITIES": {
        "code": "CL",
        "name": "Kewajiban Jangka Pendek",
        "account_types": [AccountType.LIABILITY],
        "normal_balance": NormalBalance.CREDIT,
        "prefix_match": ["21"]
    },
    "EQUITY": {
        "code": "EQ",
        "name": "Ekuitas",
        "account_types": [AccountType.EQUITY],
        "normal_balance": NormalBalance.CREDIT,
        "prefix_match": ["31", "32", "33", "34"]
    }
}
