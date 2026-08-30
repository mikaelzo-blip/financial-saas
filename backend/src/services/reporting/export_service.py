"""Authoritative, presentation-neutral financial report export models.

Renderers consume these models. All monetary values originate in an existing
reporting DTO; no ledger query or accounting calculation is duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from src.schemas.reporting import (
    APAgingReportResponse, ARAgingReportResponse, BalanceSheetReportResponse,
    CashFlowReportResponse, GeneralLedgerResponse, ProfitLossReportResponse,
    ProjectProfitabilityReportResponse, ReportSection, TrialBalanceResponse,
)

SUPPORTED_REPORT_TYPES = frozenset({
    "profit-loss", "balance-sheet", "cash-flow", "trial-balance",
    "general-ledger", "receivables-aging", "payables-aging",
    "project-profitability",
})


@dataclass(frozen=True)
class ExportRow:
    key: str
    values: tuple[Any, ...]
    style: str = "detail"
    formulas: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportExportModel:
    report_type: str
    title: str
    organization_name: str
    subtitle: str
    headers: tuple[str, ...]
    rows: tuple[ExportRow, ...]
    filename_stem: str


class ExportService:
    """Map authoritative reporting DTOs to deterministic export rows."""

    @staticmethod
    def build(report_type: str, report: BaseModel) -> ReportExportModel:
        builders = {
            "profit-loss": ExportService._profit_loss,
            "balance-sheet": ExportService._balance_sheet,
            "cash-flow": ExportService._cash_flow,
            "trial-balance": ExportService._trial_balance,
            "general-ledger": ExportService._general_ledger,
            "receivables-aging": ExportService._receivables_aging,
            "payables-aging": ExportService._payables_aging,
            "project-profitability": ExportService._project_profitability,
        }
        try:
            return builders[report_type](report)
        except KeyError as exc:
            raise ValueError(f"Unsupported report type: {report_type}") from exc

    @staticmethod
    def _section_rows(prefix: str, section: ReportSection) -> list[ExportRow]:
        rows = [ExportRow(f"{prefix}_header", ("", section.section_name, None), "section")]
        keys = []
        for index, line in enumerate(section.lines):
            key = f"{prefix}_line_{index}"
            keys.append(key)
            rows.append(ExportRow(key, (line.account_code or "", line.line_name, line.amount)))
        formula = "=0" if not keys else f"=SUM(C{{{keys[0]}}}:C{{{keys[-1]}}})"
        rows.append(ExportRow(f"{prefix}_total", ("", f"Total {section.section_name}", section.subtotal), "subtotal", {2: formula}))
        return rows

    @staticmethod
    def _profit_loss(report: BaseModel) -> ReportExportModel:
        data = ProfitLossReportResponse.model_validate(report)
        rows = []
        rows += ExportService._section_rows("revenue", data.revenue_section)
        rows += ExportService._section_rows("cogs", data.cogs_section)
        rows.append(ExportRow("gross_profit", ("", "Laba Kotor", data.gross_profit), "total", {2: "=C{revenue_total}-C{cogs_total}"}))
        rows += ExportService._section_rows("opex", data.operating_expenses_section)
        rows.append(ExportRow("operating_profit", ("", "Laba Usaha", data.operating_profit), "total", {2: "=C{gross_profit}-C{opex_total}"}))
        rows += ExportService._section_rows("other", data.other_income_expense_section)
        rows.append(ExportRow("ebt", ("", "Laba Sebelum Pajak", data.earnings_before_tax), "total", {2: "=C{operating_profit}+C{other_total}"}))
        rows.append(ExportRow("tax", ("", "Beban Pajak", data.tax_expense)))
        rows.append(ExportRow("net_profit", ("", "Laba Bersih", data.net_profit), "grand_total", {2: "=C{ebt}-C{tax}"}))
        return ReportExportModel("profit-loss", "LAPORAN LABA RUGI", data.organization_name, f"Periode: {data.period_label}", ("Kode", "Keterangan", "Jumlah (IDR)"), tuple(rows), f"Laporan_Laba_Rugi_{data.start_date}_{data.end_date}")

    @staticmethod
    def _balance_sheet(report: BaseModel) -> ReportExportModel:
        data = BalanceSheetReportResponse.model_validate(report)
        rows = []
        rows += ExportService._section_rows("current_assets", data.current_assets)
        rows += ExportService._section_rows("fixed_assets", data.fixed_assets)
        rows.append(ExportRow("total_assets", ("", "TOTAL ASET", data.total_assets), "grand_total", {2: "=C{current_assets_total}+C{fixed_assets_total}"}))
        rows += ExportService._section_rows("current_liabilities", data.current_liabilities)
        rows += ExportService._section_rows("long_term_liabilities", data.long_term_liabilities)
        rows.append(ExportRow("total_liabilities", ("", "Total Kewajiban", data.total_liabilities), "total", {2: "=C{current_liabilities_total}+C{long_term_liabilities_total}"}))
        rows += ExportService._section_rows("equity", data.equity)
        rows.append(ExportRow("total_equity", ("", "Total Ekuitas", data.total_equity), "total", {2: "=C{equity_total}"}))
        rows.append(ExportRow("liabilities_equity", ("", "TOTAL KEWAJIBAN + EKUITAS", data.total_liabilities_and_equity), "grand_total", {2: "=C{total_liabilities}+C{total_equity}"}))
        return ReportExportModel("balance-sheet", "LAPORAN NERACA", data.organization_name, f"Per tanggal: {data.as_of_date}", ("Kode", "Komponen Neraca", "Jumlah (IDR)"), tuple(rows), f"Laporan_Neraca_{data.as_of_date}")

    @staticmethod
    def _cash_flow(report: BaseModel) -> ReportExportModel:
        data = CashFlowReportResponse.model_validate(report)
        rows = [ExportRow("opening_cash", ("", "Saldo Kas Awal", data.opening_cash_balance), "total")]
        rows += ExportService._section_rows("operating", data.operating_activities)
        rows += ExportService._section_rows("investing", data.investing_activities)
        rows += ExportService._section_rows("financing", data.financing_activities)
        if data.unclassified_cash_activities is not None:
            rows += ExportService._section_rows("unclassified", data.unclassified_cash_activities)
            formula = "=C{operating_total}+C{investing_total}+C{financing_total}+C{unclassified_total}"
        else:
            formula = "=C{operating_total}+C{investing_total}+C{financing_total}"
        rows.append(ExportRow("net_change", ("", "Perubahan Bersih Kas", data.net_cash_change), "total", {2: formula}))
        rows.append(ExportRow("closing_cash", ("", "SALDO KAS AKHIR", data.closing_cash_balance), "grand_total", {2: "=C{opening_cash}+C{net_change}"}))
        return ReportExportModel("cash-flow", "LAPORAN ARUS KAS", data.organization_name, f"Periode: {data.period_label}", ("Kode", "Aktivitas", "Jumlah (IDR)"), tuple(rows), f"Laporan_Arus_Kas_{data.start_date}_{data.end_date}")

    @staticmethod
    def _trial_balance(report: BaseModel) -> ReportExportModel:
        data = TrialBalanceResponse.model_validate(report)
        rows = [ExportRow(f"account_{i}", (line.account_code, line.account_name, line.opening_debit, line.opening_credit, line.period_debit, line.period_credit, line.ending_debit, line.ending_credit)) for i, line in enumerate(data.lines)]
        formulas = {}
        if rows:
            for column in range(2, 8):
                letter = chr(ord("A") + column)
                formulas[column] = f"=SUM({letter}{{{rows[0].key}}}:{letter}{{{rows[-1].key}}})"
        totals = ("", "TOTAL", data.total_opening_debit, data.total_opening_credit, data.total_period_debit, data.total_period_credit, data.total_ending_debit, data.total_ending_credit)
        rows.append(ExportRow("totals", totals, "grand_total", formulas))
        return ReportExportModel("trial-balance", "NERACA SALDO", data.organization_name, f"Periode: {data.start_date} s.d. {data.end_date}", ("Kode", "Nama Akun", "Saldo Awal D", "Saldo Awal K", "Mutasi D", "Mutasi K", "Saldo Akhir D", "Saldo Akhir K"), tuple(rows), f"Neraca_Saldo_{data.as_of_date}")

    @staticmethod
    def _general_ledger(report: BaseModel) -> ReportExportModel:
        data = GeneralLedgerResponse.model_validate(report)
        rows = [ExportRow("opening", ("", "", "Saldo Awal", None, None, data.opening_balance), "total")]
        rows += [ExportRow(f"entry_{i}", (entry.date, entry.journal_entry_number, entry.description, entry.debit, entry.credit, entry.running_balance)) for i, entry in enumerate(data.entries)]
        formulas = {} if not data.entries else {3: f"=SUM(D{{entry_0}}:D{{entry_{len(data.entries)-1}}})", 4: f"=SUM(E{{entry_0}}:E{{entry_{len(data.entries)-1}}})"}
        rows.append(ExportRow("totals", ("", "", "Total Mutasi / Saldo Akhir", data.total_debit, data.total_credit, data.closing_balance), "grand_total", formulas))
        return ReportExportModel("general-ledger", "BUKU BESAR", data.organization_name, f"{data.account_code} — {data.account_name}; {data.start_date} s.d. {data.end_date}", ("Tanggal", "No. Jurnal", "Keterangan", "Debet", "Kredit", "Saldo"), tuple(rows), f"Buku_Besar_{data.account_code}_{data.start_date}_{data.end_date}")

    @staticmethod
    def _aging_rows(lines, prefix: str):
        rows = [ExportRow(f"{prefix}_{i}", (line.invoice_number if prefix == "invoice" else line.bill_number, line.customer_name if prefix == "invoice" else line.vendor_name, line.due_date, line.bucket, line.total_amount, line.paid_amount, line.outstanding_amount)) for i, line in enumerate(lines)]
        formulas = {}
        if rows:
            formulas = {column: f"=SUM({chr(65 + column)}{{{rows[0].key}}}:{chr(65 + column)}{{{rows[-1].key}}})" for column in (4, 5, 6)}
        return rows, formulas

    @staticmethod
    def _receivables_aging(report: BaseModel) -> ReportExportModel:
        data = ARAgingReportResponse.model_validate(report)
        rows, formulas = ExportService._aging_rows(data.invoices, "invoice")
        total = lambda attr: sum((getattr(line, attr) for line in data.invoices), Decimal("0.00"))
        rows.append(ExportRow("totals", ("", "TOTAL", "", "", total("total_amount"), total("paid_amount"), data.summary.total), "grand_total", formulas))
        return ReportExportModel("receivables-aging", "LAPORAN UMUR PIUTANG", data.organization_name, f"Per tanggal: {data.as_of_date}", ("Invoice", "Pelanggan", "Jatuh Tempo", "Bucket", "Nilai", "Dibayar", "Sisa Piutang"), tuple(rows), f"Umur_Piutang_{data.as_of_date}")

    @staticmethod
    def _payables_aging(report: BaseModel) -> ReportExportModel:
        data = APAgingReportResponse.model_validate(report)
        rows, formulas = ExportService._aging_rows(data.bills, "bill")
        total = lambda attr: sum((getattr(line, attr) for line in data.bills), Decimal("0.00"))
        rows.append(ExportRow("totals", ("", "TOTAL", "", "", total("total_amount"), total("paid_amount"), data.summary.total), "grand_total", formulas))
        rows.append(ExportRow("advances", ("", "Uang Muka Vendor Belum Diselesaikan", "", "", None, None, data.unsettled_advances_total), "total"))
        return ReportExportModel("payables-aging", "LAPORAN UMUR UTANG", data.organization_name, f"Per tanggal: {data.as_of_date}", ("Tagihan", "Vendor", "Jatuh Tempo", "Bucket", "Nilai", "Dibayar", "Sisa Utang"), tuple(rows), f"Umur_Utang_{data.as_of_date}")

    @staticmethod
    def _project_profitability(report: BaseModel) -> ReportExportModel:
        data = ProjectProfitabilityReportResponse.model_validate(report)
        rows = [ExportRow("contract", ("", "Nilai Kontrak Revisi", data.revised_contract_value), "total"), ExportRow("revenue", ("", "Pendapatan Diakui", data.revenue_recognized), "total"), ExportRow("cost_header", ("", "Realisasi Biaya Proyek", None), "section")]
        rows += [ExportRow(f"cost_{i}", (line.cost_category, line.category_name, line.amount)) for i, line in enumerate(data.cost_breakdown)]
        formula = "=0" if not data.cost_breakdown else f"=SUM(C{{cost_0}}:C{{cost_{len(data.cost_breakdown)-1}}})"
        rows.append(ExportRow("total_cost", ("", "Total Biaya Proyek", data.total_project_cost), "total", {2: formula}))
        rows.append(ExportRow("gross_profit", ("", "LABA KOTOR PROYEK", data.gross_profit), "grand_total", {2: "=C{revenue}-C{total_cost}"}))
        return ReportExportModel("project-profitability", "LAPORAN PROFITABILITAS PROYEK", data.organization_name, f"{data.project_code} — {data.project_name}", ("Kode", "Komponen", "Jumlah (IDR)"), tuple(rows), f"Profitabilitas_Proyek_{data.project_code}")


def safe_filename(stem: str, extension: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_." else "_" for char in stem)
    return f"{cleaned}.{extension}"
