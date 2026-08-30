"""Print-ready PDF renderer for authoritative report export models."""

import io
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from xml.sax.saxutils import escape

from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.services.reporting.export_service import ExportService, ReportExportModel


def format_currency_idr(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rendered = f"{quantized:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Rp {rendered}"


class PdfExportService:
    @staticmethod
    def export(report_type: str, report: BaseModel) -> io.BytesIO:
        return PdfExportService.render(ExportService.build(report_type, report))

    @staticmethod
    def render(model: ReportExportModel) -> io.BytesIO:
        stream = io.BytesIO()
        page_size = landscape(A4) if len(model.headers) > 5 else A4
        document = SimpleDocTemplate(stream, pagesize=page_size, rightMargin=30, leftMargin=30, topMargin=45, bottomMargin=45)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("ReportTitle", parent=styles["Heading1"], fontSize=14, alignment=1, spaceAfter=4)
        subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=9, alignment=1, spaceAfter=12)
        cell_style = ParagraphStyle("ReportCell", parent=styles["Normal"], fontSize=7, leading=9)
        elements = [Paragraph(escape(model.organization_name.upper()), title_style), Paragraph(escape(model.title), title_style), Paragraph(escape(model.subtitle), subtitle_style)]

        table_data = [[Paragraph(f"<b>{escape(header)}</b>", cell_style) for header in model.headers]]
        row_styles = []
        for index, row in enumerate(model.rows, start=1):
            rendered = []
            for value in row.values:
                text = format_currency_idr(value) if isinstance(value, Decimal) else "" if value is None else str(value)
                rendered.append(Paragraph(escape(text), cell_style))
            table_data.append(rendered)
            row_styles.append((row.style, index))

        available_width = page_size[0] - 60
        widths = [available_width / len(model.headers)] * len(model.headers)
        if len(model.headers) == 3:
            widths = [available_width * 0.16, available_width * 0.54, available_width * 0.30]
        table = Table(table_data, colWidths=widths, repeatRows=1)
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for style, index in row_styles:
            if style == "section":
                commands.extend([("BACKGROUND", (0, index), (-1, index), colors.HexColor("#475569")), ("TEXTCOLOR", (0, index), (-1, index), colors.white)])
            if style in {"subtotal", "total", "grand_total"}:
                commands.append(("FONTNAME", (0, index), (-1, index), "Helvetica-Bold"))
            if style == "grand_total":
                commands.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#DCFCE7")))
        table.setStyle(TableStyle(commands))
        elements.extend([table, Spacer(1, 28)])
        approval = Table([["Disusun oleh,", "Diperiksa oleh,", "Disahkan oleh,"], ["\n\n\n(________________)", "\n\n\n(________________)", "\n\n\n(________________)"]], colWidths=[available_width / 3] * 3)
        approval.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        elements.append(approval)

        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.drawString(30, 22, f"Dihasilkan {date.today().isoformat()} dari data pelaporan otoritatif")
            canvas.drawRightString(page_size[0] - 30, 22, f"Halaman {doc.page}")
            canvas.restoreState()

        document.build(elements, onFirstPage=footer, onLaterPages=footer)
        stream.seek(0)
        return stream

    @staticmethod
    def export_profit_loss(report: BaseModel) -> io.BytesIO:
        return PdfExportService.export("profit-loss", report)

    @staticmethod
    def export_balance_sheet(report: BaseModel) -> io.BytesIO:
        return PdfExportService.export("balance-sheet", report)
