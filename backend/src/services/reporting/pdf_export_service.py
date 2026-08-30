import io
from decimal import Decimal
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from src.schemas.reporting import (
    ProfitLossReportResponse,
    BalanceSheetReportResponse
)


def format_currency_idr(val: Decimal | float) -> str:
    num = float(val)
    return f"Rp {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class PdfExportService:
    @staticmethod
    def export_profit_loss(data: ProfitLossReportResponse) -> io.BytesIO:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            alignment=1, # Center
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            alignment=1,
            spaceAfter=15
        )

        elements = []
        elements.append(Paragraph(f"<b>{data.organization_name.upper()}</b>", title_style))
        elements.append(Paragraph(f"LAPORAN LABA RUGI — Periode: {data.period_label}", subtitle_style))

        # Table data
        table_data = [["Kode", "Keterangan", "Jumlah"]]

        def add_sec(sec_title, lines, subtotal):
            table_data.append(["", f"<b>{sec_title}</b>", ""])
            for l in lines:
                table_data.append([l.account_code or "", f"  {l.line_name}", format_currency_idr(l.amount)])
            table_data.append(["", f"<b>Total {sec_title}</b>", f"<b>{format_currency_idr(subtotal)}</b>"])

        add_sec("PENDAPATAN USAHA", data.revenue_section.lines, data.revenue_section.subtotal)
        add_sec("HARGA POKOK PROYEK (HPP)", data.cogs_section.lines, data.cogs_section.subtotal)
        table_data.append(["", "<b>LABA KOTOR (GROSS PROFIT)</b>", f"<b>{format_currency_idr(data.gross_profit)}</b>"])
        add_sec("BEBAN OPERASIONAL", data.operating_expenses_section.lines, data.operating_expenses_section.subtotal)
        table_data.append(["", "<b>LABA USAHA (OPERATING PROFIT)</b>", f"<b>{format_currency_idr(data.operating_profit)}</b>"])
        table_data.append(["", "<b>LABA BERSIH TAHUN BERJALAN</b>", f"<b>{format_currency_idr(data.net_profit)}</b>"])

        # Convert rows into paragraphs
        formatted_table = []
        for row in table_data:
            c0 = Paragraph(row[0], styles["Normal"])
            c1 = Paragraph(row[1], styles["Normal"])
            c2 = Paragraph(f"<para align='right'>{row[2]}</para>", styles["Normal"])
            formatted_table.append([c0, c1, c2])

        t = Table(formatted_table, colWidths=[60, 320, 140])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))

        elements.append(t)
        doc.build(elements)
        buf.seek(0)
        return buf

    @staticmethod
    def export_balance_sheet(data: BalanceSheetReportResponse) -> io.BytesIO:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            alignment=1,
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            alignment=1,
            spaceAfter=15
        )

        elements = []
        elements.append(Paragraph(f"<b>{data.organization_name.upper()}</b>", title_style))
        elements.append(Paragraph(f"LAPORAN NERACA — Per Tanggal: {data.as_of_date}", subtitle_style))

        table_data = [["Kode", "Komponen Neraca", "Jumlah"]]

        def add_sec(sec_title, lines, subtotal):
            table_data.append(["", f"<b>{sec_title}</b>", ""])
            for l in lines:
                table_data.append([l.account_code or "", f"  {l.line_name}", format_currency_idr(l.amount)])
            table_data.append(["", f"<b>Total {sec_title}</b>", f"<b>{format_currency_idr(subtotal)}</b>"])

        add_sec("ASET LANCAR", data.current_assets.lines, data.current_assets.subtotal)
        add_sec("ASET TETAP", data.fixed_assets.lines, data.fixed_assets.subtotal)
        table_data.append(["", "<b>TOTAL ASET</b>", f"<b>{format_currency_idr(data.total_assets)}</b>"])

        add_sec("KEWAJIBAN JANGKA PENDEK", data.current_liabilities.lines, data.current_liabilities.subtotal)
        add_sec("EKUITAS", data.equity.lines, data.equity.subtotal)
        table_data.append(["", "<b>TOTAL KEWAJIBAN & EKUITAS</b>", f"<b>{format_currency_idr(data.total_liabilities_and_equity)}</b>"])

        formatted_table = []
        for row in table_data:
            c0 = Paragraph(row[0], styles["Normal"])
            c1 = Paragraph(row[1], styles["Normal"])
            c2 = Paragraph(f"<para align='right'>{row[2]}</para>", styles["Normal"])
            formatted_table.append([c0, c1, c2])

        t = Table(formatted_table, colWidths=[60, 320, 140])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))

        elements.append(t)
        doc.build(elements)
        buf.seek(0)
        return buf
