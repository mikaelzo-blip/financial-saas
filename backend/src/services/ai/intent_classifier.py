import re

class IntentClassifier:
    RULES = (
        ('OUT_OF_SCOPE', re.compile(r'ignore|system instruction|hacked|approve|posting|jurnal|debit|kredit|select\s|sql', re.I)),
        ('AR_AGING', re.compile(r'piutang|invoice|tagih|pelanggan|receivable', re.I)),
        ('AP_AGING', re.compile(r'utang|vendor|payable|supplier', re.I)),
        ('CASH_VS_PROFIT', re.compile(r'\bkas\b.*\b(laba|profit)\b|\b(laba|profit)\b.*\bkas\b|cash.*profit|likuiditas', re.I)),
        ('PROJECT_HEALTH', re.compile(r'proyek|project|margin|profitabil', re.I)),
        ('OPERATIONAL_REVIEW', re.compile(r'review|dokumen|anomal|exception', re.I)),
        ('FINANCIAL_SUMMARY', re.compile(r'laba|pendapatan|neraca|keuangan|ringkasan', re.I)),
    )
    @classmethod
    def classify(cls, text: str) -> str:
        for intent, rule in cls.RULES:
            if rule.search(text): return intent
        return 'OUT_OF_SCOPE'
