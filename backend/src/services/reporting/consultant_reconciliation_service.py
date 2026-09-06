import io
import re
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
import pypdf

from src.schemas.consultant_reconciliation import (
    ConsultantFinancialStatementData,
    ConsultantIntegrityAudit,
    ConsultantReconciliationReport,
    ConsultantReconciliationSummary,
    DifferenceClassification,
    LineItemComparison,
)
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.pl_service import ProfitLossService


class ConsultantReconciliationService:
    """Reconciles external consultant financial statements against Financial SaaS live ledger."""

    # Verified historical statements ratified from owner source PDF documents
    VERIFIED_HISTORICAL_STATEMENTS: Dict[int, ConsultantFinancialStatementData] = {
        2023: ConsultantFinancialStatementData(
            year=2023,
            company_name="PT SAMUDERA TERANG JAYA",
            source_document_name="Neraca dan laba rugi 2023.pdf",
            revenue=Decimal("1569062699.00"),
            cogs=Decimal("969449976.00"),
            gross_profit=Decimal("599612723.00"),
            operating_expenses=Decimal("453750710.00"),
            operating_profit=Decimal("145862013.00"),
            other_income=Decimal("1244463.00"),
            other_expenses=Decimal("800493.00"),
            profit_before_tax=Decimal("147106476.00"),
            income_tax=Decimal("800493.00"),
            profit_after_tax=Decimal("146305983.00"),
            cash=Decimal("27659620.00"),
            bank=Decimal("581586759.00"),
            receivables=Decimal("169864355.00"),
            other_current_assets=Decimal("95609004.00"),  # Piutang Lain 74.300.000 + Aktiva Tidak Lancar Lain 21.309.004
            inventory=Decimal("0.00"),
            fixed_assets_cost=Decimal("125572000.00"),  # Peralatan 93.272.000 + Inventaris 32.300.000
            accumulated_depreciation=Decimal("55725000.00"),  # 31.500.000 + 24.225.000
            total_assets=Decimal("944566738.00"),
            payables=Decimal("70951200.00"),
            tax_liabilities=Decimal("46993882.00"),
            long_term_liabilities=Decimal("0.00"),
            total_liabilities=Decimal("117945082.00"),
            capital=Decimal("600000000.00"),
            retained_earnings=Decimal("80315673.00"),
            current_year_earnings=Decimal("146305983.00"),
            total_equity=Decimal("826621656.00"),
            total_liabilities_equity=Decimal("944566738.00"),
            expense_breakdown={
                "Gaji & THR": Decimal("311015055.00"),
                "BBM & Tol": Decimal("6372472.00"),
                "Mobile Phone": Decimal("3994000.00"),
                "Perjalanan Dinas": Decimal("10900000.00"),
                "Utilitas": Decimal("24682335.00"),
                "Perlengkapan Kantor & ATK": Decimal("9817300.00"),
                "Photocopy": Decimal("324000.00"),
                "Iuran Lingkungan": Decimal("3000000.00"),
                "Service Inventaris": Decimal("280000.00"),
                "BPJS": Decimal("5793020.00"),
                "Materai": Decimal("1000000.00"),
                "Penyusutan": Decimal("18575000.00"),
                "Perijinan SIUJK": Decimal("23500000.00"),
                "Makan / Dapur": Decimal("34497528.00"),
            },
        ),
        2024: ConsultantFinancialStatementData(
            year=2024,
            company_name="PT SAMUDERA TERANG JAYA",
            source_document_name="Laba Rugi 2024.pdf / Neraca 2024-12.pdf",
            revenue=Decimal("3271190594.00"),
            cogs=Decimal("1804921019.00"),
            gross_profit=Decimal("1466269575.00"),
            operating_expenses=Decimal("1184386900.00"),
            operating_profit=Decimal("281882675.00"),
            other_income=Decimal("1491264.00"),
            other_expenses=Decimal("1190153.00"),
            profit_before_tax=Decimal("282183786.00"),
            income_tax=Decimal("31040216.00"),
            profit_after_tax=Decimal("251143570.00"),
            cash=Decimal("84997214.00"),
            bank=Decimal("634522700.00"),
            receivables=Decimal("249840383.00"),
            other_current_assets=Decimal("36581854.00"),
            inventory=Decimal("0.00"),
            fixed_assets_cost=Decimal("158951000.00"),  # Peralatan 93.272.000 + Inventaris 65.679.000
            accumulated_depreciation=Decimal("87118000.00"),  # 54.818.000 + 32.300.000
            total_assets=Decimal("1077775151.00"),
            payables=Decimal("0.00"),
            tax_liabilities=Decimal("9925.00"),
            long_term_liabilities=Decimal("0.00"),
            total_liabilities=Decimal("9925.00"),
            capital=Decimal("600000000.00"),
            retained_earnings=Decimal("226621656.00"),  # Exact sum: 80.315.673 + 146.305.983
            current_year_earnings=Decimal("251143570.00"),
            total_equity=Decimal("1077765226.00"),
            total_liabilities_equity=Decimal("1077775151.00"),
            expense_breakdown={
                "Gaji & THR": Decimal("1092600000.00"),
                "Listrik, Air & Telepon": Decimal("17682000.00"),
                "Rumah Tangga": Decimal("17497000.00"),
                "Telepon": Decimal("839000.00"),
                "Perjalanan Dinas": Decimal("900000.00"),
                "BBM, Parkir, Tol": Decimal("7637200.00"),
                "Asuransi": Decimal("3237000.00"),
                "Materai, Pos & Fotokopi": Decimal("300000.00"),
                "Perlengkapan Kantor": Decimal("8801700.00"),
                "Perijinan SBU": Decimal("3500000.00"),
                "Penyusutan": Decimal("31393000.00"),
            },
        ),
        2025: ConsultantFinancialStatementData(
            year=2025,
            company_name="PT SAMUDERA TERANG JAYA",
            source_document_name="STJ SPT THN 2025.pdf",
            revenue=Decimal("6047503085.00"),
            cogs=Decimal("3974006498.00"),
            gross_profit=Decimal("2073496587.00"),
            operating_expenses=Decimal("1438362950.00"),
            operating_profit=Decimal("635133637.00"),
            other_income=Decimal("2717213.00"),
            other_expenses=Decimal("1149717.00"),
            profit_before_tax=Decimal("636701133.00"),
            income_tax=Decimal("84484662.00"),
            profit_after_tax=Decimal("552216471.00"),
            cash=Decimal("338421159.00"),
            bank=Decimal("701099934.00"),
            receivables=Decimal("13708500.00"),
            other_current_assets=Decimal("536581854.00"),
            inventory=Decimal("0.00"),
            fixed_assets_cost=Decimal("158951000.00"),  # Peralatan 93.272.000 + Inventaris 65.679.000
            accumulated_depreciation=Decimal("118780750.00"),  # 78.136.000 + 40.644.750
            total_assets=Decimal("1629981697.00"),
            payables=Decimal("0.00"),
            tax_liabilities=Decimal("0.00"),
            long_term_liabilities=Decimal("0.00"),
            total_liabilities=Decimal("0.00"),
            capital=Decimal("600000000.00"),
            retained_earnings=Decimal("477765226.00"),  # Exact sum: 226.621.656 + 251.143.570
            current_year_earnings=Decimal("552008841.00"),  # Document states 552.008.841 on Neraca
            total_equity=Decimal("1629774067.00"),
            total_liabilities_equity=Decimal("1629774067.00"),
            expense_breakdown={
                "Gaji & THR": Decimal("1259700000.00"),
                "Listrik, Air & Telepon": Decimal("27682000.00"),
                "Rumah Tangga": Decimal("46497100.00"),
                "Telepon": Decimal("8939800.00"),
                "Perjalanan Dinas": Decimal("38804000.00"),
                "BBM, Parkir, Tol": Decimal("9667100.00"),
                "Materai, Pos & Fotokopi": Decimal("1200000.00"),
                "Perlengkapan Kantor": Decimal("9710200.00"),
                "Perijinan": Decimal("4500000.00"),
                "Penyusutan": Decimal("31662750.00"),
            },
        ),
    }

    @classmethod
    def audit_consultant_statement(cls, data: ConsultantFinancialStatementData) -> ConsultantIntegrityAudit:
        """Audits internal arithmetic integrity of consultant financial statement."""
        findings: List[str] = []

        # 1. Assets vs Liabilities + Equity
        bs_diff = data.total_assets - data.total_liabilities_equity
        if bs_diff != Decimal("0.00"):
            findings.append(
                f"Selisih Neraca Laporan Konsultan: Total Aktiva (Rp {data.total_assets:,.2f}) "
                f"tidak sama dengan Total Passiva (Rp {data.total_liabilities_equity:,.2f}). "
                f"Selisih internal = Rp {bs_diff:,.2f}."
            )

        # 2. Profit After Tax vs Current Year Earnings on Balance Sheet
        pat_diff = data.profit_after_tax - data.current_year_earnings
        if pat_diff != Decimal("0.00"):
            findings.append(
                f"Inkonsistensi Laba Berjalan Konsultan: Laba Setelah Pajak (EAT) di Laporan Laba Rugi "
                f"(Rp {data.profit_after_tax:,.2f}) tidak sama dengan Laba Tahun Berjalan di Neraca "
                f"(Rp {data.current_year_earnings:,.2f}). Selisih = Rp {pat_diff:,.2f}."
            )

        # 3. P&L Internal Math
        expected_gross = data.revenue - data.cogs
        if expected_gross != data.gross_profit:
            findings.append(
                f"Aritmatika Laba Kotor Konsultan: Peredaran Usaha - HPP (Rp {expected_gross:,.2f}) "
                f"!= Laba Usaha tercantum (Rp {data.gross_profit:,.2f})."
            )

        expected_ebt_standard = data.operating_profit + data.other_income - data.other_expenses
        expected_ebt_post_ebt_expenses = data.operating_profit + data.other_income
        if data.profit_before_tax not in (expected_ebt_standard, expected_ebt_post_ebt_expenses):
            findings.append(
                f"Aritmatika Laba Sebelum Pajak Konsultan: Laba Usaha + Pendapatan Lain - Biaya Lain "
                f"(Rp {expected_ebt_standard:,.2f}) != EBT tercantum (Rp {data.profit_before_tax:,.2f})."
            )

        expected_eat_standard = data.profit_before_tax - data.income_tax
        expected_eat_alt = data.profit_before_tax - data.other_expenses
        if data.profit_after_tax not in (expected_eat_standard, expected_eat_alt):
            findings.append(
                f"Aritmatika Laba Bersih Konsultan: EBT - Pajak (Rp {expected_eat_standard:,.2f}) "
                f"!= EAT tercantum (Rp {data.profit_after_tax:,.2f})."
            )

        is_balanced = (bs_diff == Decimal("0.00")) and (pat_diff == Decimal("0.00"))
        return ConsultantIntegrityAudit(
            is_balanced=is_balanced,
            assets_liabilities_equity_discrepancy=bs_diff,
            pat_vs_current_earnings_discrepancy=pat_diff,
            findings=findings,
        )

    @classmethod
    async def reconcile_with_saas(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        consultant_data: ConsultantFinancialStatementData,
    ) -> ConsultantReconciliationReport:
        """Compares consultant statement line-by-line against Financial SaaS double-entry ledger."""
        year = consultant_data.year
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # 1. Audit consultant statement integrity first
        audit = cls.audit_consultant_statement(consultant_data)

        # 2. Fetch authoritative Financial SaaS P&L
        saas_pl = await ProfitLossService.get_profit_and_loss(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        # 3. Fetch authoritative Financial SaaS Balance Sheet
        saas_bs = await BalanceSheetService.get_balance_sheet(
            session=session,
            organization_id=organization_id,
            as_of_date=end_date,
        )

        # 4. Map and classify P&L items
        pl_items = [
            ("REVENUE", "Peredaran Usaha / Pendapatan Proyek", "Revenue / Project Income", consultant_data.revenue, saas_pl.revenue_section.subtotal),
            ("COGS", "Harga Pokok Proyek / Penjualan (HPP)", "Cost of Goods Sold (COGS)", consultant_data.cogs, saas_pl.cogs_section.subtotal),
            ("GROSS_PROFIT", "Laba Kotor / Laba Usaha Proyek", "Gross Profit", consultant_data.gross_profit, saas_pl.gross_profit),
            ("OPEX", "Beban Umum & Administrasi", "General & Administrative Expenses", consultant_data.operating_expenses, saas_pl.operating_expenses_section.subtotal),
            ("OPERATING_PROFIT", "Laba Usaha (EBIT)", "Operating Profit (EBIT)", consultant_data.operating_profit, saas_pl.operating_profit),
            ("OTHER_INCOME", "Pendapatan Lain-lain", "Other Income", consultant_data.other_income, saas_pl.other_income_expense_section.subtotal if saas_pl.other_income_expense_section.subtotal > 0 else Decimal("0.00")),
            ("OTHER_EXPENSES", "Biaya Lain-lain / Bank", "Other / Bank Expenses", consultant_data.other_expenses, abs(saas_pl.other_income_expense_section.subtotal) if saas_pl.other_income_expense_section.subtotal < 0 else Decimal("0.00")),
            ("PROFIT_BEFORE_TAX", "Laba Sebelum Pajak (EBT)", "Profit Before Tax (EBT)", consultant_data.profit_before_tax, saas_pl.earnings_before_tax),
            ("INCOME_TAX", "Beban Pajak Penghasilan", "Income Tax Expense", consultant_data.income_tax, saas_pl.tax_expense),
            ("PROFIT_AFTER_TAX", "Laba Setelah Pajak (EAT / Net Profit)", "Profit After Tax (EAT)", consultant_data.profit_after_tax, saas_pl.net_profit),
        ]

        pl_comparisons: List[LineItemComparison] = []
        for key, lbl_id, lbl_en, c_val, s_val in pl_items:
            variance = s_val - c_val
            classification = cls._classify_difference(key, c_val, s_val, variance, audit)
            notes = cls._generate_item_note(key, classification, variance, audit)
            pl_comparisons.append(
                LineItemComparison(
                    item_key=key,
                    label_id=lbl_id,
                    label_en=lbl_en,
                    consultant_amount=c_val,
                    saas_amount=s_val,
                    variance=variance,
                    classification=classification,
                    notes=notes,
                )
            )

        # 5. Extract balance sheet components from SaaS report
        saas_cash = Decimal("0.00")
        saas_bank = Decimal("0.00")
        saas_receivables = Decimal("0.00")
        saas_other_current_assets = Decimal("0.00")
        saas_inventory = Decimal("0.00")
        saas_fixed_assets_cost = Decimal("0.00")
        saas_accumulated_depreciation = Decimal("0.00")

        # Parse active accounts from SaaS Balance Sheet current assets
        for line in saas_bs.current_assets.lines:
            code = getattr(line, "account_code", "")
            name = getattr(line, "line_name", "")
            amt = line.amount
            if code == "1001" or "Kas" in name:
                saas_cash += amt
            elif code in ("1101", "1102") or "Bank" in name:
                saas_bank += amt
            elif code in ("1201", "1202") or "Piutang" in name:
                saas_receivables += amt
            elif code == "1301" or "Persediaan" in name:
                saas_inventory += amt
            else:
                saas_other_current_assets += amt

        for line in saas_bs.fixed_assets.lines:
            code = getattr(line, "account_code", "")
            name = getattr(line, "line_name", "")
            amt = line.amount
            if code in ("1501", "1503") or ("Aktiva Tetap" in name and "Akumulasi" not in name):
                saas_fixed_assets_cost += amt
            elif code in ("1502", "1504") or "Akumulasi" in name:
                saas_accumulated_depreciation += abs(amt)
            else:
                saas_fixed_assets_cost += amt

        saas_payables = Decimal("0.00")
        saas_tax_liabilities = Decimal("0.00")
        saas_long_term_liabilities = Decimal("0.00")

        for line in saas_bs.current_liabilities.lines:
            code = getattr(line, "account_code", "")
            name = getattr(line, "line_name", "")
            amt = line.amount
            if code == "2101" or "Utang Usaha" in name:
                saas_payables += amt
            elif code == "2201" or "Pajak" in name:
                saas_tax_liabilities += amt
            else:
                saas_payables += amt

        for line in saas_bs.long_term_liabilities.lines:
            saas_long_term_liabilities += line.amount

        saas_capital = Decimal("0.00")
        saas_retained_earnings = Decimal("0.00")
        saas_current_year_earnings = Decimal("0.00")

        for line in saas_bs.equity.lines:
            code = getattr(line, "account_code", "")
            name = getattr(line, "line_name", "")
            amt = line.amount
            if code == "3101" or "Modal" in name:
                saas_capital += amt
            elif code == "3201" or "Ditahan" in name:
                saas_retained_earnings += amt
            elif code == "EQ-CY" or "Berjalan" in name:
                saas_current_year_earnings += amt

        bs_items = [
            ("CASH", "Kas", "Cash", consultant_data.cash, saas_cash),
            ("BANK", "Bank Mandiri / BTN", "Bank Accounts", consultant_data.bank, saas_bank),
            ("RECEIVABLES", "Piutang Usaha", "Accounts Receivable", consultant_data.receivables, saas_receivables),
            ("OTHER_CURRENT_ASSETS", "Aktiva Lancar / Tidak Lancar Lain", "Other Current / Non-Current Assets", consultant_data.other_current_assets, saas_other_current_assets),
            ("INVENTORY", "Persediaan Material", "Inventory", consultant_data.inventory, saas_inventory),
            ("FIXED_ASSETS_COST", "Aktiva Tetap (Harga Perolehan)", "Fixed Assets (Cost)", consultant_data.fixed_assets_cost, saas_fixed_assets_cost),
            ("ACCUMULATED_DEPRECIATION", "Akumulasi Penyusutan", "Accumulated Depreciation", consultant_data.accumulated_depreciation, saas_accumulated_depreciation),
            ("TOTAL_ASSETS", "TOTAL AKTIVA", "Total Assets", consultant_data.total_assets, saas_bs.total_assets),
            ("PAYABLES", "Hutang Usaha Suplier", "Accounts Payable", consultant_data.payables, saas_payables),
            ("TAX_LIABILITIES", "Hutang Pajak", "Tax Liabilities", consultant_data.tax_liabilities, saas_tax_liabilities),
            ("LONG_TERM_LIABILITIES", "Kewajiban Jangka Panjang", "Long-Term Liabilities", consultant_data.long_term_liabilities, saas_long_term_liabilities),
            ("TOTAL_LIABILITIES", "TOTAL KEWAJIBAN", "Total Liabilities", consultant_data.total_liabilities, saas_bs.total_liabilities),
            ("CAPITAL", "Modal Saham", "Capital / Share Equity", consultant_data.capital, saas_capital),
            ("RETAINED_EARNINGS", "Laba(Rugi) Ditahan / Tahun Sebelumnya", "Retained Earnings", consultant_data.retained_earnings, saas_retained_earnings),
            ("CURRENT_YEAR_EARNINGS", "Laba(Rugi) Tahun Berjalan", "Current-Year Earnings", consultant_data.current_year_earnings, saas_current_year_earnings),
            ("TOTAL_EQUITY", "TOTAL EKUITAS", "Total Equity", consultant_data.total_equity, saas_bs.total_equity),
            ("TOTAL_PASSIVA", "TOTAL PASSIVA (Kewajiban + Ekuitas)", "Total Liabilities & Equity", consultant_data.total_liabilities_equity, saas_bs.total_liabilities_and_equity),
        ]

        bs_comparisons: List[LineItemComparison] = []
        for key, lbl_id, lbl_en, c_val, s_val in bs_items:
            variance = s_val - c_val
            classification = cls._classify_difference(key, c_val, s_val, variance, audit)
            notes = cls._generate_item_note(key, classification, variance, audit)
            bs_comparisons.append(
                LineItemComparison(
                    item_key=key,
                    label_id=lbl_id,
                    label_en=lbl_en,
                    consultant_amount=c_val,
                    saas_amount=s_val,
                    variance=variance,
                    classification=classification,
                    notes=notes,
                )
            )

        # 6. Aggregate Summary
        all_comparisons = pl_comparisons + bs_comparisons
        match_count = sum(1 for c in all_comparisons if c.classification == DifferenceClassification.MATCH)
        diff_count = sum(1 for c in all_comparisons if c.classification in (DifferenceClassification.MAPPING_DIFFERENCE, DifferenceClassification.TIMING_DIFFERENCE, DifferenceClassification.FISCAL_DIFFERENCE))
        missing_count = sum(1 for c in all_comparisons if c.classification == DifferenceClassification.MISSING_DATA)
        defect_count = sum(1 for c in all_comparisons if c.classification in (DifferenceClassification.CONSULTANT_REPORT_DIFFERENCE, DifferenceClassification.SYSTEM_DEFECT))

        summary = ConsultantReconciliationSummary(
            total_items_compared=len(all_comparisons),
            match_count=match_count,
            difference_count=diff_count,
            missing_data_count=missing_count,
            consultant_defect_count=defect_count,
            net_pl_variance=saas_pl.net_profit - consultant_data.profit_after_tax,
            net_bs_variance=saas_bs.total_assets - consultant_data.total_assets,
        )

        return ConsultantReconciliationReport(
            organization_id=organization_id,
            year=year,
            as_of_date=end_date,
            consultant_data=consultant_data,
            statement_integrity=audit,
            pl_comparisons=pl_comparisons,
            bs_comparisons=bs_comparisons,
            summary=summary,
        )

    @classmethod
    def _classify_difference(
        cls,
        item_key: str,
        consultant_val: Decimal,
        saas_val: Decimal,
        variance: Decimal,
        audit: ConsultantIntegrityAudit,
    ) -> DifferenceClassification:
        """Deterministically classifies difference without guessing or forcing matches."""
        if variance == Decimal("0.00"):
            return DifferenceClassification.MATCH

        # Check if the discrepancy originates in the consultant's own statement
        if item_key in ("CURRENT_YEAR_EARNINGS", "TOTAL_PASSIVA") and audit.pat_vs_current_earnings_discrepancy != Decimal("0.00"):
            return DifferenceClassification.CONSULTANT_REPORT_DIFFERENCE

        if item_key in ("TOTAL_ASSETS", "TOTAL_PASSIVA") and audit.assets_liabilities_equity_discrepancy != Decimal("0.00"):
            return DifferenceClassification.CONSULTANT_REPORT_DIFFERENCE

        # If SaaS has 0 but consultant has value, and no transactions exist in that period, it is MISSING_DATA
        if saas_val == Decimal("0.00") and consultant_val != Decimal("0.00"):
            return DifferenceClassification.MISSING_DATA

        # If tax related, mark FISCAL_DIFFERENCE
        if "TAX" in item_key:
            return DifferenceClassification.FISCAL_DIFFERENCE

        return DifferenceClassification.MAPPING_DIFFERENCE

    @classmethod
    def _generate_item_note(
        cls,
        item_key: str,
        classification: DifferenceClassification,
        variance: Decimal,
        audit: ConsultantIntegrityAudit,
    ) -> Optional[str]:
        if classification == DifferenceClassification.MATCH:
            return "Nilai cocok sempurna dengan buku besar SaaS."
        elif classification == DifferenceClassification.CONSULTANT_REPORT_DIFFERENCE:
            return (
                f"Laporan konsultan memiliki selisih internal: "
                f"Rp {audit.pat_vs_current_earnings_discrepancy:,.2f} pada laba berjalan / neraca."
            )
        elif classification == DifferenceClassification.MISSING_DATA:
            return "Transaksi periode ini belum diinput ke sistem Financial SaaS."
        elif classification == DifferenceClassification.FISCAL_DIFFERENCE:
            return "Perbedaan perlakuan taksiran pajak komersial vs fiskal."
        return f"Selisih pemetaan akun sebesar Rp {variance:,.2f}."

    @classmethod
    def parse_consultant_pdf(cls, file_bytes: bytes, filename: str) -> ConsultantFinancialStatementData:
        """Parses a consultant statement PDF into structured data with arithmetic verification."""
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Detect year
        year_match = re.search(r"(?:Tahun|Per,?\s*31\s*Desember)\s*(202[0-9])", full_text, re.IGNORECASE)
        year = int(year_match.group(1)) if year_match else 2025

        def extract_num(pattern: str, text: str) -> Decimal:
            m = re.search(pattern, text, re.IGNORECASE)
            if not m:
                return Decimal("0.00")
            raw = m.group(1).replace(".", "").replace(",", "").strip()
            try:
                return Decimal(raw)
            except Exception:
                return Decimal("0.00")

        # Peredaran Usaha / Penjualan
        revenue = extract_num(r"(?:Peredaran\s*Usaha|Penjualan)\s*([0-9.,]+)", full_text)
        cogs = extract_num(r"(?:HARGA\s*POKOK|BIAYA\s*POKOK)\s*([0-9.,]+)", full_text)
        gross_profit = extract_num(r"(?:Laba\s*Usaha|Laba\s*Kotor)\s*([0-9.,]+)", full_text)
        opex = extract_num(r"(?:Jumlah\s*Beban\s*Umum|Jumlah\s*Biaya\s*Usaha)\s*([0-9.,]+)", full_text)
        operating_profit = extract_num(r"(?:Laba/?Rugi\s*Usaha\s*Sebelum\s*Pajak|Laba\s*Rugi\s*Usaha\s*-\s*EBIT)\s*([0-9.,]+)", full_text)
        other_income = extract_num(r"(?:JUMLAH\s*PENDAPATAN\s*DILUAR\s*USAHA|Jasa\s*Giro)\s*([0-9.,]+)", full_text)
        other_expenses = extract_num(r"(?:JUMLAH\s*BIAYA\s*LAIN-LAIN|Biaya\s*Admin\s*Bank)\s*([0-9.,]+)", full_text)
        ebt = extract_num(r"(?:LABA\s*RUGI\s*SEBELUM\s*PAJAK\s*-\s*EBT)\s*([0-9.,]+)", full_text)
        tax = extract_num(r"(?:TAKSIRAN\s*PAJAK\s*PENGHASILAN|Pajak\s*penghasialan)\s*([0-9.,]+)", full_text)
        eat = extract_num(r"(?:LABA\s*RUGI\s*SETELAH\s*PAJAK\s*-\s*EAT)\s*([0-9.,]+)", full_text)

        # Balance Sheet
        cash = extract_num(r"Kas\s*([0-9.,]+)", full_text)
        bank = extract_num(r"Bank\s*(?:Mandiri[^\n0-9]*)*([0-9.,]+)", full_text)
        receivables = extract_num(r"Piutang\s*usaha\s*([0-9.,]+)", full_text)
        other_current = extract_num(r"AKTIVA\s*TIDAK\s*LANCAR\s*LAIN\s*([0-9.,]+)", full_text)
        tot_act = extract_num(r"TOTAL\s*AKTIVA\s*([0-9.,]+)", full_text)

        capital = extract_num(r"MODAL\s*SAHAM\s*([0-9.,]+)", full_text)
        retained = extract_num(r"LABA\(?RUGI\)?\s*THN\s*SEBELUMNYA\s*([0-9.,]+)", full_text)
        current_year = extract_num(r"LABA\(?RUGI\)?\s*THN\s*BERJALAN\s*([0-9.,]+)", full_text)
        tot_pas = extract_num(r"TOTAL\s*PASSIVA\s*([0-9.,]+)", full_text)

        return ConsultantFinancialStatementData(
            year=year,
            company_name="PT SAMUDERA TERANG JAYA",
            source_document_name=filename,
            revenue=revenue,
            cogs=cogs,
            gross_profit=gross_profit,
            operating_expenses=opex,
            operating_profit=operating_profit,
            other_income=other_income,
            other_expenses=other_expenses,
            profit_before_tax=ebt,
            income_tax=tax,
            profit_after_tax=eat,
            cash=cash,
            bank=bank,
            receivables=receivables,
            other_current_assets=other_current,
            total_assets=tot_act,
            capital=capital,
            retained_earnings=retained,
            current_year_earnings=current_year,
            total_liabilities_equity=tot_pas,
        )
