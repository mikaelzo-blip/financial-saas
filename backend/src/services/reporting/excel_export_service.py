"""XLSX renderer for authoritative report export models."""

import io
import re
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel

from src.services.reporting.export_service import ExportService, ReportExportModel

MONEY_FORMAT = '#,##0.00;[Red]-#,##0.00'


class ExcelExportService:
    @staticmethod
    def export(report_type: str, report: BaseModel) -> io.BytesIO:
        return ExcelExportService.render(ExportService.build(report_type, report))

    @staticmethod
    def render(model: ReportExportModel) -> io.BytesIO:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Report"
        worksheet.freeze_panes = "A5"
        worksheet.sheet_view.showGridLines = False
        worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(model.headers))
        worksheet.cell(1, 1, f"{model.organization_name} — {model.title}").font = Font(size=14, bold=True)
        worksheet.cell(1, 1).alignment = Alignment(horizontal="center")
        worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(model.headers))
        worksheet.cell(2, 1, model.subtitle).alignment = Alignment(horizontal="center")

        for column, header in enumerate(model.headers, start=1):
            cell = worksheet.cell(4, column, header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1E293B")
            cell.alignment = Alignment(horizontal="center")

        excel_rows = {row.key: index for index, row in enumerate(model.rows, start=5)}
        reconciliation = []
        for row_number, row in enumerate(model.rows, start=5):
            for column_index, value in enumerate(row.values, start=1):
                cell = worksheet.cell(row_number, column_index, value)
                if isinstance(value, Decimal):
                    cell.number_format = MONEY_FORMAT
            for zero_based_column, template in row.formulas.items():
                column = zero_based_column + 1
                source_value = row.values[zero_based_column]
                if not isinstance(source_value, Decimal):
                    raise ValueError(f"Formula source {row.key} must be Decimal")
                formula = re.sub(r"\{([^}]+)\}", lambda match: str(excel_rows[match.group(1)]), template)
                worksheet.cell(row_number, column, formula).number_format = MONEY_FORMAT
                reconciliation.append((row.key, str(row.values[1]), column, source_value, f"'{worksheet.title}'!{get_column_letter(column)}{row_number}"))

            if row.style == "section":
                for cell in worksheet[row_number]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="475569")
            elif row.style in {"subtotal", "total", "grand_total"}:
                for cell in worksheet[row_number]:
                    cell.font = Font(bold=True)
                    if row.style == "grand_total":
                        cell.fill = PatternFill("solid", fgColor="DCFCE7")

        for index in range(1, len(model.headers) + 1):
            worksheet.column_dimensions[get_column_letter(index)].width = 42 if index == 2 else 16
        worksheet.auto_filter.ref = f"A4:{get_column_letter(len(model.headers))}{len(model.rows) + 4}"

        audit = workbook.create_sheet("Reconciliation")
        audit.append(("Key", "Label", "Column", "Authoritative DTO Value", "Visible Formula Cell", "Difference"))
        for index, (key, label, column, authoritative, formula_cell) in enumerate(reconciliation, start=2):
            audit.append((key, label, get_column_letter(column), authoritative, f"={formula_cell}", f"=E{index}-D{index}"))
            for column_number in (4, 5, 6):
                audit.cell(index, column_number).number_format = MONEY_FORMAT
        audit.sheet_state = "hidden"
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True
        workbook.calculation.calcMode = "auto"

        stream = io.BytesIO()
        workbook.save(stream)
        stream.seek(0)
        return stream

    @staticmethod
    def export_profit_loss(report: BaseModel) -> io.BytesIO:
        return ExcelExportService.export("profit-loss", report)

    @staticmethod
    def export_balance_sheet(report: BaseModel) -> io.BytesIO:
        return ExcelExportService.export("balance-sheet", report)
